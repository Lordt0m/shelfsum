import csv
from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business, Membership
from catalogue.models import Product
from inventory.models import StockAdjustment, StockMovement
from inventory.services import record_stock_adjustment
from purchases.models import Purchase, PurchaseLine
from purchases.services import complete_purchase, void_purchase
from sales.models import Sale, SaleLine
from sales.services import complete_sale, void_sale
from reports.movement import current_month_bounds


LAGOS = ZoneInfo("Africa/Lagos")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MovementReportRequestTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="owner@example.com", password="password"
        )
        self.staff = user_model.objects.create_user(
            email="staff@example.com", password="password"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )
        self.client.force_login(self.owner)

    def product(self, name="Beans", sku="BEANS", stock=20, business=None):
        return Product.objects.create(
            business=business or self.business,
            name=name,
            sku=sku,
            stock_on_hand=stock,
            unit_cost=Decimal("3.00"),
            selling_price=Decimal("10.00"),
        )

    def set_movement_time(self, movement, value):
        with connection.cursor() as cursor:
            cursor.execute(
                f'UPDATE "{StockMovement._meta.db_table}" SET "created_at" = %s WHERE "id" = %s',
                [value, movement.pk],
            )
        movement.refresh_from_db()
        return movement

    def adjustment(self, product, quantity, at=None):
        business = product.business
        actor = self.owner if business.pk == self.business.pk else product.business.memberships.get(role=Membership.Role.OWNER).user
        adjustment = record_stock_adjustment(
            business=business,
            actor=actor,
            product=product,
            quantity_change=quantity,
            reason=StockAdjustment.Reason.FOUND if quantity > 0 else StockAdjustment.Reason.DAMAGE,
        )
        movement = StockMovement.objects.get(stock_adjustment=adjustment)
        return self.set_movement_time(movement, at) if at else movement

    def purchase(self, product, quantity=2, at=None, reference="PO-1"):
        purchase = Purchase.objects.create(
            business=self.business,
            creator=self.owner,
            purchase_date=date(2026, 9, 15),
            reference=reference,
        )
        line = PurchaseLine.objects.create(
            purchase=purchase,
            product=product,
            quantity=quantity,
            unit_cost=Decimal("4.00"),
        )
        complete_purchase(business=self.business, actor=self.owner, purchase=purchase)
        movement = StockMovement.objects.get(purchase_line=line)
        return self.set_movement_time(movement, at) if at else movement

    def sale(self, product, quantity=1, at=None, reference="SO-1"):
        sale = Sale.objects.create(
            business=self.business,
            creator=self.owner,
            sale_date=date(2026, 9, 15),
            reference=reference,
        )
        line = SaleLine.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_price=Decimal("7.00"),
        )
        complete_sale(business=self.business, actor=self.owner, sale=sale)
        movement = StockMovement.objects.get(sale_line=line)
        return self.set_movement_time(movement, at) if at else movement

    def csv_rows(self, params=None):
        response = self.client.get(reverse("reports_movements_csv"), params or {})
        return response, list(csv.reader(StringIO(response.content.decode("utf-8"))))

    def test_lagos_boundaries_include_local_midnight_and_exclude_utc_adjacent_rows(self):
        product = self.product()
        before = self.adjustment(product, 1, datetime(2026, 8, 31, 22, 59, tzinfo=datetime_timezone.utc))
        start = self.adjustment(product, 2, datetime(2026, 8, 31, 23, 0, tzinfo=datetime_timezone.utc))
        end = self.adjustment(product, 3, datetime(2026, 9, 30, 22, 59, 59, tzinfo=datetime_timezone.utc))
        after = self.adjustment(product, 4, datetime(2026, 9, 30, 23, 0, tzinfo=datetime_timezone.utc))

        response = self.client.get(
            reverse("reports_movements"),
            {"date_from": "2026-09-01", "date_to": "2026-09-30"},
        )
        ids = {row.movement.pk for row in response.context["report"].rows}
        self.assertEqual(ids, {start.pk, end.pk})
        self.assertNotIn(before.pk, ids)
        self.assertNotIn(after.pk, ids)
        self.assertContains(response, "2026-09-01 00:00")
        self.assertContains(response, "2026-09-30 23:59")

    @override_settings(TIME_ZONE="UTC")
    def test_html_lagos_timestamp_is_not_relocalized_by_active_settings(self):
        product = self.product()
        self.adjustment(
            product,
            1,
            datetime(2026, 9, 15, 10, 0, tzinfo=datetime_timezone.utc),
        )
        params = {"date_from": "2026-09-15", "date_to": "2026-09-15"}
        html = self.client.get(reverse("reports_movements"), params)
        csv_response, rows = self.csv_rows(params)
        self.assertContains(html, "2026-09-15 11:00:00 +0100")
        self.assertNotContains(html, "2026-09-15 10:00:00 +0000")
        self.assertEqual(rows[1][0], "2026-09-15T11:00:00+01:00")
        self.assertEqual(csv_response["Content-Type"], "text/csv; charset=utf-8")

    @override_settings(TIME_ZONE="Africa/Lagos")
    def test_omitted_dates_default_to_current_lagos_month_from_current_instant(self):
        now = datetime(2026, 9, 30, 23, 30, tzinfo=datetime_timezone.utc)
        product = self.product()
        included = self.adjustment(product, 1, datetime(2026, 10, 1, 0, 1, tzinfo=datetime_timezone.utc))
        excluded = self.adjustment(product, 1, datetime(2026, 9, 30, 22, 59, tzinfo=datetime_timezone.utc))
        with patch("reports.movement.timezone.now", return_value=now):
            self.assertEqual(current_month_bounds(), (date(2026, 10, 1), date(2026, 10, 31)))
        with patch(
            "reports.movement.current_month_bounds",
            return_value=(date(2026, 10, 1), date(2026, 10, 31)),
        ):
            response = self.client.get(reverse("reports_movements"))
        self.assertContains(response, 'name="date_from" value="2026-10-01"')
        self.assertContains(response, 'name="date_to" value="2026-10-31"')
        self.assertEqual(
            [row.movement.pk for row in response.context["report"].rows],
            [included.pk],
        )

    def test_one_sided_and_inclusive_date_filters(self):
        product = self.product()
        older = self.adjustment(product, 1, datetime(2026, 8, 31, 22, 0, tzinfo=datetime_timezone.utc))
        middle = self.adjustment(product, 2, datetime(2026, 9, 15, 12, 0, tzinfo=datetime_timezone.utc))
        newer = self.adjustment(product, 3, datetime(2026, 10, 1, 0, 0, tzinfo=datetime_timezone.utc))
        from_only = self.client.get(reverse("reports_movements"), {"date_from": "2026-09-01"})
        to_only = self.client.get(reverse("reports_movements"), {"date_to": "2026-09-30"})
        self.assertEqual({r.movement.pk for r in from_only.context["report"].rows}, {middle.pk, newer.pk})
        self.assertEqual({r.movement.pk for r in to_only.context["report"].rows}, {older.pk, middle.pk})
        self.assertContains(from_only, 'name="date_to" value=""')
        self.assertContains(to_only, 'name="date_from" value=""')

    def test_all_origin_kinds_have_explanatory_links_and_reversal_wording(self):
        product = self.product(stock=20)
        adjustment = self.adjustment(product, 2, datetime(2026, 9, 15, 9, tzinfo=LAGOS))
        purchase = self.purchase(product, quantity=2, at=datetime(2026, 9, 15, 10, tzinfo=LAGOS))
        sale = self.sale(product, quantity=1, at=datetime(2026, 9, 15, 11, tzinfo=LAGOS))
        void_purchase(business=self.business, actor=self.owner, purchase=purchase.purchase_line.purchase)
        purchase_reversal = StockMovement.objects.get(reversal_of=purchase)
        void_sale(business=self.business, actor=self.owner, sale=sale.sale_line.sale)
        sale_reversal = StockMovement.objects.get(reversal_of=sale)
        for movement in (purchase_reversal, sale_reversal):
            self.set_movement_time(movement, datetime(2026, 9, 15, 12, tzinfo=LAGOS))

        response = self.client.get(reverse("reports_movements"), {"date_from": "2026-09-01", "date_to": "2026-09-30"})
        self.assertContains(response, reverse("adjustment_detail", args=[adjustment.stock_adjustment_id]))
        self.assertContains(response, reverse("purchase_detail", args=[purchase.purchase_line.purchase_id]))
        self.assertContains(response, reverse("sale_detail", args=[sale.sale_line.sale_id]))
        self.assertContains(response, "Reversal of voided Purchase")
        self.assertContains(response, "Reversal of voided Sale")

    def test_kind_filter_and_signed_net_are_exactly_the_displayed_rows(self):
        product = self.product()
        self.adjustment(product, 5, datetime(2026, 9, 15, 9, tzinfo=LAGOS))
        sale = self.sale(product, quantity=2, at=datetime(2026, 9, 15, 10, tzinfo=LAGOS))
        void_sale(business=self.business, actor=self.owner, sale=sale.sale_line.sale)
        response = self.client.get(reverse("reports_movements"), {"kind": "sale"})
        report = response.context["report"]
        self.assertEqual([row.movement.kind for row in report.rows], [StockMovement.Kind.SALE])
        self.assertEqual(report.net_change, Decimal("-2"))
        self.assertContains(response, "Net change")
        self.assertContains(response, "-2")

    def test_product_filter_is_current_business_scoped_and_choices_do_not_leak(self):
        own = self.product(name="Own", sku="OWN")
        other_business = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(email="other@example.com", password="password")
        Membership.objects.create(user=other_owner, business=other_business, role=Membership.Role.OWNER)
        foreign = self.product(name="Foreign", sku="FOREIGN", business=other_business)
        self.adjustment(own, 1)
        self.adjustment(foreign, 9)
        response = self.client.get(reverse("reports_movements"), {"product": str(foreign.pk)})
        self.assertContains(response, "Choose a Product from this Business.")
        self.assertNotContains(response, "Foreign")
        self.assertNotContains(response, "Export CSV")
        self.assertContains(response, f'<option value="{own.pk}">Own')
        self.assertNotContains(response, f'<option value="{foreign.pk}">')
        selected = self.client.get(
            reverse("reports_movements"), {"product": str(own.pk)}
        )
        self.assertContains(selected, f'<option value="{own.pk}" selected>Own')

    def test_unfiltered_html_and_csv_isolate_foreign_business_movements(self):
        own = self.product(name="Own unfiltered", sku="OWN-U")
        other_business = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(
            email="other-unfiltered@example.com", password="password"
        )
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        foreign = self.product(
            name="Foreign unfiltered", sku="FOREIGN-U", business=other_business
        )
        self.adjustment(
            own, 2, datetime(2026, 9, 15, 10, 0, tzinfo=datetime_timezone.utc)
        )
        self.adjustment(
            foreign, 9, datetime(2026, 9, 15, 11, 0, tzinfo=datetime_timezone.utc)
        )
        params = {"date_from": "2026-09-01", "date_to": "2026-09-30"}
        html = self.client.get(reverse("reports_movements"), params)
        _, rows = self.csv_rows(params)

        self.assertContains(html, own.name)
        self.assertNotContains(html, foreign.name)
        self.assertEqual([row[1] for row in rows[1:]], [own.name])

    def test_html_and_csv_parity_stable_headings_iso_lagos_offset_integer_and_safe_text(self):
        product = self.product(name="Café", sku="")
        movement = self.adjustment(product, -2, datetime(2026, 9, 15, 10, 5, tzinfo=datetime_timezone.utc))
        Product.objects.filter(pk=product.pk).update(name="=UNSAFE")
        params = {"date_from": "2026-09-01", "date_to": "2026-09-30", "kind": "adjustment", "product": str(product.pk)}
        html = self.client.get(reverse("reports_movements"), params)
        csv_response, rows = self.csv_rows(params)
        self.assertContains(html, f'{reverse("reports_movements_csv")}?kind=adjustment&amp;product={product.pk}&amp;date_from=2026-09-01&amp;date_to=2026-09-30')
        self.assertContains(html, "-2")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ["Lagos timestamp", "Product", "SKU", "Kind", "Quantity change", "Origin"])
        self.assertEqual(rows[1][0], "2026-09-15T11:05:00+01:00")
        self.assertEqual(rows[1][1], "'=UNSAFE")
        self.assertEqual(rows[1][2], "No SKU")
        self.assertEqual(rows[1][4], "-2")
        self.assertEqual(csv_response["Content-Type"], "text/csv; charset=utf-8")

    def test_access_empty_invalid_date_kind_and_product_requests_are_safe(self):
        product = self.product()
        self.adjustment(product, 1)
        params = {"date_from": "not-a-date", "date_to": "2026-09-31", "kind": "draft", "product": "999999"}
        html = self.client.get(reverse("reports_movements"), params)
        _, rows = self.csv_rows(params)
        self.assertContains(html, "Enter a valid start date.")
        self.assertContains(html, "Enter a valid end date.")
        self.assertContains(html, "Choose all, adjustment, purchase, sale, or reversal movements.")
        self.assertContains(html, "Choose a Product from this Business.")
        self.assertContains(html, 'name="date_from" value="not-a-date"')
        self.assertContains(html, '<option value="draft" selected>draft</option>')
        self.assertContains(html, '<option value="999999" selected>999999</option>')
        self.assertContains(html, 'name="date_to" value="2026-09-31"')
        self.assertNotContains(html, "Export CSV")
        self.assertEqual(len(rows), 1)
        empty = self.client.get(reverse("reports_movements"), {"date_from": "2030-01-01", "date_to": "2030-01-31"})
        self.assertContains(empty, "No Stock Movements match these filters.")
        reversed_html = self.client.get(reverse("reports_movements"), {"date_from": "2026-09-30", "date_to": "2026-09-01"})
        self.assertContains(reversed_html, "End date cannot be earlier than start date.")

    def test_roles_demo_inactive_anonymous_business_isolation_and_accessible_discovery(self):
        product = self.product()
        self.adjustment(product, 1)
        for user in (self.owner, self.staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("reports_movements")).status_code, 200)
            self.assertEqual(self.client.get(reverse("reports_movements_csv")).status_code, 200)
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("reports_movements")).status_code, 200)
        self.assertEqual(self.client.get(reverse("reports_movements_csv")).status_code, 200)
        Membership.objects.filter(user=self.staff).update(is_active=False)
        self.assertEqual(self.client.get(reverse("reports_movements")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports_movements_csv")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("reports_movements")).status_code, 302)
        self.assertEqual(self.client.get(reverse("reports_movements_csv")).status_code, 302)
        self.client.force_login(self.owner)
        directory = self.client.get(reverse("reports_index"))
        report = self.client.get(reverse("reports_movements"))
        self.assertContains(directory, "Product movements")
        self.assertContains(report, "<caption>Stock Movements matching the selected filters</caption>")
        for heading in ("Lagos timestamp", "Product", "SKU", "Kind", "Quantity change", "Origin"):
            self.assertContains(report, f'<th scope="col">{heading}</th>')

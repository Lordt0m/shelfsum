import csv
from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.models import Business, Membership
from catalogue.models import Product
from purchases.models import Purchase, PurchaseLine
from purchases.services import complete_purchase, void_purchase


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PurchaseReportRequestTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="password"
        )
        self.staff = get_user_model().objects.create_user(
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

    def completed_purchase(
        self,
        *,
        purchase_date,
        quantity=1,
        unit_cost="10.00",
        supplier_name="",
        reference="",
    ):
        product = Product.objects.create(
            business=self.business,
            name=f"Product {Purchase.objects.count()}",
            sku=f"SKU-{Purchase.objects.count()}",
            stock_on_hand=0,
            unit_cost=Decimal("3.00"),
            selling_price=Decimal("10.00"),
        )
        purchase = Purchase.objects.create(
            business=self.business,
            creator=self.owner,
            purchase_date=purchase_date,
            supplier_name=supplier_name,
            reference=reference,
        )
        PurchaseLine.objects.create(
            purchase=purchase,
            product=product,
            quantity=quantity,
            unit_cost=Decimal(unit_cost),
        )
        return complete_purchase(
            business=self.business, actor=self.owner, purchase=purchase
        )

    def test_completed_purchase_report_shows_inclusive_boundaries_and_exact_total(self):
        first = self.completed_purchase(
            purchase_date=date(2026, 9, 1), quantity=2, unit_cost="10.25"
        )
        last = self.completed_purchase(
            purchase_date=date(2026, 9, 30), quantity=1, unit_cost="12.50"
        )
        outside = self.completed_purchase(
            purchase_date=date(2026, 10, 1), quantity=1, unit_cost="99.00"
        )

        response = self.client.get(
            reverse("reports_purchases"),
            {"date_from": "2026-09-01", "date_to": "2026-09-30"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Purchase #{first.pk}")
        self.assertContains(response, f"Purchase #{last.pk}")
        self.assertNotContains(response, f"Purchase #{outside.pk}")
        self.assertContains(response, "33.00")
        self.assertContains(response, "NGN 33.00")
        self.assertContains(response, "No supplier recorded")
        self.assertContains(response, "Quantity by unit cost total")

    def test_default_completed_report_excludes_voided_and_draft_from_active_total(self):
        completed = self.completed_purchase(
            purchase_date=date(2026, 9, 15), quantity=2, unit_cost="10.00"
        )
        voided = self.completed_purchase(
            purchase_date=date(2026, 9, 16), quantity=1, unit_cost="12.00"
        )
        void_purchase(business=self.business, actor=self.owner, purchase=voided)
        draft = Purchase.objects.create(
            business=self.business,
            creator=self.owner,
            purchase_date=date(2026, 9, 17),
        )

        completed_response = self.client.get(reverse("reports_purchases"))
        voided_response = self.client.get(
            reverse("reports_purchases"), {"status": "voided"}
        )

        self.assertContains(completed_response, f"Purchase #{completed.pk}")
        self.assertNotContains(completed_response, f"Purchase #{voided.pk}")
        self.assertNotContains(completed_response, f"Purchase #{draft.pk}")
        self.assertContains(completed_response, "NGN 20.00")
        self.assertContains(voided_response, f"Purchase #{voided.pk}")
        self.assertNotContains(voided_response, f"Purchase #{completed.pk}")
        self.assertContains(
            voided_response,
            "Voided Purchases remain available for inspection. They are excluded from active totals.",
        )
        self.assertContains(voided_response, "NGN 12.00")
        self.assertNotContains(voided_response, "Completed Purchase total")

    def test_html_and_csv_keep_the_same_active_filters_and_results(self):
        included = self.completed_purchase(
            purchase_date=date(2026, 9, 15), quantity=2, unit_cost="10.00"
        )
        excluded = self.completed_purchase(
            purchase_date=date(2026, 10, 1), quantity=1, unit_cost="99.00"
        )
        params = {
            "date_from": "2026-09-01",
            "date_to": "2026-09-30",
        }

        html = self.client.get(reverse("reports_purchases"), params)
        csv_response = self.client.get(reverse("reports_purchases_csv"), params)
        csv_rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8"))))

        self.assertContains(
            html,
            f'{reverse("reports_purchases_csv")}?status=completed&amp;date_from=2026-09-01&amp;date_to=2026-09-30',
        )
        self.assertContains(html, f"Purchase #{included.pk}")
        self.assertNotContains(html, f"Purchase #{excluded.pk}")
        self.assertEqual(csv_rows[1][1], f"Purchase #{included.pk}")
        self.assertEqual(len(csv_rows), 2)

    def test_csv_has_stable_utf8_headings_iso_dates_decimal_values_and_safe_text(self):
        purchase = self.completed_purchase(
            purchase_date=date(2026, 9, 15),
            quantity=2,
            unit_cost="10.00",
            reference="=SUM(A1:A2)",
            supplier_name="-unsafe supplier",
        )
        for character in ("+", "@"):
            self.completed_purchase(
                purchase_date=date(2026, 9, 15),
                reference=f"{character}unsafe reference",
                supplier_name=f"{character}unsafe supplier",
            )

        response = self.client.get(reverse("reports_purchases_csv"))
        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="purchases-report.csv"',
        )
        self.assertEqual(
            rows[0],
            [
                "Purchase date",
                "Purchase reference / ID",
                "Supplier",
                "Status",
                "Quantity by unit cost total",
            ],
        )
        purchase_row = next(row for row in rows[1:] if row[1] == "'=SUM(A1:A2)")
        self.assertEqual(purchase_row[2], "'-unsafe supplier")
        self.assertEqual(purchase_row[4], "20.00")
        self.assertEqual(purchase_row[0], purchase.purchase_date.isoformat())
        text_cells = {row[1] for row in rows[1:]} | {row[2] for row in rows[1:]}
        self.assertTrue(
            {
                "'=SUM(A1:A2)",
                "'-unsafe supplier",
                "'+unsafe reference",
                "'+unsafe supplier",
                "'@unsafe reference",
                "'@unsafe supplier",
            }.issubset(text_cells)
        )

    def test_report_access_allows_owner_staff_and_demo_reads_but_denies_inactive_and_anonymous(self):
        for user in (self.owner, self.staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("reports_purchases")).status_code, 200)
            self.assertEqual(self.client.get(reverse("reports_purchases_csv")).status_code, 200)

        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("reports_purchases")).status_code, 200)
        self.assertEqual(self.client.get(reverse("reports_purchases_csv")).status_code, 200)

        membership = Membership.objects.get(user=self.staff)
        membership.is_active = False
        membership.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(reverse("reports_purchases")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports_purchases_csv")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("reports_purchases")).status_code, 302)

    def test_report_isolates_other_business_and_handles_empty_results(self):
        own = self.completed_purchase(purchase_date=date(2026, 9, 15), unit_cost="10.00")
        other_business = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        other_product = Product.objects.create(
            business=other_business, name="Other product", sku="OTHER-SKU"
        )
        other_purchase = Purchase.objects.create(
            business=other_business,
            creator=other_owner,
            purchase_date=date(2026, 9, 15),
        )
        PurchaseLine.objects.create(
            purchase=other_purchase,
            product=other_product,
            quantity=1,
            unit_cost=Decimal("100.00"),
        )
        complete_purchase(
            business=other_business, actor=other_owner, purchase=other_purchase
        )

        isolated = self.client.get(reverse("reports_purchases"))
        empty = self.client.get(
            reverse("reports_purchases"),
            {"date_from": "2026-10-01", "date_to": "2026-10-31"},
        )

        self.assertContains(isolated, f"Purchase #{own.pk}")
        self.assertNotContains(isolated, f"Purchase #{other_purchase.pk}")
        self.assertNotContains(isolated, "100.00")
        self.assertContains(empty, "No completed Purchases match these filters.")

    def test_invalid_ranges_are_clear_and_export_has_no_records(self):
        self.completed_purchase(purchase_date=date(2026, 9, 15))
        params = {"date_from": "2026-09-30", "date_to": "2026-09-01"}

        html = self.client.get(reverse("reports_purchases"), params)
        csv_response = self.client.get(reverse("reports_purchases_csv"), params)
        csv_rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8"))))

        self.assertContains(html, "End date cannot be earlier than start date.")
        self.assertNotContains(html, "Export CSV")
        self.assertEqual(len(csv_rows), 1)

    def test_invalid_status_and_malformed_dates_are_clear_and_do_not_fall_back(self):
        self.completed_purchase(purchase_date=date(2026, 9, 15))
        params = {"status": "draft", "date_from": "not-a-date", "date_to": "2026-09-31"}

        html = self.client.get(reverse("reports_purchases"), params)
        csv_response = self.client.get(reverse("reports_purchases_csv"), params)
        csv_rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8"))))

        self.assertContains(html, "Choose completed or voided Purchases.")
        self.assertContains(html, "Enter a valid start date.")
        self.assertContains(html, "Enter a valid end date.")
        self.assertContains(html, 'name="date_from" value="not-a-date"')
        self.assertContains(html, 'name="date_to" value="2026-09-31"')
        self.assertNotContains(html, "Export CSV")
        self.assertNotContains(html, "Purchase #")
        self.assertEqual(len(csv_rows), 1)

    def test_one_sided_date_filter_does_not_add_an_implicit_bound(self):
        older = self.completed_purchase(purchase_date=date(2026, 8, 31))
        newer = self.completed_purchase(purchase_date=date(2026, 10, 1), unit_cost="12.00")

        response = self.client.get(
            reverse("reports_purchases"), {"date_from": "2026-09-01"}
        )

        self.assertNotContains(response, f"Purchase #{older.pk}")
        self.assertContains(response, f"Purchase #{newer.pk}")
        self.assertContains(response, 'name="date_from" value="2026-09-01"')
        self.assertContains(response, 'name="date_to" value=""')

    @override_settings(TIME_ZONE="Africa/Lagos")
    def test_omitted_dates_default_to_current_lagos_calendar_month_and_utc_boundary(self):
        utc_now = datetime(2026, 9, 30, 23, 30, tzinfo=datetime_timezone.utc)
        lagos_today = utc_now.astimezone(ZoneInfo("Africa/Lagos")).date()
        with patch("reports.purchase.timezone.localdate", return_value=lagos_today):
            included = self.completed_purchase(
                purchase_date=date(2026, 10, 1), unit_cost="10.00"
            )
            excluded = self.completed_purchase(
                purchase_date=date(2026, 9, 30), unit_cost="99.00"
            )
            html = self.client.get(reverse("reports_purchases"))
            csv_response = self.client.get(reverse("reports_purchases_csv"))

        self.assertContains(html, 'name="date_from" value="2026-10-01"')
        self.assertContains(html, 'name="date_to" value="2026-10-31"')
        self.assertContains(html, f"Purchase #{included.pk}")
        self.assertNotContains(html, f"Purchase #{excluded.pk}")
        csv_rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8"))))
        self.assertEqual(csv_rows[1][1], f"Purchase #{included.pk}")
        self.assertEqual(len(csv_rows), 2)

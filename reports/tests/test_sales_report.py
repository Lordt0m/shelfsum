import csv
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.models import Business, Membership
from catalogue.models import Product
from sales.models import Sale, SaleLine
from sales.services import complete_sale
from sales.services import void_sale


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SalesReportRequestTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="password"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )
        self.client.force_login(self.owner)

    def completed_sale(
        self,
        *,
        sale_date,
        quantity,
        unit_price,
        reference="",
        customer_name="",
    ):
        product = Product.objects.create(
            business=self.business,
            name=f"Product {Sale.objects.count()}",
            sku=f"SKU-{Sale.objects.count()}",
            stock_on_hand=20,
            unit_cost=Decimal("3.00"),
            selling_price=Decimal("10.00"),
        )
        sale = Sale.objects.create(
            business=self.business,
            creator=self.owner,
            sale_date=sale_date,
            reference=reference,
            customer_name=customer_name,
        )
        SaleLine.objects.create(
            sale=sale,
            product=product,
            quantity=quantity,
            unit_price=Decimal(unit_price),
        )
        return complete_sale(business=self.business, actor=self.owner, sale=sale)

    def test_completed_sales_report_includes_inclusive_boundaries_and_exact_totals(self):
        first = self.completed_sale(
            sale_date=date(2026, 9, 1), quantity=2, unit_price="10.00"
        )
        last = self.completed_sale(
            sale_date=date(2026, 9, 30), quantity=1, unit_price="12.00"
        )
        outside = self.completed_sale(
            sale_date=date(2026, 10, 1), quantity=1, unit_price="99.00"
        )

        response = self.client.get(
            reverse("reports_sales"),
            {"date_from": "2026-09-01", "date_to": "2026-09-30"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("reports_sales")}">Reports</a>',
            html=True,
        )
        self.assertContains(response, f"Sale #{first.pk}")
        self.assertContains(response, f"Sale #{last.pk}")
        self.assertNotContains(response, f"Sale #{outside.pk}")
        self.assertContains(response, "32.00")
        self.assertContains(response, "9.00")
        self.assertContains(response, "23.00")

    def test_default_is_completed_and_voided_history_is_explicitly_excluded_from_active_totals(self):
        completed = self.completed_sale(
            sale_date=date(2026, 9, 15), quantity=2, unit_price="10.00"
        )
        voided = self.completed_sale(
            sale_date=date(2026, 9, 16), quantity=1, unit_price="12.00"
        )
        void_sale(business=self.business, actor=self.owner, sale=voided)
        draft = Sale.objects.create(
            business=self.business, creator=self.owner, sale_date=date(2026, 9, 17)
        )

        completed_response = self.client.get(reverse("reports_sales"))
        voided_response = self.client.get(
            reverse("reports_sales"), {"status": "voided"}
        )

        self.assertContains(completed_response, f"Sale #{completed.pk}")
        self.assertNotContains(completed_response, f"Sale #{voided.pk}")
        self.assertNotContains(completed_response, f"Sale #{draft.pk}")
        self.assertContains(completed_response, "NGN 20.00")
        self.assertContains(voided_response, f"Sale #{voided.pk}")
        self.assertNotContains(voided_response, f"Sale #{completed.pk}")
        self.assertContains(
            voided_response, "Voided Sales remain available for inspection. They are excluded from active totals."
        )
        self.assertContains(voided_response, "NGN 12.00")
        self.assertContains(voided_response, "NGN 3.00")
        self.assertContains(voided_response, "NGN 9.00")

    def test_html_and_csv_keep_the_same_active_filters_and_results(self):
        included = self.completed_sale(
            sale_date=date(2026, 9, 15), quantity=1, unit_price="10.00"
        )
        excluded = self.completed_sale(
            sale_date=date(2026, 10, 1), quantity=1, unit_price="99.00"
        )
        filters = {"date_from": "2026-09-01", "date_to": "2026-09-30"}

        html = self.client.get(reverse("reports_sales"), filters)
        csv_response = self.client.get(reverse("reports_sales_csv"), filters)
        csv_rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8"))))

        self.assertContains(
            html,
            f'{reverse("reports_sales_csv")}?status=completed&amp;date_from=2026-09-01&amp;date_to=2026-09-30',
        )
        self.assertContains(html, f"Sale #{included.pk}")
        self.assertNotContains(html, f"Sale #{excluded.pk}")
        self.assertEqual(csv_rows[1][1], f"Sale #{included.pk}")
        self.assertEqual(len(csv_rows), 2)

    def test_csv_has_stable_utf8_headings_decimal_values_and_safe_text_cells(self):
        sale = self.completed_sale(
            sale_date=date(2026, 9, 15),
            quantity=2,
            unit_price="10.00",
            reference="=SUM(A1:A2)",
            customer_name="-unsafe customer",
        )
        for character in ("+", "@"):
            self.completed_sale(
                sale_date=date(2026, 9, 15),
                quantity=1,
                unit_price="10.00",
                reference=f"{character}unsafe reference",
                customer_name=f"{character}unsafe customer",
            )

        response = self.client.get(reverse("reports_sales_csv"))
        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="sales-report.csv"')
        self.assertEqual(
            rows[0],
            [
                "Sale date",
                "Sale reference / ID",
                "Customer",
                "Status",
                "Revenue",
                "Estimated COGS",
                "Estimated gross margin",
            ],
        )
        sale_row = next(row for row in rows[1:] if row[1] == "'=SUM(A1:A2)")
        self.assertEqual(sale_row[2], "'-unsafe customer")
        self.assertEqual(sale_row[4:], ["20.00", "6.00", "14.00"])
        self.assertEqual(sale_row[0], sale.sale_date.isoformat())
        text_cells = {row[1] for row in rows[1:]} | {row[2] for row in rows[1:]}
        self.assertTrue(
            {
                "'=SUM(A1:A2)",
                "'-unsafe customer",
                "'+unsafe reference",
                "'+unsafe customer",
                "'@unsafe reference",
                "'@unsafe customer",
            }.issubset(text_cells)
        )

    def test_report_access_follows_active_membership_for_html_and_csv(self):
        staff = get_user_model().objects.create_user(
            email="staff@example.com", password="password"
        )
        membership = Membership.objects.create(
            user=staff, business=self.business, role=Membership.Role.STAFF
        )

        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("reports_sales")).status_code, 200)
        self.assertEqual(self.client.get(reverse("reports_sales_csv")).status_code, 200)
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        self.assertEqual(self.client.get(reverse("reports_sales")).status_code, 200)
        membership.is_active = False
        membership.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(reverse("reports_sales")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports_sales_csv")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("reports_sales")).status_code, 302)

    def test_report_isolates_other_business_sales_and_handles_empty_results(self):
        own_sale = self.completed_sale(
            sale_date=date(2026, 9, 15), quantity=1, unit_price="10.00"
        )
        other_business = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        other_product = Product.objects.create(
            business=other_business,
            name="Other product",
            sku="OTHER-SKU",
            stock_on_hand=20,
            unit_cost=Decimal("4.00"),
            selling_price=Decimal("100.00"),
        )
        other_sale = Sale.objects.create(
            business=other_business, creator=other_owner, sale_date=date(2026, 9, 15)
        )
        SaleLine.objects.create(
            sale=other_sale,
            product=other_product,
            quantity=1,
            unit_price=Decimal("100.00"),
        )
        complete_sale(business=other_business, actor=other_owner, sale=other_sale)

        isolated = self.client.get(reverse("reports_sales"))
        empty = self.client.get(
            reverse("reports_sales"),
            {"date_from": "2026-10-01", "date_to": "2026-10-31"},
        )

        self.assertContains(isolated, f"Sale #{own_sale.pk}")
        self.assertNotContains(isolated, f"Sale #{other_sale.pk}")
        self.assertNotContains(isolated, "100.00")
        self.assertContains(empty, "No completed Sales match these filters.")

    def test_invalid_ranges_are_clear_and_export_no_records(self):
        self.completed_sale(
            sale_date=date(2026, 9, 15), quantity=1, unit_price="10.00"
        )
        filters = {"date_from": "2026-09-30", "date_to": "2026-09-01"}

        html = self.client.get(reverse("reports_sales"), filters)
        csv_response = self.client.get(reverse("reports_sales_csv"), filters)
        csv_rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8"))))

        self.assertContains(html, "End date cannot be earlier than start date.")
        self.assertNotContains(html, "Export CSV")
        self.assertEqual(len(csv_rows), 1)

    def test_invalid_status_is_clear_and_does_not_fall_back_to_unfiltered_sales(self):
        self.completed_sale(
            sale_date=date(2026, 9, 15), quantity=1, unit_price="10.00"
        )

        response = self.client.get(reverse("reports_sales"), {"status": "draft"})

        self.assertContains(response, "Choose completed or voided Sales.")
        self.assertNotContains(response, "Sale #")

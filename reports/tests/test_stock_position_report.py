import csv
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.dashboard import dashboard_context
from businesses.models import Business, Membership
from catalogue.models import Product


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class StockPositionReportRequestTests(TestCase):
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

    def product(
        self,
        *,
        name,
        sku="",
        stock=0,
        cost="1.00",
        threshold=0,
        active=True,
        business=None,
    ):
        return Product.objects.create(
            business=business or self.business,
            name=name,
            sku=sku,
            stock_on_hand=stock,
            unit_cost=Decimal(cost),
            selling_price=Decimal("10.00"),
            low_stock_threshold=threshold,
            is_active=active,
        )

    def csv_rows(self, params=None):
        response = self.client.get(reverse("reports_stock_position_csv"), params or {})
        return response, list(csv.reader(StringIO(response.content.decode("utf-8"))))

    def test_default_is_current_positive_stock_including_inactive_and_reconciles_dashboard(self):
        active = self.product(name="Beans", sku="BEANS", stock=8, cost="4.00")
        inactive = self.product(
            name="Rice", sku="RICE", stock=3, cost="7.50", active=False
        )
        self.product(name="Empty", stock=0, cost="99.00")

        response = self.client.get(reverse("reports_stock_position"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, active.name)
        self.assertContains(response, inactive.name)
        self.assertNotContains(response, "Empty")
        self.assertContains(response, "NGN 54.50")
        self.assertEqual(response.context["report"].total, dashboard_context(business=self.business)["dashboard"]["stock_value"])

    def test_product_status_filters_active_inactive_and_all(self):
        active = self.product(name="Active", stock=2)
        inactive = self.product(name="Inactive", stock=2, active=False)

        for status, shown, hidden in (
            ("active", active, inactive),
            ("inactive", inactive, active),
            ("all", active, None),
        ):
            response = self.client.get(reverse("reports_stock_position"), {"product_status": status})
            shown_names = {row.product.name for row in response.context["report"].rows}
            self.assertIn(shown.name, shown_names)
            if hidden:
                self.assertNotIn(hidden.name, shown_names)
        self.assertIn(
            inactive.name,
            {
                row.product.name
                for row in self.client.get(
                    reverse("reports_stock_position"), {"product_status": "all"}
                ).context["report"].rows
            },
        )

    def test_stock_state_filters_include_low_zero_and_inactive_products(self):
        positive = self.product(name="Positive", stock=6, cost="2.00", threshold=2)
        low = self.product(name="Low", stock=2, cost="3.00", threshold=2)
        zero = self.product(
            name="Zero inactive", stock=0, cost="4.00", threshold=0, active=False
        )

        for state, expected_names in (
            ("positive", {positive.name, low.name}),
            ("low", {low.name, zero.name}),
            ("zero", {zero.name}),
            ("all", {positive.name, low.name, zero.name}),
        ):
            response = self.client.get(
                reverse("reports_stock_position"),
                {"product_status": "all", "stock_state": state},
            )
            actual_names = {row.product.name for row in response.context["report"].rows}
            self.assertEqual(actual_names, expected_names)

    def test_total_is_the_exact_sum_of_displayed_rows_for_every_filter(self):
        self.product(name="Positive", stock=6, cost="2.00", threshold=2)
        self.product(name="Low", stock=2, cost="3.50", threshold=2)
        self.product(name="Zero", stock=0, cost="7.00", threshold=0, active=False)

        for params in (
            {},
            {"product_status": "active", "stock_state": "all"},
            {"product_status": "inactive", "stock_state": "all"},
            {"product_status": "all", "stock_state": "positive"},
            {"product_status": "all", "stock_state": "low"},
            {"product_status": "all", "stock_state": "zero"},
        ):
            response = self.client.get(reverse("reports_stock_position"), params)
            report = response.context["report"]
            self.assertEqual(report.total, sum((row.value for row in report.rows), Decimal("0.00")))

    def test_html_and_csv_share_rows_filters_links_and_snapshot_disclaimer_without_date_inputs(self):
        included = self.product(name="Included", sku="INC", stock=2, cost="3.25")
        self.product(name="Zero", stock=0, cost="99.00")
        params = {
            "product_status": "active",
            "stock_state": "positive",
            "date_from": "2000-01-01",
            "date_to": "2000-01-31",
        }

        html = self.client.get(reverse("reports_stock_position"), params)
        csv_response, rows = self.csv_rows(params)

        self.assertContains(
            html,
            f'{reverse("reports_stock_position_csv")}?product_status=active&amp;stock_state=positive',
        )
        self.assertContains(html, reverse("product_detail", args=[included.pk]))
        self.assertContains(html, "Current unit costs are a snapshot and do not reconstruct historical inventory value.")
        self.assertNotContains(html, 'type="date"')
        self.assertEqual(rows[1][0], included.name)
        self.assertEqual(len(rows), 2)

    def test_csv_has_stable_utf8_headings_integers_two_decimals_and_safe_text(self):
        product = self.product(name="Safe", sku="SKU", stock=3, cost="20.10")
        Product.objects.filter(pk=product.pk).update(name="\t=SUM(A1:A2)", sku="\r@unsafe")

        response, rows = self.csv_rows()

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="stock-position-report.csv"')
        self.assertEqual(rows[0], ["Product name", "SKU", "Active state", "Stock on Hand", "Current unit cost", "Current stock value"])
        self.assertEqual(rows[1], ["'\t=SUM(A1:A2)", "'\r@unsafe", "Active", "3", "20.10", "60.30"])

    def test_blank_sku_uses_the_product_ui_fallback_and_all_text_columns_are_safe(self):
        product = self.product(name="Named", sku="", stock=1)
        Product.objects.filter(pk=product.pk).update(name="\n=unsafe", is_active=True)

        _, rows = self.csv_rows()

        self.assertEqual(rows[1][0], "'\n=unsafe")
        self.assertEqual(rows[1][1], "No SKU")
        self.assertEqual(rows[1][2], "Active")

    def test_access_allows_owner_staff_and_demo_reads_but_denies_inactive_and_anonymous(self):
        for user in (self.owner, self.staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("reports_stock_position")).status_code, 200)
            self.assertEqual(self.client.get(reverse("reports_stock_position_csv")).status_code, 200)

        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        self.assertEqual(self.client.get(reverse("reports_stock_position")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("reports_stock_position_csv")).status_code, 200
        )
        Membership.objects.filter(user=self.staff).update(is_active=False)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("reports_stock_position")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports_stock_position_csv")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("reports_stock_position")).status_code, 302)

    def test_business_isolation_and_empty_state(self):
        own = self.product(name="Own", stock=1, cost="2.00")
        other_business = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        foreign = self.product(name="Foreign", stock=9, cost="99.00", business=other_business)

        isolated = self.client.get(reverse("reports_stock_position"))
        _, isolated_csv_rows = self.csv_rows()
        empty = self.client.get(reverse("reports_stock_position"), {"stock_state": "zero"})

        self.assertContains(isolated, own.name)
        self.assertNotContains(isolated, foreign.name)
        self.assertNotContains(isolated, "99.00")
        self.assertNotIn(foreign.name, [row[0] for row in isolated_csv_rows[1:]])
        self.assertNotIn("99.00", [row[5] for row in isolated_csv_rows[1:]])
        self.assertContains(empty, "No Products match these filters.")

    def test_invalid_filters_have_clear_errors_no_rows_and_no_export_link_or_records(self):
        self.product(name="Visible", stock=1)
        params = {"product_status": "archived", "stock_state": "negative"}

        html = self.client.get(reverse("reports_stock_position"), params)
        _, rows = self.csv_rows(params)

        self.assertContains(html, "Choose active, inactive, or all Products.")
        self.assertContains(html, "Choose positive, low, zero, or all stock.")
        self.assertNotContains(html, "Export CSV")
        self.assertNotContains(html, "Visible")
        self.assertEqual(len(rows), 1)

    def test_directory_and_every_report_navigation_discover_stock_position_with_accessible_table_structure(self):
        self.product(name="Visible", stock=1)
        directory = self.client.get(reverse("reports_index"))
        stock = self.client.get(reverse("reports_stock_position"))

        self.assertContains(directory, f'<a href="{reverse("reports_stock_position")}">', html=False)
        self.assertContains(directory, "Current stock position")
        self.assertContains(stock, "<caption>Products matching the selected filters</caption>")
        for heading in ("Product", "SKU", "Active state", "Stock on Hand", "Current unit cost", "Current stock value"):
            self.assertContains(stock, f'<th scope="col">{heading}</th>')
        for url_name in ("reports_sales", "reports_purchases", "reports_expenses"):
            response = self.client.get(reverse(url_name))
            self.assertContains(response, f'href="{reverse("reports_stock_position")}"')

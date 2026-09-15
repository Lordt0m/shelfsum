from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from auditing.models import AuditEvent
from auditing.services import record_audit_event
from businesses.models import Business, Membership
from catalogue.services import ProductCreation, ProductUpdate, create_product, deactivate_product, update_product
from expenses.models import Expense
from expenses.services import correct_expense, record_expense
from sales.models import Sale, SaleLine
from sales.services import complete_sale, void_sale


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], SESSION_COOKIE_AGE=60 * 24 * 60 * 60)
class BusinessDashboardTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="owner@example.com", password="safe-password-123")
        self.staff = get_user_model().objects.create_user(email="staff@example.com", password="safe-password-123")
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(user=self.owner, business=self.business, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.staff, business=self.business, role=Membership.Role.STAFF)

    def create_product(self, *, name="Beans", stock=10, cost="3.00", threshold=2):
        return create_product(
            business=self.business, actor=self.owner,
            details=ProductCreation(name=name, sku=name.upper(), description="", selling_price=Decimal("10.00"), unit_cost=Decimal(cost), opening_quantity=stock, low_stock_threshold=threshold),
        )

    def complete_sale(self, product, *, sale_date=date(2026, 9, 15), quantity=2, price="10.00"):
        sale = Sale.objects.create(business=self.business, creator=self.owner, sale_date=sale_date)
        SaleLine.objects.create(sale=sale, product=product, quantity=quantity, unit_price=Decimal(price))
        return complete_sale(business=self.business, actor=self.owner, sale=sale)

    def dashboard(self, user=None, now=datetime(2026, 9, 15, 12, tzinfo=datetime_timezone.utc)):
        self.client.force_login(user or self.owner)
        with patch("django.utils.timezone.now", return_value=now):
            return self.client.get(reverse("business_home"))

    def test_dashboard_explains_current_month_known_literal_totals_and_links(self):
        product = self.create_product(stock=8, cost="3.00", threshold=6)
        self.complete_sale(product, sale_date=date(2026, 9, 30), quantity=2, price="10.00")
        update_product(business=self.business, actor=self.owner, product=product, details=ProductUpdate(name=product.name, sku=product.sku, description="", selling_price=Decimal("10.00"), unit_cost=Decimal("4.00"), low_stock_threshold=6))
        record_expense(business=self.business, actor=self.owner, details={"date": date(2026, 9, 30), "category": Expense.Category.RENT, "description": "Rent", "amount": Decimal("5.00"), "notes": ""})
        for number in range(9):
            record_audit_event(business=self.business, actor=self.owner, action="product.viewed", affected_object=product, summary=f"Recent activity {number}")

        response = self.dashboard()

        dashboard = response.context["dashboard"]
        self.assertEqual(dashboard["revenue"], Decimal("20.00"))
        self.assertEqual(dashboard["cost_of_goods_sold"], Decimal("6.00"))
        self.assertEqual(dashboard["expenses"], Decimal("5.00"))
        self.assertEqual(dashboard["profit"], Decimal("9.00"))
        self.assertEqual(dashboard["stock_value"], Decimal("24.00"))
        self.assertContains(response, "NGN 20.00")
        self.assertContains(response, "Operational estimate, not accounting, tax, or cash profit")
        self.assertContains(response, f'{reverse("sale_list")}?status=completed&amp;date_from=2026-09-01&amp;date_to=2026-09-30')
        self.assertContains(response, f'{reverse("expense_list")}?status=recorded&amp;date_from=2026-09-01&amp;date_to=2026-09-30')
        self.assertContains(response, f'{reverse("product_list")}?status=active&amp;stock=low')
        self.assertEqual(len(dashboard["recent_activity"]), 8)
        self.assertTrue(all(event.record_url for event in dashboard["recent_activity"]))

    def test_dashboard_excludes_drafts_voided_records_and_replaced_expense(self):
        product = self.create_product(stock=10)
        completed = self.complete_sale(product, quantity=1, price="12.00")
        void_sale(business=self.business, actor=self.owner, sale=completed)
        draft = Sale.objects.create(business=self.business, creator=self.owner, sale_date=date(2026, 9, 30))
        SaleLine.objects.create(sale=draft, product=product, quantity=3, unit_price=Decimal("99.00"))
        original = record_expense(business=self.business, actor=self.owner, details={"date": date(2026, 9, 15), "category": Expense.Category.RENT, "description": "Old rent", "amount": Decimal("7.00"), "notes": ""})
        correct_expense(business=self.business, actor=self.owner, expense=original, details={"date": date(2026, 9, 15), "category": Expense.Category.RENT, "description": "Corrected rent", "amount": Decimal("4.00"), "notes": ""})

        response = self.dashboard()
        dashboard = response.context["dashboard"]

        self.assertEqual(dashboard["revenue"], Decimal("0"))
        self.assertEqual(dashboard["expenses"], Decimal("4.00"))
        self.assertEqual(dashboard["profit"], Decimal("-4.00"))
        self.assertNotContains(response, "99.00")

    def test_dashboard_includes_both_september_boundaries_and_excludes_adjacent_months(self):
        product = self.create_product(stock=10)
        self.complete_sale(product, sale_date=date(2026, 9, 1), quantity=1)
        self.complete_sale(product, sale_date=date(2026, 9, 30), quantity=1)
        self.complete_sale(product, sale_date=date(2026, 8, 31), quantity=1)
        self.complete_sale(product, sale_date=date(2026, 10, 1), quantity=1)

        response = self.dashboard()
        dashboard = response.context["dashboard"]

        self.assertEqual(dashboard["period_start"], date(2026, 9, 1))
        self.assertEqual(dashboard["period_end"], date(2026, 9, 30))
        self.assertEqual(dashboard["revenue"], Decimal("20.00"))

    def test_dashboard_uses_lagos_utc_month_seam_and_scopes_other_business(self):
        product = self.create_product(stock=10)
        self.complete_sale(product, sale_date=date(2026, 10, 1), quantity=2)
        other = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(email="other@example.com", password="safe-password-123")
        Membership.objects.create(user=other_owner, business=other, role=Membership.Role.OWNER)
        other_product = create_product(business=other, actor=other_owner, details=ProductCreation(name="Other", sku="OTHER", description="", selling_price=Decimal("100.00"), unit_cost=Decimal("1.00"), opening_quantity=2, low_stock_threshold=0))
        other_sale = Sale.objects.create(business=other, creator=other_owner, sale_date=date(2026, 10, 1))
        SaleLine.objects.create(sale=other_sale, product=other_product, quantity=1, unit_price=Decimal("100.00"))
        complete_sale(business=other, actor=other_owner, sale=other_sale)
        record_expense(business=other, actor=other_owner, details={"date": date(2026, 10, 1), "category": Expense.Category.RENT, "description": "Other rent", "amount": Decimal("100.00"), "notes": ""})
        record_audit_event(business=other, actor=other_owner, action="product.viewed", affected_object=other_product, summary="Foreign audit record")

        response = self.dashboard(now=datetime(2026, 9, 30, 23, 30, tzinfo=datetime_timezone.utc))
        dashboard = response.context["dashboard"]

        self.assertEqual(dashboard["period_start"], date(2026, 10, 1))
        self.assertEqual(dashboard["period_end"], date(2026, 10, 31))
        self.assertEqual(dashboard["revenue"], Decimal("20.00"))
        self.assertEqual(dashboard["expenses"], Decimal("0"))
        self.assertEqual(dashboard["stock_value"], Decimal("24.00"))
        self.assertNotContains(response, "100.00")
        self.assertNotContains(response, "Foreign audit record")

    def test_staff_and_demo_members_can_read_dashboard_but_inactive_member_cannot(self):
        self.create_product()
        staff_response = self.dashboard(self.staff)
        self.assertEqual(staff_response.status_code, 200)
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        demo_response = self.dashboard(self.owner)
        self.assertEqual(demo_response.status_code, 200)
        Membership.objects.filter(user=self.staff).update(is_active=False)
        inactive_response = self.dashboard(self.staff)
        self.assertEqual(inactive_response.status_code, 403)

    def test_empty_dashboard_is_usable(self):
        response = self.dashboard()

        self.assertContains(response, "No completed Sales in this period")
        self.assertContains(response, "No recorded Expenses in this period")
        self.assertContains(response, "No active Products are currently low on stock")
        self.assertContains(response, "No recent activity yet")

    def test_inactive_positive_stock_is_in_current_balance(self):
        product = self.create_product(stock=3, cost="4.00", threshold=3)
        deactivate_product(business=self.business, actor=self.owner, product=product)

        response = self.dashboard()

        self.assertEqual(response.context["dashboard"]["stock_value"], Decimal("12.00"))
        self.assertEqual(response.context["dashboard"]["low_stock_count"], 0)

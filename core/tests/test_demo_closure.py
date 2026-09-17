import csv
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.models import Business, Membership
from businesses.services import (
    add_staff_member,
    deactivate_staff_member,
    update_business_settings,
)
from catalogue.models import Product
from catalogue.services import ProductCreation, ProductUpdate, create_product, deactivate_product, update_product
from core.demo import (
    DEMO_BUSINESS_NAME,
    DEMO_OWNER_EMAIL,
    DEMO_OWNER_PASSWORD,
    DEMO_STAFF_EMAIL,
    DEMO_STAFF_PASSWORD,
    seed_demo_business,
)
from expenses.models import Expense
from expenses.services import correct_expense, record_expense, void_expense
from inventory.models import StockAdjustment, StockMovement
from inventory.services import record_stock_adjustment
from purchases.models import Purchase, PurchaseLine
from purchases.services import complete_purchase, create_draft_purchase, save_draft_purchase, void_purchase
from sales.models import Sale, SaleLine
from sales.services import complete_sale, create_draft_sale, save_draft_sale, void_sale
from auditing.models import AuditEvent


DEMO_CREATED_AT = datetime(2026, 8, 20, 12, tzinfo=ZoneInfo("Africa/Lagos"))


def seed_demo_fixture():
    with patch("django.utils.timezone.now", return_value=DEMO_CREATED_AT):
        return seed_demo_business()


def model_rows(model, **filters):
    fields = tuple(field.attname for field in model._meta.concrete_fields)
    return tuple(
        model._base_manager.filter(**filters).order_by("pk").values_list(*fields)
    )


def demo_state_fingerprint(business):
    member_user_ids = Membership.objects.filter(business=business).values_list(
        "user_id", flat=True
    )
    return {
        "business": model_rows(Business, pk=business.pk),
        "memberships": model_rows(Membership, business=business),
        "member_users": model_rows(get_user_model(), pk__in=member_user_ids),
        "products": model_rows(Product, business=business),
        "purchases": model_rows(Purchase, business=business),
        "purchase_lines": model_rows(PurchaseLine, purchase__business=business),
        "sales": model_rows(Sale, business=business),
        "sale_lines": model_rows(SaleLine, sale__business=business),
        "expenses": model_rows(Expense, business=business),
        "stock_adjustments": model_rows(StockAdjustment, business=business),
        "stock_movements": model_rows(StockMovement, business=business),
        "audit_events": model_rows(AuditEvent, business=business),
    }


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DemoRoleBrowseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_demo_fixture()
        cls.owner = get_user_model().objects.get(email=DEMO_OWNER_EMAIL)
        cls.staff = get_user_model().objects.get(email=DEMO_STAFF_EMAIL)
        cls.business = Business.objects.get(name=DEMO_BUSINESS_NAME)
        cls.product = Product.objects.get(business=cls.business, sku="DEMO-NIA-500")
        cls.purchase = Purchase.objects.get(business=cls.business, reference="DEMO-PUR-001")
        cls.sale = Sale.objects.get(business=cls.business, reference="DEMO-SAL-001")
        cls.expense = Expense.objects.get(
            business=cls.business,
            description="Fictional August premises correction",
        )
        cls.adjustment = StockAdjustment.objects.get(
            business=cls.business,
            reason=StockAdjustment.Reason.FOUND,
        )
        foreign_owner = get_user_model().objects.create_user(
            email="foreign-demo@example.com", password="foreign-password"
        )
        cls.foreign_business = Business.objects.create(name="Foreign Demo Shop")
        Membership.objects.create(
            user=foreign_owner,
            business=cls.foreign_business,
            role=Membership.Role.OWNER,
        )
        create_product(
            business=cls.foreign_business,
            actor=foreign_owner,
            details=ProductCreation(
                name="Foreign-only Product",
                sku="FOREIGN-ONLY",
                description="",
                selling_price=Decimal("10.00"),
                unit_cost=Decimal("5.00"),
                opening_quantity=1,
                low_stock_threshold=0,
            ),
        )

    def test_seeded_owner_and_staff_can_browse_all_major_records_reports_and_csv(self):
        browse_pages = (
            ("home", reverse("business_home"), "Demo period: August 2026"),
            ("products", reverse("product_list"), "NiaPalm Twist Noodles"),
            ("product detail", reverse("product_detail", args=[self.product.pk]), "DEMO-NIA-500"),
            ("purchases", reverse("purchase_list"), "Purchase #1"),
            ("purchase detail", reverse("purchase_detail", args=[self.purchase.pk]), "DEMO-PUR-001"),
            ("sales", reverse("sale_list"), "Sale #1"),
            ("sale detail", reverse("sale_detail", args=[self.sale.pk]), "DEMO-SAL-001"),
            ("expenses", reverse("expense_list"), "Fictional August premises correction"),
            ("expense detail", reverse("expense_detail", args=[self.expense.pk]), "Fictional August premises correction"),
            ("stock adjustments", reverse("adjustment_list"), "Found stock"),
            ("adjustment detail", reverse("adjustment_detail", args=[self.adjustment.pk]), "Two fictional sachets"),
            ("audit events", reverse("audit_event_list"), "Completed Sale"),
            ("reports", reverse("reports_index"), "Sales report"),
        )

        for role in (self.owner, self.staff):
            self.client.force_login(role)
            for label, url, expected_text in browse_pages:
                with self.subTest(role=role.email, page=label):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, expected_text)
                    self.assertNotContains(response, "Foreign-only Product")
                    self.assertNotContains(response, "Foreign Demo Shop")

        report_pages = (
            (
                "sales",
                "reports_sales",
                "reports_sales_csv",
                {"status": "completed", "date_from": "2026-08-01", "date_to": "2026-08-31"},
                "DEMO-SAL-001",
                "Revenue",
                "25800.00",
                "Revenue",
            ),
            (
                "purchases",
                "reports_purchases",
                "reports_purchases_csv",
                {"status": "completed", "date_from": "2026-08-01", "date_to": "2026-08-31"},
                "DEMO-PUR-001",
                "Active completed Purchase total",
                "31550.00",
                "Quantity by unit cost total",
            ),
            (
                "expenses",
                "reports_expenses",
                "reports_expenses_csv",
                {"status": "recorded", "date_from": "2026-08-01", "date_to": "2026-08-31"},
                "Fictional August premises correction",
                "Recorded Expense total",
                "275000.00",
                "Amount",
            ),
            (
                "stock position",
                "reports_stock_position",
                "reports_stock_position_csv",
                {"product_status": "active", "stock_state": "positive"},
                "NiaPalm Twist Noodles",
                "Current stock value",
                "59000.00",
                "Current stock value",
            ),
            (
                "movements",
                "reports_movements",
                "reports_movements_csv",
                {"kind": "all", "date_from": "2026-08-01", "date_to": "2026-08-31"},
                "NiaPalm Twist Noodles",
                "Net change",
                "87",
                "Quantity change",
            ),
        )

        for role in (self.owner, self.staff):
            self.client.force_login(role)
            for label, html_route, csv_route, params, expected_text, total_label, expected_total, csv_field in report_pages:
                with self.subTest(role=role.email, report=label):
                    html = self.client.get(reverse(html_route), params)
                    self.assertEqual(html.status_code, 200)
                    self.assertContains(html, expected_text)
                    self.assertContains(html, total_label)
                    self.assertContains(html, expected_total)
                    self.assertNotContains(html, "Foreign-only Product")
                    csv_response = self.client.get(reverse(csv_route), params)
                    self.assertEqual(csv_response.status_code, 200)
                    csv_rows = list(csv.DictReader(StringIO(csv_response.content.decode("utf-8"))))
                    self.assertTrue(any(expected_text in row.values() for row in csv_rows))
                    self.assertEqual(
                        sum((Decimal(row[csv_field]) for row in csv_rows), Decimal("0")),
                        Decimal(expected_total),
                    )
                    self.assertNotIn("Foreign-only Product", csv_response.content.decode("utf-8"))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DemoMutationDenialMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_demo_fixture()
        cls.owner = get_user_model().objects.get(email=DEMO_OWNER_EMAIL)
        cls.staff = get_user_model().objects.get(email=DEMO_STAFF_EMAIL)
        cls.business = Business.objects.get(name=DEMO_BUSINESS_NAME)
        cls.product = Product.objects.get(business=cls.business, sku="DEMO-NIA-500")
        cls.purchase = Purchase.objects.get(business=cls.business, reference="DEMO-PUR-001")
        cls.sale = Sale.objects.get(business=cls.business, reference="DEMO-SAL-001")
        cls.original_expense = Expense.objects.get(
            business=cls.business,
            description="Fictional August premises estimate",
        )
        cls.replacement_expense = Expense.objects.get(
            business=cls.business,
            description="Fictional August premises correction",
        )
        cls.staff_membership = Membership.objects.get(user=cls.staff)

    def test_every_public_demo_service_mutation_is_denied_before_writing(self):
        cases = (
            ("settings", lambda: update_business_settings(business=self.business, actor=self.owner, name="Blocked", phone_number="", address="")),
            ("staff add", lambda: add_staff_member(business=self.business, actor=self.owner, email=self.staff.email)),
            ("staff deactivate", lambda: deactivate_staff_member(business=self.business, actor=self.owner, membership=self.staff_membership)),
            ("product create", lambda: create_product(business=self.business, actor=self.owner, details=ProductCreation(name="Blocked", sku="BLOCKED", description="", selling_price=Decimal("1.00"), unit_cost=Decimal("1.00"), opening_quantity=0, low_stock_threshold=0))),
            ("product edit", lambda: update_product(business=self.business, actor=self.owner, product=self.product, details=ProductUpdate(name=self.product.name, sku=self.product.sku, description=self.product.description, selling_price=self.product.selling_price, unit_cost=self.product.unit_cost, low_stock_threshold=self.product.low_stock_threshold))),
            ("product deactivate", lambda: deactivate_product(business=self.business, actor=self.owner, product=self.product)),
            ("purchase create", lambda: create_draft_purchase(business=self.business, actor=self.owner, form=None, formset=None)),
            ("purchase edit", lambda: save_draft_purchase(business=self.business, actor=self.owner, purchase=self.purchase, form=None, formset=None)),
            ("purchase complete", lambda: complete_purchase(business=self.business, actor=self.owner, purchase=self.purchase)),
            ("purchase void", lambda: void_purchase(business=self.business, actor=self.owner, purchase=self.purchase)),
            ("sale create", lambda: create_draft_sale(business=self.business, actor=self.owner, form=None, formset=None)),
            ("sale edit", lambda: save_draft_sale(business=self.business, actor=self.owner, sale=self.sale, form=None, formset=None)),
            ("sale complete", lambda: complete_sale(business=self.business, actor=self.owner, sale=self.sale)),
            ("sale void", lambda: void_sale(business=self.business, actor=self.owner, sale=self.sale)),
            ("expense create", lambda: record_expense(business=self.business, actor=self.owner, details={})),
            ("expense correct", lambda: correct_expense(business=self.business, actor=self.owner, expense=self.original_expense, details={})),
            ("expense void", lambda: void_expense(business=self.business, actor=self.owner, expense=self.replacement_expense)),
            ("stock adjustment", lambda: record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=1, reason=StockAdjustment.Reason.FOUND)),
        )
        before = demo_state_fingerprint(self.business)

        for label, operation in cases:
            with self.subTest(operation=label), self.assertRaises(PermissionDenied):
                operation()

        after = demo_state_fingerprint(self.business)
        self.assertEqual(after, before)

    def test_every_demo_mutation_request_is_denied_before_writing(self):
        product_payload = {
            "name": self.product.name,
            "sku": self.product.sku,
            "description": self.product.description,
            "selling_price": self.product.selling_price,
            "unit_cost": self.product.unit_cost,
            "opening_quantity": 0,
            "low_stock_threshold": self.product.low_stock_threshold,
        }
        cases = (
            ("settings", "business_settings", {}, {"name": "Blocked", "phone_number": "", "address": ""}),
            ("staff add", "staff_member_add", {}, {"email": self.staff.email}),
            ("staff deactivate", "staff_member_deactivate", {"args": [self.staff_membership.pk]}, {}),
            ("product create", "product_create", {}, product_payload),
            ("product edit", "product_edit", {"args": [self.product.pk]}, product_payload),
            ("product deactivate", "product_deactivate", {"args": [self.product.pk]}, {}),
            ("purchase create", "purchase_create", {}, {}),
            ("purchase edit", "purchase_edit", {"args": [self.purchase.pk]}, {}),
            ("purchase complete", "purchase_detail", {"args": [self.purchase.pk]}, {}),
            ("purchase void", "purchase_void", {"args": [self.purchase.pk]}, {}),
            ("sale create", "sale_create", {}, {}),
            ("sale edit", "sale_edit", {"args": [self.sale.pk]}, {}),
            ("sale complete", "sale_detail", {"args": [self.sale.pk]}, {}),
            ("sale void", "sale_void", {"args": [self.sale.pk]}, {}),
            ("expense create", "expense_create", {}, {}),
            ("expense correct", "expense_correct", {"args": [self.original_expense.pk]}, {}),
            ("expense void", "expense_void", {"args": [self.replacement_expense.pk]}, {}),
            ("stock adjustment", "adjustment_create", {}, {}),
        )
        self.client.force_login(self.owner)
        before = demo_state_fingerprint(self.business)

        for label, route, kwargs, payload in cases:
            with self.subTest(operation=label):
                url = reverse(route, **kwargs)
                response = self.client.post(url, payload)
                self.assertEqual(response.status_code, 403)
                self.assertContains(response, "read-only", status_code=403)

        after = demo_state_fingerprint(self.business)
        self.assertEqual(after, before)

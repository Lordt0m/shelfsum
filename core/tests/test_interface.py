from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from businesses.models import Business, Membership
from catalogue.services import ProductCreation, create_product
from inventory.models import StockMovement
from inventory.services import record_stock_adjustment


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class InterfaceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="interface@example.com", password="password")
        self.business = Business.objects.create(name="Interface Shop")
        Membership.objects.create(user=self.owner, business=self.business, role=Membership.Role.OWNER)
        self.client.force_login(self.owner)

    def product(self, name="Rice", quantity=10, threshold=3):
        return create_product(business=self.business, actor=self.owner, details=ProductCreation(
            name=name, sku=name.upper(), description="", selling_price=Decimal("12.00"),
            unit_cost=Decimal("8.00"), opening_quantity=quantity, low_stock_threshold=threshold,
        ))

    def test_zero_and_healthy_filters_distinguish_stock_states(self):
        empty = self.product("Empty", 0)
        self.product("Low", 2)
        healthy = self.product("Healthy", 10)
        response = self.client.get(reverse("product_list"), {"stock": "out"})
        self.assertEqual(list(response.context["products"]), [empty])
        response = self.client.get(reverse("product_list"), {"stock": "healthy"})
        self.assertEqual(list(response.context["products"]), [healthy])

    def test_product_pagination_retains_search_and_filters(self):
        for index in range(26):
            self.product(f"Rice {index:02}", 0)
        response = self.client.get(reverse("product_list"), {"q": "Rice", "status": "active", "stock": "out", "page": "2"})
        self.assertEqual(len(response.context["products"]), 1)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertContains(response, "q=Rice&amp;status=active&amp;stock=out")
        self.assertContains(response, "aria-current=\"page\"")

    def test_product_history_has_reason_actor_and_ledger_balances(self):
        product = self.product()
        record_stock_adjustment(business=self.business, actor=self.owner, product=product, quantity_change=-2, reason="damage", notes="Broken pack")
        response = self.client.get(reverse("product_detail", args=[product.pk]))
        rows = response.context["movements"]
        self.assertEqual([row.balance for row in rows], [8, 10])
        self.assertContains(response, "interface@example.com")
        self.assertContains(response, "Balance after")
        self.assertContains(response, "Broken pack")

    def test_timestamp_ties_and_old_history_links_keep_complete_balances(self):
        instant = datetime(2025, 8, 1, 12, tzinfo=datetime_timezone.utc)
        with patch("django.utils.timezone.now", return_value=instant):
            product = self.product(quantity=10)
            record_stock_adjustment(business=self.business, actor=self.owner, product=product, quantity_change=-2, reason="damage")
        detail = self.client.get(reverse("product_detail", args=[product.pk]))
        self.assertEqual([row.balance for row in detail.context["movements"]], [8, 10])
        self.assertIn("date_from=2025-08-01", detail.context["history_query"])
        report = self.client.get(reverse("reports_movements") + "?" + detail.context["history_query"])
        self.assertEqual([row.balance for row in report.context["report"].rows], [8, 10])
        dashboard = self.client.get(reverse("business_home"))
        history = self.client.get(dashboard.context["dashboard"]["movements_url"])
        self.assertEqual(len(history.context["report"].rows), 2)

    def test_adjustment_preview_explains_all_quantities_without_writing(self):
        product = self.product()
        before = StockMovement.objects.count()
        response = self.client.post(reverse("adjustment_create"), {"product": product.pk, "quantity_change": "-2", "reason": "damage", "notes": "Broken pack", "action": "preview"})
        self.assertContains(response, "Current Stock on Hand")
        self.assertContains(response, "Expected new balance")
        self.assertEqual(response.context["preview"], 8)
        self.assertEqual(StockMovement.objects.count(), before)
        product.refresh_from_db()
        self.assertEqual(product.stock_on_hand, 10)

    def test_malformed_optional_ids_do_not_crash_or_select_a_product(self):
        product = self.product()
        for selector in ("²", "9" * 100, "wrong", "-1"):
            detail = self.client.get(reverse("product_detail", args=[product.pk]), {"movement": selector})
            self.assertEqual(detail.status_code, 200)
            form = self.client.get(reverse("adjustment_create"), {"product": selector})
            self.assertEqual(form.status_code, 200)
            self.assertIsNone(form.context["current_stock"])

    def test_new_document_forms_render_without_saved_parent_and_use_iso_dates(self):
        self.product()
        for route, field in (("purchase_create", "purchase_date"), ("sale_create", "sale_date")):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'id="document-total">0.00</output>')
            self.assertContains(response, "Remove this line")
            self.assertEqual(response.context["form"].fields[field].widget.format, "%Y-%m-%d")

    def test_filtered_history_keeps_balance_from_prior_movements(self):
        product = self.product(quantity=10)
        record_stock_adjustment(business=self.business, actor=self.owner, product=product, quantity_change=-2, reason="damage")
        from sales.models import Sale, SaleLine
        from sales.services import complete_sale, void_sale
        from django.utils import timezone
        sale = Sale.objects.create(business=self.business, creator=self.owner, sale_date=timezone.localdate())
        SaleLine.objects.create(sale=sale, product=product, quantity=3, unit_price=Decimal("12"))
        complete_sale(business=self.business, actor=self.owner, sale=sale)
        void_sale(business=self.business, actor=self.owner, sale=sale)
        response = self.client.get(reverse("reports_movements"), {"kind": "reversal"})
        row, = response.context["report"].rows
        self.assertEqual(row.balance, 8)
        self.assertEqual(row.movement.quantity_change, 3)
        self.assertContains(response, f"Original movement #{row.movement.reversal_of_id}")
        for index in range(26):
            record_stock_adjustment(business=self.business, actor=self.owner, product=product, quantity_change=1, reason="found")
        target = self.client.get(row.original_url.split("#")[0])
        self.assertEqual(target.context["page_obj"].number, 2)
        self.assertContains(target, f'id="movement-{row.movement.reversal_of_id}"')

    def test_demo_and_staff_have_honest_actions(self):
        product = self.product()
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        response = self.client.get(reverse("product_detail", args=[product.pk]))
        self.assertContains(response, "Read-only demo")
        self.assertNotContains(response, reverse("product_deactivate", args=[product.pk]))
        membership = Membership.objects.get(user=self.owner)
        membership.role = Membership.Role.STAFF
        membership.save(update_fields=["role"])
        response = self.client.get(reverse("product_list"))
        self.assertNotContains(response, reverse("staff_member_list"))
        self.assertNotContains(response, reverse("business_settings"))

    def test_dashboard_shows_scoped_stock_decisions_and_recent_movements(self):
        product = self.product("Low Rice", 2)
        other_business = Business.objects.create(name="Foreign Shop")
        other_owner = get_user_model().objects.create_user(email="foreign@example.com", password="password")
        Membership.objects.create(user=other_owner, business=other_business, role=Membership.Role.OWNER)
        create_product(business=other_business, actor=other_owner, details=ProductCreation(name="Hidden", sku="", description="", selling_price=Decimal("1"), unit_cost=Decimal("1"), opening_quantity=1, low_stock_threshold=3))
        response = self.client.get(reverse("business_home"))
        self.assertContains(response, "Needs attention")
        self.assertEqual([row.movement.product_id for row in response.context["dashboard"]["recent_movements"]], [product.pk])
        self.assertNotContains(response, "Hidden")

    def test_demo_document_screens_do_not_offer_writes(self):
        from purchases.models import Purchase
        from sales.models import Sale
        from expenses.models import Expense
        from django.utils import timezone

        purchase = Purchase.objects.create(business=self.business, creator=self.owner, purchase_date=timezone.localdate())
        sale = Sale.objects.create(business=self.business, creator=self.owner, sale_date=timezone.localdate())
        expense = Expense.objects.create(business=self.business, actor=self.owner, date=timezone.localdate(), category="other", description="Delivery", amount=Decimal("20"))
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        for route in ("purchase_list", "sale_list", "expense_list"):
            response = self.client.get(reverse(route))
            self.assertNotContains(response, reverse(route.replace("_list", "_create")))
        for route, record in (("purchase_detail", purchase), ("sale_detail", sale), ("expense_detail", expense)):
            response = self.client.get(reverse(route, args=[record.pk]))
            self.assertContains(response, "Read-only demo")
            self.assertNotContains(response, "Complete Purchase")
            self.assertNotContains(response, "Complete Sale")
            self.assertNotContains(response, "Void Expense")

    def test_document_forms_keep_native_add_line_and_server_totals(self):
        self.product()
        for route in ("purchase_create", "sale_create"):
            response = self.client.get(reverse(route))
            self.assertContains(response, 'name="add_line"')
            self.assertContains(response, 'data-line-template')
            self.assertContains(response, "Calculated when you save")
            self.assertNotContains(response, "toFixed")

    def test_invalid_expense_has_linked_error_summary_and_preserves_input(self):
        response = self.client.post(reverse("expense_create"), {"date": "2026-10-13", "category": "other", "description": "Delivery", "amount": "-5", "notes": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="error-summary"')
        self.assertContains(response, 'href="#id_amount"')
        self.assertContains(response, 'id="id_amount_error"')
        self.assertContains(response, "Delivery")

    def test_expense_correction_preserves_date_in_native_date_input(self):
        from datetime import date
        from expenses.models import Expense

        expense = Expense.objects.create(business=self.business, actor=self.owner, date=date(2026, 9, 12), category="transport", description="Delivery", amount=Decimal("20"))
        response = self.client.get(reverse("expense_correct", args=[expense.pk]))
        self.assertContains(response, 'type="date" name="date" value="2026-09-12"')

    def test_void_confirmation_pages_have_valid_titles_and_closed_sections(self):
        from html.parser import HTMLParser
        from purchases.models import Purchase, PurchaseLine
        from purchases.services import complete_purchase
        from sales.models import Sale, SaleLine
        from sales.services import complete_sale
        from django.utils import timezone

        class PageStructure(HTMLParser):
            def __init__(self):
                super().__init__()
                self.sections = 0
                self.in_title = False
                self.title = ""

            def handle_starttag(self, tag, attrs):
                if tag == "section":
                    self.sections += 1
                if tag == "title":
                    self.in_title = True

            def handle_endtag(self, tag):
                if tag == "section":
                    self.sections -= 1
                if tag == "title":
                    self.in_title = False

            def handle_data(self, data):
                if self.in_title:
                    self.title += data

        product = self.product()
        purchase = Purchase.objects.create(business=self.business, creator=self.owner, purchase_date=timezone.localdate())
        PurchaseLine.objects.create(purchase=purchase, product=product, quantity=1, unit_cost=Decimal("8"))
        complete_purchase(business=self.business, actor=self.owner, purchase=purchase)
        sale = Sale.objects.create(business=self.business, creator=self.owner, sale_date=timezone.localdate())
        SaleLine.objects.create(sale=sale, product=product, quantity=1, unit_price=Decimal("12"))
        complete_sale(business=self.business, actor=self.owner, sale=sale)
        for route, record, label in (("purchase_void", purchase, "Purchase"), ("sale_void", sale, "Sale")):
            response = self.client.get(reverse(route, args=[record.pk]))
            parser = PageStructure()
            parser.feed(response.content.decode())
            self.assertEqual(parser.title.strip(), f"Void {label} #{record.pk} | ShelfSum")
            self.assertEqual(parser.sections, 0)

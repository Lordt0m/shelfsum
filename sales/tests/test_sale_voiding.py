from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from catalogue.models import Product
from inventory.models import StockMovement
from inventory.models import StockAdjustment
from inventory.services import record_stock_adjustment
from sales.models import Sale, SaleLine
from sales.services import complete_sale, void_sale


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SaleVoidingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="password")
        self.staff = User.objects.create_user(email="staff@example.com", password="password")
        self.business = Business.objects.create(name="Corner Shop")
        Membership.objects.create(user=self.owner, business=self.business, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.staff, business=self.business, role=Membership.Role.STAFF)
        self.product = Product.objects.create(business=self.business, name="Rice", sku="RICE", stock_on_hand=10, unit_cost=Decimal("4.00"))

    def make_completed(self, quantity=3):
        sale = Sale.objects.create(business=self.business, creator=self.owner, sale_date=date(2026, 9, 9))
        SaleLine.objects.create(sale=sale, product=self.product, quantity=quantity, unit_price=Decimal("10.00"))
        complete_sale(business=self.business, actor=self.owner, sale=sale)
        return sale

    def test_void_sale_restores_each_movement_and_preserves_snapshot(self):
        sale = self.make_completed()
        original = StockMovement.objects.get(sale_line__sale=sale)
        snapshot = sale.lines.get().cost_snapshot
        void_sale(business=self.business, actor=self.staff, sale=sale)
        sale.refresh_from_db(); self.product.refresh_from_db()
        reversal = StockMovement.objects.get(reversal_of=original)
        self.assertEqual(sale.status, Sale.Status.VOIDED)
        self.assertEqual(reversal.quantity_change, -original.quantity_change)
        self.assertEqual(self.product.stock_on_hand, 10)
        self.assertEqual(sale.lines.get().cost_snapshot, snapshot)
        self.assertEqual(AuditEvent.objects.filter(action="sale.voided").count(), 1)

    def test_void_sale_replay_and_failure_are_atomic(self):
        sale = self.make_completed()
        with patch("sales.services.StockMovement.objects.create", side_effect=RuntimeError("movement")):
            with self.assertRaisesRegex(RuntimeError, "movement"):
                void_sale(business=self.business, actor=self.owner, sale=sale)
        sale.refresh_from_db(); self.product.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.COMPLETED); self.assertEqual(self.product.stock_on_hand, 7)
        self.assertEqual(StockMovement.objects.filter(kind=StockMovement.Kind.REVERSAL).count(), 0)
        void_sale(business=self.business, actor=self.owner, sale=sale)
        with self.assertRaisesRegex(ValidationError, "already been voided"):
            void_sale(business=self.business, actor=self.owner, sale=sale)

    def test_void_sale_rolls_back_status_movement_stock_and_audit_failures(self):
        seams = (
            ("sales.services.Sale.save", "status"),
            ("sales.services.StockMovement.objects.create", "movement"),
            ("sales.services.Product.save", "stock"),
            ("sales.services.record_audit_event", "audit"),
        )
        for target, label in seams:
            with self.subTest(seam=label):
                sale = self.make_completed(quantity=1)
                self.product.refresh_from_db()
                stock_before = self.product.stock_on_hand
                with patch(target, side_effect=RuntimeError(label)):
                    with self.assertRaisesRegex(RuntimeError, label):
                        void_sale(business=self.business, actor=self.owner, sale=sale)
                sale.refresh_from_db()
                self.product.refresh_from_db()
                self.assertEqual(sale.status, Sale.Status.COMPLETED)
                self.assertEqual(self.product.stock_on_hand, stock_before)
                self.assertFalse(
                    StockMovement.objects.filter(
                        sale_line__sale=sale, kind=StockMovement.Kind.REVERSAL
                    ).exists()
                )

    def test_void_sale_denies_demo_and_cross_business(self):
        sale = self.make_completed()
        self.business.is_demo = True; self.business.save(update_fields=["is_demo"])
        with self.assertRaises(PermissionDenied):
            void_sale(business=self.business, actor=self.owner, sale=sale)
        other = Business.objects.create(name="Other")
        other_owner = get_user_model().objects.create_user(email="other@example.com", password="password")
        Membership.objects.create(user=other_owner, business=other, role=Membership.Role.OWNER)
        with self.assertRaises(ValidationError):
            void_sale(business=other, actor=other_owner, sale=sale)

    def test_confirmation_page_exposes_restore_effect_and_post_action(self):
        sale = self.make_completed()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("sale_void", args=[sale.pk]))
        self.assertContains(response, "restores these quantities")
        self.assertContains(response, "Confirm void Sale")
        self.assertEqual(self.client.post(reverse("sale_void", args=[sale.pk])).status_code, 302)

    def test_reversal_rejects_reversal_of_reversal_and_adjustment_origins(self):
        sale = self.make_completed()
        original = StockMovement.objects.get(sale_line__sale=sale)
        void_sale(business=self.business, actor=self.owner, sale=sale)
        reversal = StockMovement.objects.get(reversal_of=original)
        adjustment = record_stock_adjustment(
            business=self.business,
            actor=self.owner,
            product=self.product,
            quantity_change=1,
            reason=StockAdjustment.Reason.FOUND,
        )
        adjustment_movement = StockMovement.objects.get(stock_adjustment=adjustment)

        for origin in (reversal, adjustment_movement):
            with self.assertRaises(ValidationError):
                StockMovement.objects.create(
                    business=self.business,
                    product=self.product,
                    quantity_change=-origin.quantity_change,
                    kind=StockMovement.Kind.REVERSAL,
                    reversal_of=origin,
                    actor=self.owner,
                )
        self.product.refresh_from_db()
        self.assertEqual(
            self.product.stock_on_hand,
            10
            + sum(
                StockMovement.objects.filter(product=self.product).values_list(
                    "quantity_change", flat=True
                )
            ),
        )

    def test_void_route_requires_a_real_csrf_token_and_applies_exact_stock_effect(self):
        sale = self.make_completed(quantity=3)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        url = reverse("sale_void", args=[sale.pk])
        csrf_client.get(url)
        self.assertEqual(csrf_client.post(url).status_code, 403)
        response = csrf_client.post(
            url, HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value
        )
        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.VOIDED)
        self.assertEqual(self.product.stock_on_hand, 10)
        self.assertEqual(
            csrf_client.post(
                url, HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value
            ).status_code,
            400,
        )

    def test_void_route_scopes_ids_and_denies_inactive_members(self):
        sale = self.make_completed()
        other = Business.objects.create(name="Other")
        hidden = Sale.objects.create(
            business=other, creator=self.owner, sale_date=date(2026, 9, 9)
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.post(reverse("sale_void", args=[hidden.pk])).status_code,
            404,
        )
        membership = Membership.objects.get(user=self.staff, business=self.business)
        membership.is_active = False
        membership.save(update_fields=["is_active"])
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.post(reverse("sale_void", args=[sale.pk])).status_code,
            403,
        )
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.COMPLETED)

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
from purchases.models import Purchase, PurchaseLine
from purchases.services import complete_purchase, void_purchase


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PurchaseVoidingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="password")
        self.staff = User.objects.create_user(email="staff@example.com", password="password")
        self.business = Business.objects.create(name="Corner Shop")
        Membership.objects.create(user=self.owner, business=self.business, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.staff, business=self.business, role=Membership.Role.STAFF)
        self.product = Product.objects.create(business=self.business, name="Rice", sku="RICE", unit_cost=Decimal("4.00"))

    def make_completed(self, quantity=3):
        purchase = Purchase.objects.create(business=self.business, creator=self.owner, purchase_date=date(2026, 9, 9))
        PurchaseLine.objects.create(purchase=purchase, product=self.product, quantity=quantity, unit_cost=Decimal("7.50"))
        complete_purchase(business=self.business, actor=self.owner, purchase=purchase)
        return purchase

    def test_void_purchase_reverses_each_movement_without_changing_cost(self):
        purchase = self.make_completed()
        original = StockMovement.objects.get(purchase_line__purchase=purchase)
        void_purchase(business=self.business, actor=self.staff, purchase=purchase)
        purchase.refresh_from_db(); self.product.refresh_from_db()
        reversal = StockMovement.objects.get(reversal_of=original)
        self.assertEqual(purchase.status, Purchase.Status.VOIDED)
        self.assertEqual(reversal.quantity_change, -original.quantity_change)
        self.assertEqual(reversal.kind, StockMovement.Kind.REVERSAL)
        self.assertEqual(self.product.stock_on_hand, 0)
        self.assertEqual(self.product.unit_cost, Decimal("7.50"))
        self.assertEqual(AuditEvent.objects.filter(action="purchase.voided").count(), 1)

    def test_void_purchase_rejects_insufficient_stock_and_replay(self):
        purchase = self.make_completed(quantity=3)
        self.product.stock_on_hand = 2; self.product.save(update_fields=["stock_on_hand"])
        with self.assertRaisesRegex(ValidationError, "negative"):
            void_purchase(business=self.business, actor=self.owner, purchase=purchase)
        self.assertEqual(StockMovement.objects.filter(kind=StockMovement.Kind.REVERSAL).count(), 0)
        self.product.stock_on_hand = 3; self.product.save(update_fields=["stock_on_hand"])
        void_purchase(business=self.business, actor=self.owner, purchase=purchase)
        with self.assertRaisesRegex(ValidationError, "already been voided"):
            void_purchase(business=self.business, actor=self.owner, purchase=purchase)

    def test_void_purchase_rolls_back_downstream_failure_and_denies_demo(self):
        purchase = self.make_completed()
        with patch("purchases.services.record_audit_event", side_effect=RuntimeError("audit")):
            with self.assertRaisesRegex(RuntimeError, "audit"):
                void_purchase(business=self.business, actor=self.owner, purchase=purchase)
        purchase.refresh_from_db(); self.product.refresh_from_db()
        self.assertEqual(purchase.status, Purchase.Status.COMPLETED)
        self.assertEqual(self.product.stock_on_hand, 3)
        self.assertEqual(StockMovement.objects.filter(kind=StockMovement.Kind.REVERSAL).count(), 0)
        self.business.is_demo = True; self.business.save(update_fields=["is_demo"])
        with self.assertRaises(PermissionDenied):
            void_purchase(business=self.business, actor=self.owner, purchase=purchase)

    def test_void_purchase_rolls_back_status_movement_stock_and_audit_failures(self):
        seams = (
            ("purchases.services.Purchase.save", "status"),
            ("purchases.services.StockMovement.objects.create", "movement"),
            ("purchases.services.Product.save", "stock"),
            ("purchases.services.record_audit_event", "audit"),
        )
        for target, label in seams:
            with self.subTest(seam=label):
                purchase = self.make_completed()
                self.product.refresh_from_db()
                stock_before = self.product.stock_on_hand
                with patch(target, side_effect=RuntimeError(label)):
                    with self.assertRaisesRegex(RuntimeError, label):
                        void_purchase(
                            business=self.business, actor=self.owner, purchase=purchase
                        )
                purchase.refresh_from_db()
                self.product.refresh_from_db()
                self.assertEqual(purchase.status, Purchase.Status.COMPLETED)
                self.assertEqual(self.product.stock_on_hand, stock_before)
                self.assertFalse(
                    StockMovement.objects.filter(
                        purchase_line__purchase=purchase,
                        kind=StockMovement.Kind.REVERSAL,
                    ).exists()
                )

    def test_confirmation_is_get_and_void_is_post_only_with_csrf(self):
        purchase = self.make_completed()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("purchase_void", args=[purchase.pk]))
        self.assertContains(response, "removes these quantities")
        self.assertContains(response, "Confirm void Purchase")
        self.assertEqual(self.client.post(reverse("purchase_void", args=[purchase.pk])).status_code, 302)
        purchase.refresh_from_db(); self.assertEqual(purchase.status, Purchase.Status.VOIDED)

    def test_reversal_provenance_rejects_direct_and_bulk_forgery(self):
        purchase = self.make_completed()
        original = StockMovement.objects.get(purchase_line__purchase=purchase)

        # A caller-supplied owner cache cannot make a completed Purchase look
        # voided: reversal validation reloads the persisted origin chain.
        forged_purchase = Purchase(pk=purchase.pk, status=Purchase.Status.VOIDED)
        forged_line = PurchaseLine(
            pk=original.purchase_line_id,
            purchase=forged_purchase,
            product=self.product,
            quantity=original.quantity_change,
            unit_cost=Decimal("7.50"),
        )
        original._state.fields_cache["purchase_line"] = forged_line
        with self.assertRaisesRegex(ValidationError, "voided Purchase"):
            StockMovement(
                business=self.business,
                product=self.product,
                quantity_change=-original.quantity_change,
                kind=StockMovement.Kind.REVERSAL,
                reversal_of=original,
                actor=self.owner,
            ).full_clean()

        # This narrow setup mirrors the persisted state visible inside the
        # void service before it creates reversals, without consuming origin.
        purchase.status = Purchase.Status.VOIDED
        purchase._void_authorized = True
        try:
            purchase.save(update_fields=["status", "updated_at"])
        finally:
            del purchase._void_authorized
        other_business = Business.objects.create(name="Other")
        other_product = Product.objects.create(
            business=self.business, name="Other", sku="OTHER"
        )
        invalid = (
            StockMovement(
                business=other_business,
                product=self.product,
                quantity_change=-original.quantity_change,
                kind=StockMovement.Kind.REVERSAL,
                reversal_of=original,
                actor=self.owner,
            ),
            StockMovement(
                business=self.business,
                product=other_product,
                quantity_change=-original.quantity_change,
                kind=StockMovement.Kind.REVERSAL,
                reversal_of=original,
                actor=self.owner,
            ),
            StockMovement(
                business=self.business,
                product=self.product,
                quantity_change=-(original.quantity_change + 1),
                kind=StockMovement.Kind.REVERSAL,
                reversal_of=original,
                actor=self.owner,
            ),
        )
        for movement in invalid:
            with self.assertRaises(ValidationError):
                movement.full_clean()
        with self.assertRaisesRegex(ValidationError, "quantity must negate"):
            StockMovement.objects.bulk_create(
                StockMovement(
                    business=self.business,
                    product=self.product,
                    quantity_change=-(original.quantity_change + 1),
                    kind=StockMovement.Kind.REVERSAL,
                    reversal_of=original,
                    actor=self.owner,
                )
                for _ in range(1)
            )
        self.assertFalse(StockMovement.objects.filter(kind=StockMovement.Kind.REVERSAL).exists())

    def test_void_route_requires_a_real_csrf_token_and_applies_exact_stock_effect(self):
        purchase = self.make_completed(quantity=3)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        url = reverse("purchase_void", args=[purchase.pk])
        confirmation = csrf_client.get(url)
        self.assertEqual(csrf_client.post(url).status_code, 403)
        response = csrf_client.post(
            url, HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value
        )
        self.assertEqual(response.status_code, 302)
        purchase.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(purchase.status, Purchase.Status.VOIDED)
        self.assertEqual(self.product.stock_on_hand, 0)
        self.assertEqual(
            csrf_client.post(
                url, HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value
            ).status_code,
            400,
        )

    def test_void_route_scopes_ids_and_denies_inactive_members(self):
        purchase = self.make_completed()
        other = Business.objects.create(name="Other")
        hidden = Purchase.objects.create(
            business=other, creator=self.owner, purchase_date=date(2026, 9, 9)
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.post(reverse("purchase_void", args=[hidden.pk])).status_code,
            404,
        )
        membership = Membership.objects.get(user=self.staff, business=self.business)
        membership.is_active = False
        membership.save(update_fields=["is_active"])
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.post(reverse("purchase_void", args=[purchase.pk])).status_code,
            403,
        )
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, Purchase.Status.COMPLETED)

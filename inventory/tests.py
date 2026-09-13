from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from businesses.rules import DemoBusinessReadOnly
from catalogue.models import Product
from catalogue.services import ProductCreation
from catalogue.services import create_product
from .models import StockAdjustment, StockMovement
from .services import record_stock_adjustment


class StockAdjustmentBehaviorTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="test-pass")
        self.staff = User.objects.create_user(email="staff@example.com", password="test-pass")
        self.business = Business.objects.create(name="Shop")
        Membership.objects.create(user=self.owner, business=self.business, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.staff, business=self.business, role=Membership.Role.STAFF)
        self.product = create_product(
            business=self.business,
            actor=self.owner,
            details=ProductCreation(
                "Tea", "", "", Decimal("2"), Decimal("1"), 10, 0
            ),
        )
        self.product.refresh_from_db()

    def data(self, **overrides):
        values = {"product": self.product.pk, "quantity_change": "-2", "reason": "damage", "notes": "Spoilt"}
        values.update(overrides)
        return values

    def test_staff_can_preview_without_writing_then_record_adjustment(self):
        self.client.force_login(self.staff)
        url = reverse("adjustment_create")
        response = self.client.post(url, self.data(action="preview"))
        self.assertContains(response, "Resulting Stock on Hand: <strong>8</strong>", html=True)
        self.assertEqual(StockAdjustment.objects.count(), 1)
        response = self.client.post(url, self.data(action="record"))
        adjustment = StockAdjustment.objects.get(reason=StockAdjustment.Reason.DAMAGE)
        self.assertRedirects(response, reverse("adjustment_detail", args=[adjustment.pk]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_on_hand, 8)
        self.assertEqual(
            StockMovement.objects.get(stock_adjustment=adjustment).quantity_change, -2
        )
        self.assertEqual(
            AuditEvent.objects.get(action="stock.adjusted").action, "stock.adjusted"
        )

    def test_service_rejects_manual_opening_and_invalid_quantity(self):
        with self.assertRaises(ValidationError):
            record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=1, reason=StockAdjustment.Reason.OPENING)
        for quantity in (0, True, Decimal("1.5")):
            with self.assertRaises(ValidationError):
                record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=quantity, reason=StockAdjustment.Reason.FOUND)

    def test_public_service_cannot_enable_opening_stock(self):
        with self.assertRaises(TypeError):
            record_stock_adjustment(
                business=self.business,
                actor=self.owner,
                product=self.product,
                quantity_change=1,
                reason=StockAdjustment.Reason.OPENING,
                allow_opening=True,
            )

    def test_service_records_every_manual_reason(self):
        for reason, quantity in (("damage", -1), ("missing", -1), ("found", 1), ("correction", 1)):
            with self.subTest(reason=reason):
                adjustment = record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=quantity, reason=reason)
                self.assertEqual(adjustment.reason, reason)

    def test_movement_or_audit_database_failure_rolls_back_adjustment_and_stock(self):
        for target in ("inventory.services.StockMovement.objects.create", "inventory.services.record_audit_event"):
            with self.subTest(target=target), patch(target, side_effect=IntegrityError("database write failed")):
                before_adjustments = StockAdjustment.objects.count()
                before_movements = StockMovement.objects.count()
                with self.assertRaises(IntegrityError):
                    record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=1, reason="found")
                self.product.refresh_from_db()
                self.assertEqual(self.product.stock_on_hand, 10)
                self.assertEqual(StockAdjustment.objects.count(), before_adjustments)
                self.assertEqual(StockMovement.objects.count(), before_movements)

    def test_list_detail_and_demo_write_are_business_scoped(self):
        other_business = Business.objects.create(name="Other shop")
        other_product = Product.objects.create(business=other_business, name="Other tea")
        other_adjustment = StockAdjustment.objects.create(business=other_business, product=other_product, quantity_change=1, reason="found", actor=self.owner)
        adjustment = record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=-1, reason="damage")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("adjustment_list"), {"reason": "damage", "date_from": "2026-02-30"})
        self.assertContains(response, "Enter valid calendar dates.")
        self.assertContains(response, adjustment.product.name)
        self.assertNotContains(response, other_product.name)
        self.assertEqual(self.client.get(reverse("adjustment_detail", args=[other_adjustment.pk])).status_code, 404)
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        self.assertEqual(self.client.post(reverse("adjustment_create"), self.data(action="record")).status_code, 403)

    def test_request_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)
        self.assertEqual(csrf_client.post(reverse("adjustment_create"), self.data(action="record")).status_code, 403)

    def test_service_rechecks_locked_product_stock_and_activity_and_rejects_demo(self):
        Product.objects.filter(pk=self.product.pk).update(stock_on_hand=0)
        with self.assertRaises(ValidationError):
            record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=-1, reason="missing")
        Product.objects.filter(pk=self.product.pk).update(stock_on_hand=10, is_active=False)
        with self.assertRaises(ValidationError):
            record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=1, reason="found")
        Product.objects.filter(pk=self.product.pk).update(is_active=True)
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])
        with self.assertRaises(DemoBusinessReadOnly):
            record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=1, reason="found")

    def test_adjustment_ledger_reconciles_stock_on_hand(self):
        record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=-3, reason="damage")
        record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=2, reason="found")
        self.product.refresh_from_db()
        self.assertEqual(
            self.product.stock_on_hand,
            sum(StockMovement.objects.filter(product=self.product).values_list("quantity_change", flat=True)),
        )

    def test_product_creation_opening_keeps_single_product_audit(self):
        product = create_product(business=self.business, actor=self.owner, details=ProductCreation("Coffee", "", "", Decimal("2"), Decimal("1"), 4, 0))
        self.assertEqual(StockAdjustment.objects.filter(product=product).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(business=self.business, object_identifier=str(product.pk)).count(), 1)
        self.assertEqual(AuditEvent.objects.get(object_identifier=str(product.pk)).action, "product.created")

    def test_negative_adjustment_is_rejected_without_writes(self):
        adjustment_count = StockAdjustment.objects.count()
        movement_count = StockMovement.objects.count()
        with self.assertRaises(ValidationError):
            record_stock_adjustment(business=self.business, actor=self.owner, product=self.product, quantity_change=-11, reason=StockAdjustment.Reason.MISSING)
        self.assertEqual(StockAdjustment.objects.count(), adjustment_count)
        self.assertEqual(StockMovement.objects.count(), movement_count)

    def test_adjustment_persistence_rejects_zero_fractional_and_cross_business_values(self):
        other_business = Business.objects.create(name="Other shop")
        other_product = Product.objects.create(business=other_business, name="Other tea")
        invalid_adjustments = (
            {"quantity_change": 0},
            {"quantity_change": Decimal("1.5")},
            {"business": other_business, "product": self.product},
        )
        for overrides in invalid_adjustments:
            values = {
                "business": self.business,
                "product": self.product,
                "quantity_change": 1,
                "reason": StockAdjustment.Reason.FOUND,
                "actor": self.owner,
            }
            values.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                StockAdjustment.objects.create(**values)
        with self.assertRaises(ValidationError):
            StockAdjustment.objects.bulk_create(
                (
                    StockAdjustment(
                        business=self.business,
                        product=other_product,
                        quantity_change=1,
                        reason=StockAdjustment.Reason.FOUND,
                        actor=self.owner,
                    )
                    for _ in range(1)
                )
            )

    def test_adjustment_movement_uses_persisted_adjustment_values_not_a_relation_cache(self):
        adjustment = record_stock_adjustment(
            business=self.business,
            actor=self.owner,
            product=self.product,
            quantity_change=1,
            reason=StockAdjustment.Reason.FOUND,
        )
        forged = StockAdjustment(
            pk=adjustment.pk,
            business=self.business,
            product=self.product,
            quantity_change=99,
            reason=StockAdjustment.Reason.FOUND,
            actor=self.owner,
        )
        movement = StockMovement(
            business=self.business,
            product=self.product,
            quantity_change=99,
            kind=StockMovement.Kind.ADJUSTMENT,
            stock_adjustment_id=adjustment.pk,
            actor=self.owner,
        )
        movement._state.fields_cache["stock_adjustment"] = forged
        with self.assertRaises(ValidationError):
            movement.clean()

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from catalogue.models import Product
from catalogue.services import ProductCreation, create_product
from inventory.models import StockAdjustment, StockMovement


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ProductCreationServiceTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            email="owner@example.com", password="password"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(
            user=self.actor, business=self.business, role=Membership.Role.OWNER
        )

    def details(self, **overrides):
        values = {
            "name": "Golden Penny Spaghetti",
            "sku": "gp-spag-500",
            "description": "500 g pack",
            "selling_price": Decimal("1250.00"),
            "unit_cost": Decimal("1080.50"),
            "opening_quantity": 12,
            "low_stock_threshold": 3,
        }
        values.update(overrides)
        return ProductCreation(**values)

    def test_opening_stock_creates_a_complete_trace_atomically(self):
        product = create_product(
            business=self.business, actor=self.actor, details=self.details()
        )

        product.refresh_from_db()
        adjustment = StockAdjustment.objects.get(product=product)
        movement = StockMovement.objects.get(product=product)
        event = AuditEvent.objects.get(business=self.business)
        self.assertEqual(product.stock_on_hand, 12)
        self.assertEqual(adjustment.quantity_change, 12)
        self.assertEqual(adjustment.reason, StockAdjustment.Reason.OPENING)
        self.assertEqual(movement.quantity_change, 12)
        self.assertEqual(movement.stock_adjustment, adjustment)
        self.assertEqual(event.object_identifier, str(product.pk))

    def test_zero_opening_stock_creates_product_and_audit_without_zero_movements(self):
        product = create_product(
            business=self.business,
            actor=self.actor,
            details=self.details(opening_quantity=0),
        )

        self.assertEqual(product.stock_on_hand, 0)
        self.assertFalse(StockAdjustment.objects.exists())
        self.assertFalse(StockMovement.objects.exists())
        self.assertTrue(AuditEvent.objects.filter(object_identifier=str(product.pk)).exists())

    def test_failure_during_stock_trace_rolls_back_the_product(self):
        with patch(
            "catalogue.services.record_stock_adjustment",
            side_effect=RuntimeError("simulated ledger failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "ledger failure"):
                create_product(
                    business=self.business, actor=self.actor, details=self.details()
                )

        self.assertFalse(Product.objects.exists())
        self.assertFalse(StockAdjustment.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_identifiers_are_reusable_by_another_business(self):
        first = create_product(
            business=self.business, actor=self.actor, details=self.details()
        )
        other_actor = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        other_business = Business.objects.create(name="Other Shop")
        Membership.objects.create(
            user=other_actor,
            business=other_business,
            role=Membership.Role.OWNER,
        )

        second = create_product(
            business=other_business, actor=other_actor, details=self.details()
        )

        self.assertEqual(first.name, second.name)
        self.assertEqual(first.sku, second.sku)
        self.assertNotEqual(first.business, second.business)

    def test_service_rejects_writes_to_demo_business(self):
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])

        with self.assertRaises(PermissionDenied):
            create_product(
                business=self.business, actor=self.actor, details=self.details()
            )

        self.assertFalse(Product.objects.exists())

    def test_stock_movement_cannot_be_changed_or_deleted(self):
        product = create_product(
            business=self.business, actor=self.actor, details=self.details()
        )
        movement = StockMovement.objects.get(product=product)

        movement.quantity_change = 99
        with self.assertRaisesRegex(TypeError, "immutable"):
            movement.save()
        with self.assertRaisesRegex(TypeError, "immutable"):
            movement.delete()

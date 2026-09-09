from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from catalogue.models import Product
from catalogue.services import (
    ProductCreation,
    ProductUpdate,
    create_product,
    deactivate_product,
    update_product,
)
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

    def test_audit_failure_rolls_back_the_completed_stock_trace(self):
        with patch(
            "catalogue.services.record_audit_event",
            side_effect=RuntimeError("simulated audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "audit failure"):
                create_product(
                    business=self.business, actor=self.actor, details=self.details()
                )

        self.assertFalse(Product.objects.exists())
        self.assertFalse(StockAdjustment.objects.exists())
        self.assertFalse(StockMovement.objects.exists())
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
        with self.assertRaisesRegex(TypeError, "immutable"):
            StockMovement.objects.filter(pk=movement.pk).update(quantity_change=99)
        movement.quantity_change = 99
        with self.assertRaisesRegex(TypeError, "immutable"):
            StockMovement.objects.bulk_update([movement], ["quantity_change"])
        with self.assertRaisesRegex(TypeError, "immutable"):
            StockMovement.objects.filter(pk=movement.pk).delete()

    def test_adjustment_and_audit_event_are_immutable(self):
        product = create_product(
            business=self.business, actor=self.actor, details=self.details()
        )
        adjustment = StockAdjustment.objects.get(product=product)
        event = AuditEvent.objects.get(business=self.business)

        adjustment.quantity_change = 99
        with self.assertRaisesRegex(TypeError, "immutable"):
            adjustment.save()
        with self.assertRaisesRegex(TypeError, "immutable"):
            StockAdjustment.objects.filter(pk=adjustment.pk).update(quantity_change=99)
        with self.assertRaisesRegex(TypeError, "immutable"):
            StockAdjustment.objects.filter(pk=adjustment.pk).delete()
        with self.assertRaisesRegex(TypeError, "append-only"):
            AuditEvent.objects.filter(pk=event.pk).update(summary="rewritten")
        with self.assertRaisesRegex(TypeError, "append-only"):
            AuditEvent.objects.filter(pk=event.pk).delete()

    def test_maintenance_actions_record_audit_events(self):
        product = create_product(
            business=self.business, actor=self.actor, details=self.details()
        )
        update_product(
            business=self.business,
            actor=self.actor,
            product=product,
            details=ProductUpdate(
                name="Updated Pasta",
                sku=product.sku,
                description=product.description,
                selling_price=product.selling_price,
                unit_cost=product.unit_cost,
                low_stock_threshold=product.low_stock_threshold,
            ),
        )
        deactivate_product(
            business=self.business, actor=self.actor, product=product
        )

        events = list(AuditEvent.objects.filter(business=self.business))
        self.assertEqual(
            {event.action for event in events},
            {"product.created", "product.updated", "product.deactivated"},
        )
        self.assertTrue(all(event.actor == self.actor for event in events))

    def test_audit_failure_rolls_back_update_and_deactivation(self):
        product = create_product(
            business=self.business, actor=self.actor, details=self.details()
        )
        original_name = product.name
        with patch(
            "catalogue.services.record_audit_event",
            side_effect=RuntimeError("simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                update_product(
                    business=self.business,
                    actor=self.actor,
                    product=product,
                    details=ProductUpdate(
                        name="Should Roll Back",
                        sku=product.sku,
                        description=product.description,
                        selling_price=product.selling_price,
                        unit_cost=product.unit_cost,
                        low_stock_threshold=product.low_stock_threshold,
                    ),
                )
            with self.assertRaises(RuntimeError):
                deactivate_product(
                    business=self.business, actor=self.actor, product=product
                )

        product.refresh_from_db()
        self.assertEqual(product.name, original_name)
        self.assertTrue(product.is_active)

    def test_demo_business_rejects_maintenance_services_without_side_effects(self):
        product = create_product(
            business=self.business, actor=self.actor, details=self.details()
        )
        original_name = product.name
        initial_events = self.business.audit_events.count()
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])

        with self.assertRaises(PermissionDenied):
            update_product(
                business=self.business,
                actor=self.actor,
                product=product,
                details=ProductUpdate(
                    name="Forbidden Demo Change",
                    sku=product.sku,
                    description=product.description,
                    selling_price=product.selling_price,
                    unit_cost=product.unit_cost,
                    low_stock_threshold=product.low_stock_threshold,
                ),
            )
        with self.assertRaises(PermissionDenied):
            deactivate_product(
                business=self.business, actor=self.actor, product=product
            )

        product.refresh_from_db()
        self.assertEqual(product.name, original_name)
        self.assertTrue(product.is_active)
        self.assertEqual(self.business.audit_events.count(), initial_events)

    def test_maintenance_services_reject_a_product_from_another_business(self):
        other_business = Business.objects.create(name="Other Service Shop")
        other_product = Product.objects.create(
            business=other_business, name="Other Product"
        )
        initial_events = AuditEvent.objects.count()

        with self.assertRaisesRegex(ValidationError, "does not belong"):
            update_product(
                business=self.business,
                actor=self.actor,
                product=other_product,
                details=ProductUpdate(
                    name="Cross-Business Change",
                    sku=other_product.sku,
                    description=other_product.description,
                    selling_price=other_product.selling_price,
                    unit_cost=other_product.unit_cost,
                    low_stock_threshold=other_product.low_stock_threshold,
                ),
            )
        with self.assertRaisesRegex(ValidationError, "does not belong"):
            deactivate_product(
                business=self.business, actor=self.actor, product=other_product
            )

        other_product.refresh_from_db()
        self.assertEqual(other_product.name, "Other Product")
        self.assertTrue(other_product.is_active)
        self.assertEqual(AuditEvent.objects.count(), initial_events)

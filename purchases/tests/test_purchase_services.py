from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from catalogue.models import Product
from inventory.models import StockAdjustment, StockMovement
from inventory.services import record_stock_adjustment
from purchases.models import Purchase, PurchaseLine
from purchases.services import complete_purchase


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PurchaseCompletionServiceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com", password="password"
        )
        self.staff = get_user_model().objects.create_user(
            email="staff@example.com", password="password"
        )
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(
            user=self.owner, business=self.business, role=Membership.Role.OWNER
        )
        Membership.objects.create(
            user=self.staff, business=self.business, role=Membership.Role.STAFF
        )

    def product(self, **overrides):
        values = {"business": self.business, "name": "Golden Penny", "sku": "GP-1"}
        values.update(overrides)
        return Product.objects.create(**values)

    def draft(self, *lines, actor=None, **overrides):
        values = {
            "business": self.business,
            "creator": actor or self.owner,
            "purchase_date": date(2026, 9, 9),
        }
        values.update(overrides)
        purchase = Purchase.objects.create(**values)
        for product, quantity, unit_cost in lines:
            PurchaseLine.objects.create(
                purchase=purchase,
                product=product,
                quantity=quantity,
                unit_cost=Decimal(unit_cost),
            )
        return purchase

    def test_owner_and_staff_can_complete_valid_multi_line_drafts(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1")
        owner_purchase = self.draft(
            (first, 3, "101.25"), (second, 4, "202.50")
        )
        staff_purchase = self.draft((first, 2, "110.00"), actor=self.staff)

        complete_purchase(
            business=self.business, actor=self.owner, purchase=owner_purchase
        )
        complete_purchase(
            business=self.business, actor=self.staff, purchase=staff_purchase
        )

        first.refresh_from_db()
        second.refresh_from_db()
        owner_purchase.refresh_from_db()
        staff_purchase.refresh_from_db()
        self.assertEqual(owner_purchase.status, Purchase.Status.COMPLETED)
        self.assertEqual(staff_purchase.status, Purchase.Status.COMPLETED)
        self.assertEqual(first.stock_on_hand, 5)
        self.assertEqual(first.unit_cost, Decimal("110.00"))
        self.assertEqual(second.stock_on_hand, 4)
        self.assertEqual(second.unit_cost, Decimal("202.50"))
        self.assertEqual(owner_purchase.total, Decimal("1113.75"))
        self.assertEqual(staff_purchase.total, Decimal("220.00"))

    def test_completion_creates_one_purchase_movement_per_line_and_audit_event(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1")
        purchase = self.draft((first, 3, "101.25"), (second, 4, "202.50"))

        complete_purchase(business=self.business, actor=self.owner, purchase=purchase)

        movements = list(
            StockMovement.objects.filter(kind=StockMovement.Kind.PURCHASE).order_by(
                "purchase_line_id"
            )
        )
        lines = list(purchase.lines.order_by("pk"))
        self.assertEqual(len(movements), 2)
        self.assertEqual(
            {movement.purchase_line_id for movement in movements},
            {line.pk for line in lines},
        )
        self.assertTrue(all(movement.stock_adjustment_id is None for movement in movements))
        self.assertEqual(
            AuditEvent.objects.get(object_identifier=str(purchase.pk)).action,
            "purchase.completed",
        )

    def test_completion_locks_products_by_primary_key_in_deterministic_order(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1")
        purchase = self.draft((second, 1, "10.00"), (first, 1, "20.00"))

        with CaptureQueriesContext(connection) as queries:
            complete_purchase(business=self.business, actor=self.owner, purchase=purchase)

        product_lock_queries = [
            query["sql"]
            for query in queries.captured_queries
            if "catalogue_product" in query["sql"] and "ORDER BY" in query["sql"]
        ]
        self.assertTrue(product_lock_queries)
        self.assertTrue(any('ORDER BY "catalogue_product"."id" ASC' in query for query in product_lock_queries))

    def test_reconciliation_matches_stock_on_hand_to_purchase_movements(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1")
        purchase = self.draft((first, 3, "101.25"), (second, 4, "202.50"))

        complete_purchase(business=self.business, actor=self.owner, purchase=purchase)

        for product in (first, second):
            product.refresh_from_db()
            movement_total = sum(
                StockMovement.objects.filter(product=product).values_list(
                    "quantity_change", flat=True
                )
            )
            self.assertEqual(product.stock_on_hand, movement_total)

    def test_service_rejects_demo_inactive_actor_and_cross_business_purchase(self):
        product = self.product()
        purchase = self.draft((product, 1, "10.00"))
        self.business.is_demo = True
        self.business.save(update_fields=["is_demo"])

        with self.assertRaises(PermissionDenied):
            complete_purchase(business=self.business, actor=self.owner, purchase=purchase)
        self.assertEqual(StockMovement.objects.count(), 0)

        self.business.is_demo = False
        self.business.save(update_fields=["is_demo"])
        membership = Membership.objects.get(user=self.staff, business=self.business)
        membership.is_active = False
        membership.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            complete_purchase(business=self.business, actor=self.staff, purchase=purchase)

        other_business = Business.objects.create(name="Other Shop")
        other_owner = get_user_model().objects.create_user(
            email="other@example.com", password="password"
        )
        Membership.objects.create(
            user=other_owner, business=other_business, role=Membership.Role.OWNER
        )
        with self.assertRaises(ValidationError):
            complete_purchase(business=other_business, actor=other_owner, purchase=purchase)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_service_and_persistence_reject_invalid_product_lines(self):
        product = self.product()
        blank = self.draft()
        with self.assertRaisesRegex(ValidationError, "at least one line"):
            complete_purchase(business=self.business, actor=self.owner, purchase=blank)

        with self.assertRaisesRegex(ValidationError, "positive whole number"):
            self.draft((product, 0, "10.00"))

        product.is_active = False
        product.save(update_fields=["is_active"])
        inactive = self.draft((product, 1, "10.00"))
        with self.assertRaisesRegex(ValidationError, "active Product"):
            complete_purchase(business=self.business, actor=self.owner, purchase=inactive)

        other_business = Business.objects.create(name="Other Shop")
        other_product = Product.objects.create(
            business=other_business, name="Hidden", sku="HIDDEN-1"
        )
        with self.assertRaisesRegex(ValidationError, "must belong to this Business"):
            self.draft((other_product, 1, "10.00"))
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_duplicate_lines_are_rejected(self):
        product = self.product()
        purchase = self.draft((product, 1, "10.00"))

        with self.assertRaises(ValidationError):
            PurchaseLine.objects.create(
                purchase=purchase,
                product=product,
                quantity=2,
                unit_cost=Decimal("10.00"),
            )

    def test_purchase_line_persistence_rejects_cross_business_products(self):
        purchase = self.draft()
        other_business = Business.objects.create(name="Other Shop")
        other_product = Product.objects.create(
            business=other_business, name="Hidden", sku="HIDDEN-1"
        )

        with self.assertRaisesRegex(ValidationError, "must belong to this Business"):
            PurchaseLine.objects.create(
                purchase=purchase,
                product=other_product,
                quantity=1,
                unit_cost=Decimal("10.00"),
            )
        with self.assertRaisesRegex(ValidationError, "must belong to this Business"):
            PurchaseLine.objects.bulk_create(
                [
                    PurchaseLine(
                        purchase=purchase,
                        product=other_product,
                        quantity=1,
                        unit_cost=Decimal("10.00"),
                    )
                ]
            )

        valid_product = self.product(name="Valid", sku="VALID-1")
        line = PurchaseLine.objects.create(
            purchase=purchase,
            product=valid_product,
            quantity=1,
            unit_cost=Decimal("10.00"),
        )
        line.product = other_product
        with self.assertRaisesRegex(ValidationError, "must belong to this Business"):
            PurchaseLine.objects.bulk_update([line], ["product"])

        self.assertEqual(purchase.lines.count(), 1)
        self.assertEqual(purchase.lines.get().product, valid_product)

    def test_validated_bulk_create_accepts_generator_inputs(self):
        product = self.product()
        purchase = self.draft()

        created_lines = PurchaseLine.objects.bulk_create(
            (
                PurchaseLine(
                    purchase=purchase,
                    product=product,
                    quantity=2,
                    unit_cost=Decimal("10.00"),
                )
                for _ in range(1)
            )
        )

        adjustment = StockAdjustment.objects.create(
            business=self.business,
            product=product,
            quantity_change=2,
            reason=StockAdjustment.Reason.FOUND,
            actor=self.owner,
        )
        created_movements = StockMovement.objects.bulk_create(
            (
                StockMovement(
                    business=self.business,
                    product=product,
                    quantity_change=adjustment.quantity_change,
                    kind=StockMovement.Kind.ADJUSTMENT,
                    stock_adjustment=adjustment,
                    actor=self.owner,
                )
                for _ in range(1)
            )
        )

        self.assertEqual(len(created_lines), 1)
        self.assertEqual(purchase.lines.count(), 1)
        self.assertEqual(len(created_movements), 1)
        self.assertTrue(StockMovement.objects.filter(stock_adjustment=adjustment).exists())

    def test_repeated_completion_has_no_second_effect(self):
        product = self.product()
        purchase = self.draft((product, 2, "10.00"))
        complete_purchase(business=self.business, actor=self.owner, purchase=purchase)

        with self.assertRaisesRegex(ValidationError, "already been completed"):
            complete_purchase(business=self.business, actor=self.owner, purchase=purchase)

        product.refresh_from_db()
        self.assertEqual(product.stock_on_hand, 2)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="purchase.completed").count(), 1)

    def test_downstream_failures_roll_back_products_movements_status_and_audit(self):
        cases = (
            ("StockMovement.objects.create", "movement failure"),
            ("Product.save", "product failure"),
            ("Purchase.save", "status failure"),
            ("record_audit_event", "audit failure"),
        )
        for target, message in cases:
            with self.subTest(target=target):
                product = self.product(name=f"Product {target}", sku=f"SKU-{target}")
                purchase = self.draft((product, 2, "10.00"))
                with patch(f"purchases.services.{target}", side_effect=RuntimeError(message)):
                    with self.assertRaisesRegex(RuntimeError, message):
                        complete_purchase(
                            business=self.business, actor=self.owner, purchase=purchase
                        )
                product.refresh_from_db()
                purchase.refresh_from_db()
                self.assertEqual(product.stock_on_hand, 0)
                self.assertEqual(product.unit_cost, Decimal("0"))
                self.assertEqual(purchase.status, Purchase.Status.DRAFT)
                self.assertFalse(StockMovement.objects.filter(product=product).exists())
                self.assertFalse(
                    AuditEvent.objects.filter(object_identifier=str(purchase.pk)).exists()
                )

    def test_completed_purchase_and_lines_reject_instance_and_bulk_mutation(self):
        product = self.product()
        purchase = self.draft((product, 2, "10.00"))
        complete_purchase(business=self.business, actor=self.owner, purchase=purchase)
        line = purchase.lines.get()
        draft_product = self.product(name="Draft line", sku="DRAFT-1")
        other_draft = self.draft((draft_product, 1, "1.00"))
        draft_line = other_draft.lines.get()

        mutation_attempts = (
            lambda: purchase.save(),
            lambda: purchase.delete(),
            lambda: Purchase.objects.filter(pk=purchase.pk).update(reference="changed"),
            lambda: Purchase.objects.bulk_update([purchase], ["reference"]),
            lambda: Purchase.objects.filter(pk=purchase.pk).delete(),
            lambda: line.save(),
            lambda: line.delete(),
            lambda: PurchaseLine.objects.filter(pk=line.pk).update(quantity=9),
            lambda: PurchaseLine.objects.bulk_update([line], ["quantity"]),
            lambda: PurchaseLine.objects.filter(pk=line.pk).delete(),
            lambda: PurchaseLine.objects.create(
                purchase=purchase,
                product=self.product(name="New line", sku="NEW-1"),
                quantity=1,
                unit_cost=Decimal("1.00"),
            ),
            lambda: PurchaseLine.objects.bulk_create(
                [
                    PurchaseLine(
                        purchase=purchase,
                        product=self.product(name="Bulk line", sku="BULK-1"),
                        quantity=1,
                        unit_cost=Decimal("1.00"),
                    )
                ]
            ),
            lambda: PurchaseLine.objects.filter(pk=draft_line.pk).update(
                purchase=purchase
            ),
            lambda: PurchaseLine.objects.bulk_update(
                [
                    PurchaseLine(
                        pk=draft_line.pk,
                        purchase=purchase,
                        product=draft_product,
                        quantity=1,
                        unit_cost=Decimal("1.00"),
                    )
                ],
                ["purchase"],
            ),
        )
        for attempt in mutation_attempts:
            with self.assertRaisesRegex(TypeError, "immutable"):
                attempt()

    def test_movement_origins_are_exclusive_without_breaking_adjustment_history(self):
        product = self.product()
        adjustment = record_stock_adjustment(
            business=self.business,
            actor=self.owner,
            product=product,
            quantity_change=1,
            reason=StockAdjustment.Reason.FOUND,
        )
        movement = StockMovement.objects.get(stock_adjustment=adjustment)
        self.assertEqual(movement.kind, StockMovement.Kind.ADJUSTMENT)
        self.assertIsNone(movement.purchase_line_id)

        with self.assertRaises(ValidationError):
            StockMovement.objects.create(
                business=self.business,
                product=product,
                quantity_change=1,
                kind=StockMovement.Kind.PURCHASE,
                actor=self.owner,
            )

    def test_stock_movement_creation_validates_purchase_and_adjustment_provenance(self):
        purchase_product = self.product(name="Purchase Product", sku="PUR-1")
        other_product = self.product(name="Other Product", sku="OTHER-1")
        purchase = self.draft((purchase_product, 2, "10.00"))
        purchase.status = Purchase.Status.COMPLETED
        purchase._completion_authorized = True
        try:
            purchase.save(update_fields=["status", "updated_at"])
        finally:
            del purchase._completion_authorized
        purchase_line = purchase.lines.get()

        invalid_purchase_movements = (
            (
                "product",
                StockMovement(
                    business=self.business,
                    product=other_product,
                    quantity_change=purchase_line.quantity,
                    kind=StockMovement.Kind.PURCHASE,
                    purchase_line=purchase_line,
                    actor=self.owner,
                ),
                "Product must match",
            ),
            (
                "quantity",
                StockMovement(
                    business=self.business,
                    product=purchase_product,
                    quantity_change=purchase_line.quantity + 1,
                    kind=StockMovement.Kind.PURCHASE,
                    purchase_line=purchase_line,
                    actor=self.owner,
                ),
                "quantity must match",
            ),
            (
                "kind",
                StockMovement(
                    business=self.business,
                    product=purchase_product,
                    quantity_change=purchase_line.quantity,
                    kind=StockMovement.Kind.ADJUSTMENT,
                    purchase_line=purchase_line,
                    actor=self.owner,
                ),
                "require a Stock Adjustment",
            ),
        )
        for label, movement, error in invalid_purchase_movements:
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValidationError, error):
                    movement.save()

        other_business = Business.objects.create(name="Other Shop")
        with self.assertRaisesRegex(ValidationError, "Business must match"):
            StockMovement.objects.create(
                business=other_business,
                product=purchase_product,
                quantity_change=purchase_line.quantity,
                kind=StockMovement.Kind.PURCHASE,
                purchase_line=purchase_line,
                actor=self.owner,
            )

        with self.assertRaisesRegex(ValidationError, "quantity must match"):
            StockMovement.objects.bulk_create(
                [
                    StockMovement(
                        business=self.business,
                        product=purchase_product,
                        quantity_change=purchase_line.quantity + 1,
                        kind=StockMovement.Kind.PURCHASE,
                        purchase_line=purchase_line,
                        actor=self.owner,
                    )
                ]
            )

        adjustment = StockAdjustment.objects.create(
            business=self.business,
            product=purchase_product,
            quantity_change=3,
            reason=StockAdjustment.Reason.FOUND,
            actor=self.owner,
        )
        invalid_adjustment_movements = (
            (
                "business",
                {"business": other_business},
                "Business must match",
            ),
            (
                "product",
                {"product": other_product},
                "Product must match",
            ),
            (
                "quantity",
                {"quantity_change": adjustment.quantity_change + 1},
                "quantity must match",
            ),
        )
        for label, overrides, error in invalid_adjustment_movements:
            with self.subTest(label=label):
                values = {
                    "business": self.business,
                    "product": purchase_product,
                    "quantity_change": adjustment.quantity_change,
                    "kind": StockMovement.Kind.ADJUSTMENT,
                    "stock_adjustment": adjustment,
                    "actor": self.owner,
                }
                values.update(overrides)
                with self.assertRaisesRegex(ValidationError, error):
                    StockMovement.objects.create(**values)
        self.assertFalse(StockMovement.objects.filter(purchase_line=purchase_line).exists())
        self.assertFalse(StockMovement.objects.filter(stock_adjustment=adjustment).exists())

from datetime import date
from decimal import Decimal
from threading import Event, Thread, current_thread
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.db.models import Case, F, Value, When
from django.test import TestCase, TransactionTestCase, override_settings

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from catalogue.models import Product
from inventory.models import StockMovement
from sales.forms import SaleForm, SaleLineFormSet
from sales.models import Sale, SaleLine
from sales.services import complete_sale, save_draft_sale


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SaleCompletionServiceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="owner@example.com", password="password")
        self.staff = get_user_model().objects.create_user(email="staff@example.com", password="password")
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(user=self.owner, business=self.business, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.staff, business=self.business, role=Membership.Role.STAFF)

    def product(self, **overrides):
        values = {"business": self.business, "name": "Golden Penny", "sku": "GP-1", "stock_on_hand": 10, "unit_cost": Decimal("4.00"), "selling_price": Decimal("10.00")}
        values.update(overrides)
        return Product.objects.create(**values)

    def draft(self, *lines, actor=None, **overrides):
        sale = Sale.objects.create(business=self.business, creator=actor or self.owner, sale_date=date(2026, 9, 9), **overrides)
        for product, quantity, unit_price in lines:
            SaleLine.objects.create(sale=sale, product=product, quantity=quantity, unit_price=Decimal(unit_price))
        return sale

    def draft_edit_forms(self, sale, line, *, quantity=2):
        data = {
            "sale_date": sale.sale_date.isoformat(),
            "customer_name": sale.customer_name,
            "reference": "EDITED",
            "notes": sale.notes,
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "1",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-id": str(line.pk),
            "lines-0-product": str(line.product_id),
            "lines-0-quantity": str(quantity),
            "lines-0-unit_price": str(line.unit_price),
        }
        form = SaleForm(data, instance=sale)
        formset = SaleLineFormSet(data, instance=sale, form_kwargs={"business": self.business})
        self.assertTrue(form.is_valid())
        self.assertTrue(formset.is_valid())
        return form, formset

    def test_owner_and_staff_complete_and_snapshot_costs(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1", stock_on_hand=4, unit_cost=Decimal("6.50"))
        owner_sale = self.draft((first, 3, "10.00"), (second, 2, "20.00"))
        staff_sale = self.draft((first, 2, "11.00"), actor=self.staff)
        complete_sale(business=self.business, actor=self.owner, sale=owner_sale)
        complete_sale(business=self.business, actor=self.staff, sale=staff_sale)
        owner_sale.refresh_from_db(); staff_sale.refresh_from_db(); first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(owner_sale.status, Sale.Status.COMPLETED)
        owner_lines = list(owner_sale.lines.order_by("product_id", "pk"))
        self.assertEqual([line.cost_snapshot for line in owner_lines], [Decimal("4.00"), Decimal("6.50")])
        self.assertEqual(owner_sale.total, Decimal("70.00"))
        self.assertEqual(first.stock_on_hand, 5); self.assertEqual(second.stock_on_hand, 2)
        movements = list(StockMovement.objects.filter(sale_line__sale=owner_sale).order_by("sale_line__product_id", "sale_line_id"))
        self.assertEqual([movement.quantity_change for movement in movements], [-3, -2])
        self.assertEqual([movement.sale_line_id for movement in movements], [line.pk for line in owner_lines])
        self.assertTrue(all(movement.kind == StockMovement.Kind.SALE for movement in movements))
        self.assertTrue(all(movement.business_id == self.business.pk for movement in movements))
        self.assertEqual([movement.product_id for movement in movements], [line.product_id for line in owner_lines])
        audit = AuditEvent.objects.get(object_identifier=str(owner_sale.pk))
        self.assertEqual(audit.action, "sale.completed")
        self.assertEqual(audit.business_id, self.business.pk)
        self.assertEqual(audit.actor_id, self.owner.pk)

    def test_completion_locks_sale_before_ordered_lines(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1")
        sale = self.draft((second, 1, "10.00"), (first, 1, "20.00"))
        calls = []

        from sales import services

        original_lock_sale = services._lock_sale
        original_lock_lines = services._lock_sale_lines
        with patch("sales.services._lock_sale", side_effect=lambda **kwargs: (calls.append("sale"), original_lock_sale(**kwargs))[1]), patch(
            "sales.services._lock_sale_lines", side_effect=lambda **kwargs: (calls.append("lines"), original_lock_lines(**kwargs))[1]
        ):
            complete_sale(business=self.business, actor=self.owner, sale=sale)

        self.assertEqual(calls[:2], ["sale", "lines"])
        self.assertEqual(
            list(sale.lines.order_by("product_id", "pk").values_list("product_id", flat=True)),
            sorted((first.pk, second.pk)),
        )

    def test_stale_draft_edit_rechecks_status_after_the_sale_lock(self):
        product = self.product()
        sale = self.draft((product, 1, "10.00"))
        line = sale.lines.get()
        form, formset = self.draft_edit_forms(sale, line)
        complete_sale(business=self.business, actor=self.owner, sale=sale)

        with self.assertRaisesRegex(ValidationError, "already been completed"):
            save_draft_sale(
                business=self.business,
                actor=self.owner,
                sale=sale,
                form=form,
                formset=formset,
            )
        sale.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.COMPLETED)
        self.assertEqual(line.quantity, 1)
        self.assertEqual(line.cost_snapshot, Decimal("4.00"))

    def test_draft_edit_saves_after_parent_then_line_locks(self):
        product = self.product()
        sale = self.draft((product, 1, "10.00"))
        line = sale.lines.get()
        form, formset = self.draft_edit_forms(sale, line)
        calls = []

        from sales import services

        original_lock_sale = services._lock_sale
        original_lock_lines = services._lock_sale_lines
        with patch("sales.services._lock_sale", side_effect=lambda **kwargs: (calls.append("sale"), original_lock_sale(**kwargs))[1]), patch(
            "sales.services._lock_sale_lines", side_effect=lambda **kwargs: (calls.append("lines"), original_lock_lines(**kwargs))[1]
        ):
            save_draft_sale(business=self.business, actor=self.owner, sale=sale, form=form, formset=formset)

        sale.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(calls[:2], ["sale", "lines"])
        self.assertEqual(sale.reference, "EDITED")
        self.assertEqual(line.quantity, 2)

    def test_unavailable_stock_rechecked_and_no_partial_effect(self):
        product = self.product(stock_on_hand=2)
        sale = self.draft((product, 3, "10.00"))
        with self.assertRaisesRegex(ValidationError, "available Stock on Hand"):
            complete_sale(business=self.business, actor=self.owner, sale=sale)
        product.refresh_from_db(); sale.refresh_from_db()
        self.assertEqual(product.stock_on_hand, 2); self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertFalse(StockMovement.objects.exists())

    def test_repeated_completion_demo_inactive_cross_business_and_rollback(self):
        product = self.product(); sale = self.draft((product, 1, "10.00"))
        complete_sale(business=self.business, actor=self.owner, sale=sale)
        with self.assertRaisesRegex(ValidationError, "already been completed"):
            complete_sale(business=self.business, actor=self.owner, sale=sale)
        self.assertEqual(StockMovement.objects.count(), 1)
        other = self.product(name="Other", sku="OTHER", stock_on_hand=5)
        draft = self.draft((other, 1, "10.00"))
        self.business.is_demo = True; self.business.save(update_fields=["is_demo"])
        with self.assertRaises(PermissionDenied): complete_sale(business=self.business, actor=self.owner, sale=draft)
        self.business.is_demo = False; self.business.save(update_fields=["is_demo"])
        Membership.objects.filter(user=self.staff).update(is_active=False)
        with self.assertRaises(PermissionDenied): complete_sale(business=self.business, actor=self.staff, sale=draft)
        with patch("sales.services.record_audit_event", side_effect=RuntimeError("audit failure")):
            with self.assertRaisesRegex(RuntimeError, "audit failure"):
                complete_sale(business=self.business, actor=self.owner, sale=draft)
        other.refresh_from_db(); draft.refresh_from_db()
        self.assertEqual(other.stock_on_hand, 5); self.assertEqual(draft.status, Sale.Status.DRAFT)
        self.assertIsNone(draft.lines.get().cost_snapshot)
        self.assertFalse(StockMovement.objects.filter(sale_line__sale=draft).exists())
        self.assertFalse(AuditEvent.objects.filter(object_identifier=str(draft.pk)).exists())

    def test_completed_sale_and_lines_are_immutable(self):
        product = self.product(); sale = self.draft((product, 1, "10.00")); complete_sale(business=self.business, actor=self.owner, sale=sale)
        line = sale.lines.get()
        draft_product = self.product(name="Draft product", sku="DRAFT")
        draft_sale = self.draft((draft_product, 1, "10.00"))
        draft_line = draft_sale.lines.get()
        attempts = (
            lambda: sale.save(),
            lambda: sale.delete(),
            lambda: Sale.objects.filter(pk=sale.pk).update(reference="x"),
            lambda: Sale.objects.bulk_update([sale], ["reference"]),
            lambda: Sale.objects.filter(pk=sale.pk).delete(),
            lambda: Sale.objects.bulk_create([Sale(business=self.business, creator=self.owner, sale_date=date(2026, 9, 9), status=Sale.Status.COMPLETED)]),
            lambda: SaleLine.objects.filter(pk=line.pk).update(quantity=2),
            lambda: SaleLine.objects.bulk_update([line], ["quantity"]),
            lambda: line.save(),
            lambda: line.delete(),
            lambda: SaleLine.objects.filter(pk=line.pk).delete(),
            lambda: SaleLine.objects.create(sale=sale, product=self.product(name="New product", sku="NEW"), quantity=1, unit_price=Decimal("1.00")),
            lambda: SaleLine.objects.bulk_create([SaleLine(sale=sale, product=self.product(name="Bulk product", sku="BULK"), quantity=1, unit_price=Decimal("1.00"))]),
            lambda: SaleLine.objects.filter(pk=draft_line.pk).update(sale=sale),
            lambda: SaleLine.objects.bulk_update([SaleLine(pk=draft_line.pk, sale=sale, product=draft_product, quantity=1, unit_price=Decimal("1.00"))], ["sale"]),
        )
        for attempt in attempts:
            with self.assertRaisesRegex(TypeError, "immutable"): attempt()

    def test_sale_bulk_mutations_reject_status_expressions_and_materialize_generators(self):
        sale = self.draft()
        for status in (
            Sale.Status.COMPLETED,
            F("status"),
            Case(When(pk=sale.pk, then=Value(Sale.Status.COMPLETED)), default=F("status")),
        ):
            with self.subTest(status=status):
                with self.assertRaisesRegex(TypeError, "immutable"):
                    Sale.objects.filter(pk=sale.pk).update(status=status)
        sale.reference = "generator-safe"
        updated = Sale.objects.bulk_update((item for item in [sale]), ["reference"])
        sale.refresh_from_db()
        self.assertEqual(updated, 1)
        self.assertEqual(sale.reference, "generator-safe")
        with self.assertRaisesRegex(TypeError, "immutable"):
            Sale.objects.bulk_update((item for item in [sale]), ["status"])

    def test_line_queryset_delete_preserves_the_exact_selected_draft_lines(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1")
        sale = self.draft((first, 1, "10.00"), (second, 1, "10.00"))
        first_line, second_line = sale.lines.order_by("pk")

        deleted_count, _ = SaleLine.objects.filter(pk=first_line.pk).delete()

        self.assertEqual(deleted_count, 1)
        self.assertFalse(SaleLine.objects.filter(pk=first_line.pk).exists())
        self.assertTrue(SaleLine.objects.filter(pk=second_line.pk).exists())

    def test_draft_sale_line_queryset_and_bulk_updates_are_instance_save_only(self):
        first = self.product()
        second = self.product(name="Milo", sku="MILO-1")
        sale = self.draft((first, 1, "10.00"))
        other_sale = self.draft((second, 1, "10.00"))
        line = sale.lines.get()
        line.quantity = 2

        with self.assertRaisesRegex(TypeError, "instance saves"):
            SaleLine.objects.filter(pk=line.pk).update(quantity=2)
        with self.assertRaisesRegex(TypeError, "instance saves"):
            SaleLine.objects.bulk_update([line], ["quantity"])
        reassigned = SaleLine(
            pk=line.pk,
            sale=other_sale,
            product=first,
            quantity=1,
            unit_price=Decimal("10.00"),
        )
        with self.assertRaisesRegex(TypeError, "instance saves"):
            SaleLine.objects.bulk_update([reassigned], ["sale"])

        line.refresh_from_db()
        self.assertEqual(line.quantity, 1)
        self.assertEqual(line.sale_id, sale.pk)

    def test_stock_movement_rejects_invalid_sale_provenance_directly_and_in_bulk(self):
        product = self.product()
        other_product = self.product(name="Other", sku="OTHER")
        sale = self.draft((product, 2, "10.00"))
        complete_sale(business=self.business, actor=self.owner, sale=sale)
        line = sale.lines.get()
        other_business = Business.objects.create(name="Other Shop")

        invalid = (
            StockMovement(business=self.business, product=other_product, quantity_change=-line.quantity, kind=StockMovement.Kind.SALE, sale_line=line, actor=self.owner),
            StockMovement(business=self.business, product=product, quantity_change=-(line.quantity + 1), kind=StockMovement.Kind.SALE, sale_line=line, actor=self.owner),
            StockMovement(business=other_business, product=product, quantity_change=-line.quantity, kind=StockMovement.Kind.SALE, sale_line=line, actor=self.owner),
        )
        for movement in invalid:
            with self.assertRaises(ValidationError):
                movement.save()
        with self.assertRaisesRegex(ValidationError, "quantity must match"):
            StockMovement.objects.bulk_create(
                StockMovement(business=self.business, product=product, quantity_change=-(line.quantity + 1), kind=StockMovement.Kind.SALE, sale_line=line, actor=self.owner)
                for _ in range(1)
            )
        self.assertEqual(StockMovement.objects.filter(sale_line=line).count(), 1)

    def test_stock_movement_sale_provenance_uses_persisted_line_not_relation_cache(self):
        product = self.product()
        other_product = self.product(name="Other", sku="OTHER")
        sale = self.draft((product, 2, "10.00"))
        sale.status = Sale.Status.COMPLETED
        sale._completion_authorized = True
        try:
            sale.save(update_fields=["status", "updated_at"])
        finally:
            del sale._completion_authorized
        line = sale.lines.get()
        forged_line = SaleLine(
            pk=line.pk,
            sale=Sale(pk=sale.pk, status=Sale.Status.DRAFT),
            product=other_product,
            quantity=99,
            unit_price=Decimal("1.00"),
        )
        movement = StockMovement(
            business=self.business,
            product=product,
            quantity_change=-line.quantity,
            kind=StockMovement.Kind.SALE,
            sale_line=forged_line,
            actor=self.owner,
        )

        self.assertIs(movement.sale_line, forged_line)
        movement.full_clean()


@skipUnless(
    connection.vendor == "postgresql",
    "Release verification only: requires PostgreSQL row locks and independent database connections.",
)
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SaleEditCompletionPostgreSQLConcurrencyTests(TransactionTestCase):
    """Exercise the real edit/completion race against PostgreSQL's row locking."""

    reset_sequences = True

    def setUp(self):
        self.owner = get_user_model().objects.create_user(email="owner@example.com", password="password")
        self.business = Business.objects.create(name="Balogun Corner Shop")
        Membership.objects.create(user=self.owner, business=self.business, role=Membership.Role.OWNER)
        self.product = Product.objects.create(
            business=self.business,
            name="Golden Penny",
            sku="GP-1",
            stock_on_hand=10,
            unit_cost=Decimal("4.00"),
            selling_price=Decimal("10.00"),
        )
        self.sale = Sale.objects.create(business=self.business, creator=self.owner, sale_date=date(2026, 9, 9))
        self.line = SaleLine.objects.create(sale=self.sale, product=self.product, quantity=1, unit_price=Decimal("10.00"))

    def test_edit_locked_first_serializes_completion_and_uses_edited_line(self):
        from sales import services

        edit_locked = Event()
        release_edit = Event()
        completion_started = Event()
        errors = []
        original_lock_lines = services._lock_sale_lines

        def pause_edit_after_line_locks(**kwargs):
            lines = original_lock_lines(**kwargs)
            if current_thread().name == "sale-edit":
                edit_locked.set()
                if not release_edit.wait(timeout=10):
                    raise TimeoutError("The completion worker did not reach the Sale lock.")
            return lines

        def edit_worker():
            close_old_connections()
            try:
                sale = Sale.objects.get(pk=self.sale.pk)
                line = SaleLine.objects.get(pk=self.line.pk)
                data = {
                    "sale_date": sale.sale_date.isoformat(), "customer_name": "", "reference": "EDITED", "notes": "",
                    "lines-TOTAL_FORMS": "1", "lines-INITIAL_FORMS": "1", "lines-MIN_NUM_FORMS": "0", "lines-MAX_NUM_FORMS": "1000",
                    "lines-0-id": str(line.pk), "lines-0-product": str(line.product_id), "lines-0-quantity": "2", "lines-0-unit_price": "10.00",
                }
                form = SaleForm(data, instance=sale)
                formset = SaleLineFormSet(data, instance=sale, form_kwargs={"business": self.business})
                if not form.is_valid() or not formset.is_valid():
                    raise AssertionError("The concurrent draft edit must be valid before it waits for completion.")
                save_draft_sale(business=self.business, actor=self.owner, sale=sale, form=form, formset=formset)
            except Exception as error:  # thread exceptions are asserted in the test process
                errors.append(error)
            finally:
                close_old_connections()

        def completion_worker():
            close_old_connections()
            try:
                completion_started.set()
                complete_sale(business=self.business, actor=self.owner, sale=Sale.objects.get(pk=self.sale.pk))
            except Exception as error:
                errors.append(error)
            finally:
                close_old_connections()

        with patch("sales.services._lock_sale_lines", side_effect=pause_edit_after_line_locks):
            edit_thread = Thread(target=edit_worker, name="sale-edit")
            edit_thread.start()
            self.assertTrue(edit_locked.wait(timeout=10), "The draft edit did not acquire the Sale and line locks.")
            completion_thread = Thread(target=completion_worker, name="sale-completion")
            completion_thread.start()
            self.assertTrue(completion_started.wait(timeout=10))
            release_edit.set()
            edit_thread.join(timeout=15)
            completion_thread.join(timeout=15)

        self.assertFalse(edit_thread.is_alive())
        self.assertFalse(completion_thread.is_alive())
        self.assertEqual(errors, [])
        self.sale.refresh_from_db()
        self.line.refresh_from_db()
        self.assertEqual(self.sale.status, Sale.Status.COMPLETED)
        self.assertEqual(self.line.quantity, 2)
        self.assertEqual(self.line.cost_snapshot, Decimal("4.00"))
        self.assertEqual(StockMovement.objects.get(sale_line=self.line).quantity_change, -2)

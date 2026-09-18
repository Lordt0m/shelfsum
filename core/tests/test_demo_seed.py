from datetime import datetime
from decimal import Decimal
from io import StringIO
from threading import Barrier, Thread
from unittest import skipUnless
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import CommandError, call_command
from django.db import close_old_connections, connection, models
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from catalogue.models import Product
from catalogue.services import ProductCreation, create_product
from core.demo import (
    DEMO_BUSINESS_NAME,
    DEMO_OWNER_EMAIL,
    DEMO_OWNER_PASSWORD,
    DEMO_REFERENCE_END,
    DEMO_REFERENCE_START,
    DEMO_STAFF_EMAIL,
    DEMO_STAFF_PASSWORD,
    DemoSeedError,
    seed_demo_business,
)
from expenses.models import Expense
from inventory.models import StockAdjustment, StockMovement
from purchases.models import Purchase
from sales.models import Sale, SaleLine
from businesses.dashboard import dashboard_context
from reports.expense import ExpenseReportFilters, build_expense_report
from reports.movement import MovementReportFilters, build_movement_report
from reports.purchase import PurchaseReportFilters, build_purchase_report
from reports.sales import SalesReportFilters, build_sales_report
from reports.stock_position import StockPositionReportFilters, build_stock_position_report


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DemoSeedCommandTests(TestCase):
    def test_seed_demo_command_is_available(self):
        output = StringIO()

        call_command("seed_demo", stdout=output)

        self.assertIn(DEMO_BUSINESS_NAME, output.getvalue())
        self.assertNotIn(DEMO_OWNER_EMAIL, output.getvalue())
        self.assertNotIn(DEMO_OWNER_PASSWORD, output.getvalue())
        self.assertNotIn(DEMO_STAFF_EMAIL, output.getvalue())
        self.assertNotIn(DEMO_STAFF_PASSWORD, output.getvalue())

    def test_first_run_builds_coherent_canonical_dataset(self):
        seed_demo_business()

        owner = get_user_model().objects.get(email=DEMO_OWNER_EMAIL)
        staff = get_user_model().objects.get(email=DEMO_STAFF_EMAIL)
        business = Business.objects.get(name=DEMO_BUSINESS_NAME)
        self.assertTrue(owner.check_password(DEMO_OWNER_PASSWORD))
        self.assertTrue(staff.check_password(DEMO_STAFF_PASSWORD))
        self.assertTrue(business.is_demo)
        self.assertEqual(
            set(Membership.objects.filter(business=business).values_list("role", flat=True)),
            {Membership.Role.OWNER, Membership.Role.STAFF},
        )

        products = {product.sku: product for product in Product.objects.filter(business=business)}
        self.assertEqual(len(products), 5)
        self.assertTrue(products["DEMO-KOR-100"].is_low_stock)
        self.assertFalse(products["DEMO-PAP-090"].is_active)
        self.assertEqual(products["DEMO-KOR-100"].stock_on_hand, 17)

        self.assertEqual(Purchase.objects.filter(business=business, status=Purchase.Status.COMPLETED).count(), 2)
        self.assertEqual(Purchase.objects.filter(business=business, status=Purchase.Status.VOIDED).count(), 1)
        self.assertEqual(Sale.objects.filter(business=business, status=Sale.Status.COMPLETED).count(), 2)
        self.assertEqual(Sale.objects.filter(business=business, status=Sale.Status.VOIDED).count(), 1)
        self.assertEqual(Expense.objects.filter(business=business).count(), 2)
        self.assertEqual(Expense.objects.filter(business=business, status=Expense.Status.VOIDED).count(), 1)
        self.assertEqual(Expense.objects.filter(business=business, correction_of__isnull=False).count(), 1)
        self.assertEqual(StockAdjustment.objects.filter(business=business).count(), 6)
        self.assertEqual(StockAdjustment.objects.filter(business=business, reason=StockAdjustment.Reason.FOUND).count(), 1)
        self.assertEqual(StockMovement.objects.filter(business=business).count(), 18)
        for product in products.values():
            net = sum(StockMovement.objects.filter(business=business, product=product).values_list("quantity_change", flat=True))
            self.assertEqual(net, product.stock_on_hand)

        self.assertEqual(AuditEvent.objects.filter(business=business).count(), 19)
        self.assertEqual(
            set(AuditEvent.objects.filter(business=business).values_list("action", flat=True)),
            {
                "business.created", "membership.staff_added", "product.created", "product.deactivated",
                "purchase.completed", "purchase.voided", "sale.completed", "sale.voided",
                "expense.recorded", "expense.corrected", "stock.adjusted",
            },
        )

    def test_exact_rerun_converges_and_resets_only_named_credentials(self):
        seed_demo_business()
        counts = {
            model.__name__: model.objects.count()
            for model in (Business, Membership, Product, Purchase, Sale, Expense, StockAdjustment, StockMovement, AuditEvent)
        }
        owner = get_user_model().objects.get(email=DEMO_OWNER_EMAIL)
        staff = get_user_model().objects.get(email=DEMO_STAFF_EMAIL)
        owner.set_password("changed-owner")
        owner.save(update_fields=["password"])
        staff.set_password("changed-staff")
        staff.save(update_fields=["password"])

        seed_demo_business()

        owner.refresh_from_db()
        staff.refresh_from_db()
        self.assertTrue(owner.check_password(DEMO_OWNER_PASSWORD))
        self.assertTrue(staff.check_password(DEMO_STAFF_PASSWORD))
        self.assertEqual(
            counts,
            {
                model.__name__: model.objects.count()
                for model in (Business, Membership, Product, Purchase, Sale, Expense, StockAdjustment, StockMovement, AuditEvent)
            },
        )

    def test_drift_fails_before_changing_named_credentials(self):
        seed_demo_business()
        staff = get_user_model().objects.get(email=DEMO_STAFF_EMAIL)
        staff.set_password("known-drift-password")
        staff.save(update_fields=["password"])
        Product.objects.filter(sku="DEMO-KOR-100").update(low_stock_threshold=0)

        with self.assertRaisesRegex(DemoSeedError, "drift"):
            seed_demo_business()

        staff.refresh_from_db()
        self.assertTrue(staff.check_password("known-drift-password"))

    def test_first_run_rolls_back_users_and_business_when_downstream_fails(self):
        with patch("core.demo.create_product", side_effect=RuntimeError("simulated demo failure")):
            with self.assertRaisesRegex(RuntimeError, "simulated demo failure"):
                seed_demo_business()

        self.assertFalse(get_user_model().objects.filter(email__in=[DEMO_OWNER_EMAIL, DEMO_STAFF_EMAIL]).exists())
        self.assertFalse(Business.objects.filter(name=DEMO_BUSINESS_NAME).exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_unrelated_business_and_user_are_untouched(self):
        unrelated_user = get_user_model().objects.create_user(email="shopkeeper@example.com", password="unchanged")
        unrelated_business = Business.objects.create(name="Unrelated Lagos Shop")
        Membership.objects.create(user=unrelated_user, business=unrelated_business, role=Membership.Role.OWNER)

        seed_demo_business()

        unrelated_user.refresh_from_db()
        unrelated_business.refresh_from_db()
        self.assertTrue(unrelated_user.check_password("unchanged"))
        self.assertEqual(unrelated_business.name, "Unrelated Lagos Shop")
        self.assertFalse(unrelated_business.is_demo)
        self.assertEqual(Membership.objects.filter(business=unrelated_business).count(), 1)

    def test_demo_write_rule_still_denies_direct_service_mutation(self):
        seed_demo_business()
        owner = get_user_model().objects.get(email=DEMO_OWNER_EMAIL)
        business = Business.objects.get(name=DEMO_BUSINESS_NAME)

        with self.assertRaises(PermissionDenied):
            create_product(
                business=business,
                actor=owner,
                details=ProductCreation(
                    name="Forbidden Demo Product",
                    sku="FORBIDDEN-1",
                    description="",
                    selling_price=Decimal("1.00"),
                    unit_cost=Decimal("1.00"),
                    opening_quantity=0,
                    low_stock_threshold=0,
                ),
            )
        self.assertFalse(Product.objects.filter(name="Forbidden Demo Product").exists())

    def test_privilege_drift_fails_before_either_password_is_reset(self):
        seed_demo_business()
        owner = get_user_model().objects.get(email=DEMO_OWNER_EMAIL)
        staff = get_user_model().objects.get(email=DEMO_STAFF_EMAIL)
        owner.set_password("owner-drift-password")
        owner.is_staff = True
        owner.save(update_fields=["password", "is_staff"])
        staff.set_password("staff-drift-password")
        staff.save(update_fields=["password"])

        with self.assertRaisesRegex(DemoSeedError, "identity drifted"):
            seed_demo_business()

        owner.refresh_from_db()
        staff.refresh_from_db()
        self.assertTrue(owner.check_password("owner-drift-password"))
        self.assertTrue(staff.check_password("staff-drift-password"))

    def test_cost_snapshot_provenance_drift_fails_before_password_reset(self):
        seed_demo_business()
        sale_line = SaleLine.objects.select_related("sale").get(sale__reference="DEMO-SAL-001", product__sku="DEMO-NIA-500")
        models.QuerySet.update(SaleLine.objects.filter(pk=sale_line.pk), cost_snapshot=Decimal("1.00"))
        staff = get_user_model().objects.get(email=DEMO_STAFF_EMAIL)
        staff.set_password("cost-drift-password")
        staff.save(update_fields=["password"])

        with self.assertRaisesRegex(DemoSeedError, "Sale DEMO-SAL-001 lines drifted"):
            seed_demo_business()

        staff.refresh_from_db()
        self.assertTrue(staff.check_password("cost-drift-password"))

    def test_management_command_wraps_canonical_drift_as_command_error(self):
        seed_demo_business()
        Product.objects.filter(sku="DEMO-KOR-100").update(low_stock_threshold=0)

        with self.assertRaisesRegex(CommandError, "Demo seed drift"):
            call_command("seed_demo", stdout=StringIO())

    def test_malformed_audit_identifier_is_demo_drift_before_password_reset(self):
        seed_demo_business()
        event = AuditEvent.objects.get(action="business.created")
        models.QuerySet.update(
            AuditEvent.objects.filter(pk=event.pk), object_identifier="not-a-number"
        )
        staff = get_user_model().objects.get(email=DEMO_STAFF_EMAIL)
        staff.set_password("audit-drift-password")
        staff.save(update_fields=["password"])

        with self.assertRaisesRegex(DemoSeedError, "Audit Event attribution"):
            seed_demo_business()

        staff.refresh_from_db()
        self.assertTrue(staff.check_password("audit-drift-password"))

    def test_swapped_product_audit_targets_are_demo_drift_before_password_reset(self):
        seed_demo_business()
        events = list(
            AuditEvent.objects.filter(action="product.created").order_by("pk")[:2]
        )
        first_identifier, second_identifier = events[0].object_identifier, events[1].object_identifier
        models.QuerySet.update(
            AuditEvent.objects.filter(pk=events[0].pk), object_identifier=second_identifier
        )
        models.QuerySet.update(
            AuditEvent.objects.filter(pk=events[1].pk), object_identifier=first_identifier
        )
        staff = get_user_model().objects.get(email=DEMO_STAFF_EMAIL)
        staff.set_password("audit-target-drift-password")
        staff.save(update_fields=["password"])

        with self.assertRaisesRegex(DemoSeedError, "Audit Event attribution"):
            seed_demo_business()

        staff.refresh_from_db()
        self.assertTrue(staff.check_password("audit-target-drift-password"))

    def test_fixed_reference_period_drives_dashboard_and_reports(self):
        seed_demo_business()
        business = Business.objects.get(name=DEMO_BUSINESS_NAME)
        lagos_now = timezone.make_aware(datetime(2026, 8, 20, 12, 0), ZoneInfo("Africa/Lagos"))
        with patch("businesses.dashboard.timezone.now", return_value=lagos_now):
            dashboard = dashboard_context(business=business)["dashboard"]

        self.assertEqual((dashboard["period_start"], dashboard["period_end"]), (DEMO_REFERENCE_START, DEMO_REFERENCE_END))
        self.assertEqual(dashboard["revenue"], Decimal("25800.00"))
        self.assertEqual(dashboard["cost_of_goods_sold"], Decimal("17850.00"))
        self.assertEqual(dashboard["expenses"], Decimal("275000.00"))
        self.assertEqual(dashboard["stock_value"], Decimal("61400.00"))
        self.assertEqual(dashboard["low_stock_count"], 1)

        sales = build_sales_report(
            business=business,
            filters=SalesReportFilters.from_query_params({"date_from": DEMO_REFERENCE_START.isoformat(), "date_to": DEMO_REFERENCE_END.isoformat()}),
        )
        purchases = build_purchase_report(
            business=business,
            filters=PurchaseReportFilters.from_query_params({"date_from": DEMO_REFERENCE_START.isoformat(), "date_to": DEMO_REFERENCE_END.isoformat()}),
        )
        expenses = build_expense_report(
            business=business,
            filters=ExpenseReportFilters.from_query_params({"date_from": DEMO_REFERENCE_START.isoformat(), "date_to": DEMO_REFERENCE_END.isoformat()}),
        )
        stock = build_stock_position_report(
            business=business,
            filters=StockPositionReportFilters.from_query_params({"product_status": "active", "stock_state": "positive"}),
        )
        movements = build_movement_report(
            business=business,
            filters=MovementReportFilters(kind="all", product_id=None, date_from=None, date_to=None),
        )
        self.assertEqual((len(sales.rows), sales.revenue), (2, Decimal("25800.00")))
        self.assertEqual((len(purchases.rows), purchases.total), (2, Decimal("31550.00")))
        self.assertEqual((len(expenses.rows), expenses.total), (1, Decimal("275000.00")))
        self.assertEqual((len(stock.rows), stock.total), (4, Decimal("59000.00")))
        self.assertEqual((len(movements.rows), movements.net_change), (18, 87))


@skipUnless(
    connection.vendor == "postgresql",
    "Release verification only: requires PostgreSQL row locks and independent database connections.",
)
class DemoSeedPostgreSQLConcurrencyTests(TransactionTestCase):
    """Verify the sentinel lock serializes two first-run seed commands."""

    reset_sequences = True

    def test_simultaneous_first_runs_both_verify_one_canonical_dataset(self):
        start = Barrier(2)
        errors = []
        results = []

        def worker():
            close_old_connections()
            try:
                start.wait(timeout=10)
                results.append(seed_demo_business().pk)
            except Exception as error:
                errors.append(error)
            finally:
                close_old_connections()

        first = Thread(target=worker, name="demo-seed-1")
        second = Thread(target=worker, name="demo-seed-2")
        first.start()
        second.start()
        first.join(timeout=90)
        second.join(timeout=90)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(Business.objects.filter(name=DEMO_BUSINESS_NAME).count(), 1)
        self.assertEqual(
            get_user_model()
            .objects.filter(email__in=[DEMO_OWNER_EMAIL, DEMO_STAFF_EMAIL])
            .count(),
            2,
        )
        business = Business.objects.get(name=DEMO_BUSINESS_NAME)
        self.assertTrue(business.is_demo)
        self.assertEqual(Membership.objects.filter(business=business).count(), 2)
        self.assertEqual(Product.objects.filter(business=business).count(), 5)
        self.assertEqual(Purchase.objects.filter(business=business).count(), 3)
        self.assertEqual(Sale.objects.filter(business=business).count(), 3)
        self.assertEqual(StockMovement.objects.filter(business=business).count(), 18)
        self.assertEqual(AuditEvent.objects.filter(business=business).count(), 19)

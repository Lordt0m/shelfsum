"""Deterministic, fictional data for the read-only Demo Business.

This module is deliberately the only orchestration layer for the demo seed. It
uses each owning application service so the generated records exercise the same
stock, immutability, and audit invariants as normal business activity.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from auditing.models import AuditEvent
from businesses.models import Business, Membership
from businesses.services import add_staff_member, create_business_for_owner
from catalogue.models import Product
from catalogue.services import ProductCreation, create_product, deactivate_product
from expenses.models import Expense
from expenses.services import correct_expense, record_expense
from inventory.models import StockAdjustment, StockMovement
from inventory.services import record_stock_adjustment
from purchases.forms import PurchaseForm, PurchaseLineFormSet
from purchases.models import Purchase
from purchases.services import complete_purchase, create_draft_purchase, void_purchase
from sales.forms import SaleForm, SaleLineFormSet
from sales.models import Sale
from sales.services import complete_sale, create_draft_sale, void_sale


DEMO_BUSINESS_NAME = "Lagos Lantern Pantry Demo (Fictional)"
DEMO_OWNER_EMAIL = "demo-owner@shelfsum.test"
DEMO_OWNER_PASSWORD = "ShelfSumDemoOwner2026!"
DEMO_STAFF_EMAIL = "demo-staff@shelfsum.test"
DEMO_STAFF_PASSWORD = "ShelfSumDemoStaff2026!"
DEMO_REFERENCE_START = date(2026, 8, 1)
DEMO_REFERENCE_END = date(2026, 8, 31)


class DemoSeedError(RuntimeError):
    """Raised when existing fictional demo state is not canonical."""


@dataclass(frozen=True)
class DemoCredential:
    email: str
    password: str
    first_name: str
    last_name: str
    role: str


DEMO_CREDENTIALS = (
    DemoCredential(DEMO_OWNER_EMAIL, DEMO_OWNER_PASSWORD, "Adaeze", "Demo", Membership.Role.OWNER),
    DemoCredential(DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD, "Bayo", "Sample", Membership.Role.STAFF),
)

_PRODUCTS = (
    {
        "name": "NiaPalm Twist Noodles",
        "sku": "DEMO-NIA-500",
        "description": "500 g fictional noodle pack",
        "selling_price": Decimal("1400.00"),
        "unit_cost": Decimal("1050.00"),
        "opening_quantity": 20,
        "low_stock_threshold": 8,
    },
    {
        "name": "KoraMoo Sachet",
        "sku": "DEMO-KOR-100",
        "description": "100 g fictional sachet",
        "selling_price": Decimal("700.00"),
        "unit_cost": Decimal("450.00"),
        "opening_quantity": 12,
        "low_stock_threshold": 20,
    },
    {
        "name": "BlueBasin Wash Powder",
        "sku": "DEMO-BLU-500",
        "description": "500 g fictional wash powder",
        "selling_price": Decimal("1300.00"),
        "unit_cost": Decimal("900.00"),
        "opening_quantity": 10,
        "low_stock_threshold": 4,
    },
    {
        "name": "SunsetFizz Can",
        "sku": "DEMO-SUN-330",
        "description": "330 ml fictional drink can",
        "selling_price": Decimal("800.00"),
        "unit_cost": Decimal("500.00"),
        "opening_quantity": 18,
        "low_stock_threshold": 6,
    },
    {
        "name": "PaperMoon Soap Bar",
        "sku": "DEMO-PAP-090",
        "description": "90 g fictional bar (discontinued)",
        "selling_price": Decimal("600.00"),
        "unit_cost": Decimal("400.00"),
        "opening_quantity": 6,
        "low_stock_threshold": 2,
    },
)

_PURCHASES = (
    {
        "reference": "DEMO-PUR-001",
        "purchase_date": date(2026, 8, 8),
        "supplier_name": "Fictional Oke-Arin Supplier",
        "lines": (("DEMO-NIA-500", 12, Decimal("1050.00")), ("DEMO-KOR-100", 15, Decimal("450.00"))),
    },
    {
        "reference": "DEMO-PUR-002",
        "purchase_date": date(2026, 8, 15),
        "supplier_name": "Fictional Ikeja Distributor",
        "lines": (("DEMO-BLU-500", 8, Decimal("900.00")), ("DEMO-SUN-330", 10, Decimal("500.00"))),
    },
    {
        "reference": "DEMO-PUR-VOID",
        "purchase_date": date(2026, 8, 22),
        "supplier_name": "Fictional Oke-Arin Supplier",
        "lines": (("DEMO-NIA-500", 5, Decimal("1050.00")),),
    },
)

_SALES = (
    {
        "reference": "DEMO-SAL-001",
        "sale_date": date(2026, 8, 12),
        "customer_name": "Fictional Mariam Sample Buyer",
        "lines": (("DEMO-NIA-500", 7, Decimal("1400.00")), ("DEMO-KOR-100", 12, Decimal("700.00"))),
    },
    {
        "reference": "DEMO-SAL-002",
        "sale_date": date(2026, 8, 19),
        "customer_name": "Fictional Adebayo Sample Shop",
        "lines": (("DEMO-BLU-500", 4, Decimal("1300.00")), ("DEMO-SUN-330", 3, Decimal("800.00"))),
    },
    {
        "reference": "DEMO-SAL-VOID",
        "sale_date": date(2026, 8, 25),
        "customer_name": "Fictional Mariam Sample Buyer",
        "lines": (("DEMO-NIA-500", 2, Decimal("1400.00")),),
    },
)


def _formset_data(*, prefix, lines, product_by_sku, price_field):
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(lines)),
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for index, (sku, quantity, price) in enumerate(lines):
        data[f"{prefix}-{index}-product"] = str(product_by_sku[sku].pk)
        data[f"{prefix}-{index}-quantity"] = str(quantity)
        data[f"{prefix}-{index}-{price_field}"] = str(price)
    return data


def _create_purchase(*, business, actor, spec, product_by_sku):
    form = PurchaseForm(
        data={
            "purchase_date": spec["purchase_date"].isoformat(),
            "supplier_name": spec["supplier_name"],
            "reference": spec["reference"],
            "notes": "Fictional Demo Business record.",
        }
    )
    if not form.is_valid():
        raise DemoSeedError(f"Invalid canonical Purchase form: {form.errors}")
    formset = PurchaseLineFormSet(
        data=_formset_data(
            prefix="lines",
            lines=spec["lines"],
            product_by_sku=product_by_sku,
            price_field="unit_cost",
        ),
        instance=Purchase(),
        form_kwargs={"business": business},
    )
    if not formset.is_valid():
        raise DemoSeedError(f"Invalid canonical Purchase lines: {formset.errors}")
    purchase = create_draft_purchase(business=business, actor=actor, form=form, formset=formset)
    complete_purchase(business=business, actor=actor, purchase=purchase)
    return purchase


def _create_sale(*, business, actor, spec, product_by_sku):
    form = SaleForm(
        data={
            "sale_date": spec["sale_date"].isoformat(),
            "customer_name": spec["customer_name"],
            "reference": spec["reference"],
            "notes": "Fictional Demo Business record.",
        }
    )
    if not form.is_valid():
        raise DemoSeedError(f"Invalid canonical Sale form: {form.errors}")
    formset = SaleLineFormSet(
        data=_formset_data(
            prefix="lines",
            lines=spec["lines"],
            product_by_sku=product_by_sku,
            price_field="unit_price",
        ),
        instance=Sale(),
        form_kwargs={"business": business},
    )
    if not formset.is_valid():
        raise DemoSeedError(f"Invalid canonical Sale lines: {formset.errors}")
    sale = create_draft_sale(business=business, actor=actor, form=form, formset=formset)
    complete_sale(business=business, actor=actor, sale=sale)
    return sale


def _create_canonical_dataset(*, owner, staff):
    business = create_business_for_owner(
        actor=owner,
        name=DEMO_BUSINESS_NAME,
        phone_number="",
        address="Fictional demo premises, Lagos - no physical location",
    )
    add_staff_member(business=business, actor=owner, email=staff.email)

    product_by_sku = {}
    for details in _PRODUCTS:
        product_by_sku[details["sku"]] = create_product(
            business=business,
            actor=owner,
            details=ProductCreation(**details),
        )

    inactive_product = product_by_sku["DEMO-PAP-090"]
    deactivate_product(business=business, actor=owner, product=inactive_product)

    for spec in _PURCHASES:
        purchase = _create_purchase(
            business=business,
            actor=staff,
            spec=spec,
            product_by_sku=product_by_sku,
        )
        if spec["reference"] == "DEMO-PUR-VOID":
            void_purchase(business=business, actor=owner, purchase=purchase)

    for spec in _SALES:
        sale = _create_sale(
            business=business,
            actor=staff,
            spec=spec,
            product_by_sku=product_by_sku,
        )
        if spec["reference"] == "DEMO-SAL-VOID":
            void_sale(business=business, actor=owner, sale=sale)

    expense = record_expense(
        business=business,
        actor=staff,
        details={
            "date": date(2026, 8, 5),
            "category": Expense.Category.RENT,
            "description": "Fictional August premises estimate",
            "amount": Decimal("250000.00"),
            "notes": "Fictional demo expense only.",
        },
    )
    correct_expense(
        business=business,
        actor=owner,
        expense=expense,
        details={
            "date": date(2026, 8, 5),
            "category": Expense.Category.RENT,
            "description": "Fictional August premises correction",
            "amount": Decimal("275000.00"),
            "notes": "Corrected fictional demo expense only.",
        },
    )
    record_stock_adjustment(
        business=business,
        actor=staff,
        product=product_by_sku["DEMO-KOR-100"],
        quantity_change=2,
        reason=StockAdjustment.Reason.FOUND,
        notes="Two fictional sachets found during the Friday count.",
    )

    # The maintenance window ends inside the transaction and is never visible
    # to a committed request. Runtime writes still use ensure_business_write_allowed.
    business.is_demo = True
    business.save(update_fields=["is_demo", "updated_at"])
    return business


def _fail(message):
    raise DemoSeedError(f"Demo seed drift: {message}")


def _verify_canonical_dataset(*, business, owner, staff):
    if not business.is_demo:
        _fail("the canonical Business must already be marked as Demo")
    if (business.phone_number, business.address, business.currency, business.timezone) != (
        "",
        "Fictional demo premises, Lagos - no physical location",
        "NGN",
        "Africa/Lagos",
    ):
        _fail("Business settings do not match the canonical manifest")

    memberships = list(Membership.objects.filter(business=business).order_by("pk"))
    if len(memberships) != 2:
        _fail("expected exactly the Owner and Staff Member memberships")
    by_user = {membership.user_id: membership for membership in memberships}
    for user, role in ((owner, Membership.Role.OWNER), (staff, Membership.Role.STAFF)):
        membership = by_user.get(user.pk)
        if membership is None or membership.role != role or not membership.is_active:
            _fail(f"membership drift for {user.email}")

    products = list(Product.objects.filter(business=business).order_by("sku"))
    if len(products) != len(_PRODUCTS):
        _fail("expected exactly five canonical Products")
    product_by_sku = {product.sku: product for product in products}
    expected_stocks = {
        "DEMO-NIA-500": 25,
        "DEMO-KOR-100": 17,
        "DEMO-BLU-500": 14,
        "DEMO-SUN-330": 25,
        "DEMO-PAP-090": 6,
    }
    for details in _PRODUCTS:
        product = product_by_sku.get(details["sku"])
        if product is None:
            _fail(f"missing Product {details['sku']}")
        for field in ("name", "description", "selling_price", "unit_cost", "low_stock_threshold"):
            if getattr(product, field) != details[field]:
                _fail(f"Product {details['sku']} field {field} drifted")
        if product.stock_on_hand != expected_stocks[details["sku"]]:
            _fail(f"Product {details['sku']} Stock on Hand drifted")
        if product.is_active != (details["sku"] != "DEMO-PAP-090"):
            _fail(f"Product {details['sku']} active state drifted")
    if not product_by_sku["DEMO-KOR-100"].is_low_stock:
        _fail("the canonical low-stock Product is no longer low stock")

    purchases = list(Purchase.objects.filter(business=business).order_by("reference"))
    if len(purchases) != len(_PURCHASES):
        _fail("expected exactly three canonical Purchases")
    purchase_by_reference = {purchase.reference: purchase for purchase in purchases}
    for spec in _PURCHASES:
        purchase = purchase_by_reference.get(spec["reference"])
        if (
            purchase is None
            or purchase.purchase_date != spec["purchase_date"]
            or purchase.supplier_name != spec["supplier_name"]
            or purchase.notes != "Fictional Demo Business record."
            or purchase.creator_id != staff.pk
        ):
            _fail(f"Purchase {spec['reference']} drifted")
        expected_status = Purchase.Status.VOIDED if spec["reference"] == "DEMO-PUR-VOID" else Purchase.Status.COMPLETED
        if purchase.status != expected_status:
            _fail(f"Purchase {spec['reference']} status drifted")
        lines = {
            (line.product.sku, line.quantity, line.unit_cost)
            for line in purchase.lines.select_related("product")
        }
        if lines != set(spec["lines"]):
            _fail(f"Purchase {spec['reference']} lines drifted")

    sales = list(Sale.objects.filter(business=business).order_by("reference"))
    if len(sales) != len(_SALES):
        _fail("expected exactly three canonical Sales")
    sale_by_reference = {sale.reference: sale for sale in sales}
    for spec in _SALES:
        sale = sale_by_reference.get(spec["reference"])
        if (
            sale is None
            or sale.sale_date != spec["sale_date"]
            or sale.customer_name != spec["customer_name"]
            or sale.notes != "Fictional Demo Business record."
            or sale.creator_id != staff.pk
        ):
            _fail(f"Sale {spec['reference']} drifted")
        expected_status = Sale.Status.VOIDED if spec["reference"] == "DEMO-SAL-VOID" else Sale.Status.COMPLETED
        if sale.status != expected_status:
            _fail(f"Sale {spec['reference']} status drifted")
        lines = {
            (
                line.product.sku,
                line.quantity,
                line.unit_price,
                line.cost_snapshot,
            )
            for line in sale.lines.select_related("product")
        }
        expected_lines = {
            (
                sku,
                quantity,
                unit_price,
                next(item["unit_cost"] for item in _PRODUCTS if item["sku"] == sku),
            )
            for sku, quantity, unit_price in spec["lines"]
        }
        if lines != expected_lines:
            _fail(f"Sale {spec['reference']} lines drifted")

    expenses = list(Expense.objects.filter(business=business).order_by("pk"))
    if len(expenses) != 2:
        _fail("expected one corrected Expense pair")
    original = next((item for item in expenses if item.description == "Fictional August premises estimate"), None)
    replacement = next((item for item in expenses if item.description == "Fictional August premises correction"), None)
    if (
        original is None
        or replacement is None
        or original.date != date(2026, 8, 5)
        or original.category != Expense.Category.RENT
        or original.amount != Decimal("250000.00")
        or original.notes != "Fictional demo expense only."
        or original.actor_id != staff.pk
        or original.status != Expense.Status.VOIDED
        or replacement.date != date(2026, 8, 5)
        or replacement.category != Expense.Category.RENT
        or replacement.amount != Decimal("275000.00")
        or replacement.notes != "Corrected fictional demo expense only."
        or replacement.actor_id != owner.pk
        or replacement.status != Expense.Status.RECORDED
        or replacement.correction_of_id != original.pk
    ):
        _fail("Expense correction drifted")

    adjustments = list(StockAdjustment.objects.filter(business=business))
    if len(adjustments) != 6:
        _fail("expected five opening adjustments and one manual adjustment")
    opening = [item for item in adjustments if item.reason == StockAdjustment.Reason.OPENING]
    expected_opening = {details["sku"]: details["opening_quantity"] for details in _PRODUCTS}
    if len(opening) != 5 or {
        item.product.sku: (item.quantity_change, item.actor_id, item.notes)
        for item in opening
    } != {
        sku: (quantity, owner.pk, "Opening quantity recorded during Product creation.")
        for sku, quantity in expected_opening.items()
    }:
        _fail("opening Stock Adjustments drifted")
    manual = [item for item in adjustments if item.reason == StockAdjustment.Reason.FOUND]
    if (
        len(manual) != 1
        or manual[0].quantity_change != 2
        or manual[0].product.sku != "DEMO-KOR-100"
        or manual[0].actor_id != staff.pk
        or manual[0].notes != "Two fictional sachets found during the Friday count."
        or manual[0].business_id != business.pk
    ):
        _fail("manual Stock Adjustment drifted")

    movements = list(StockMovement.objects.filter(business=business))
    if len(movements) != 18:
        _fail("expected exactly eighteen immutable Stock Movements")
    movement_by_purchase_line = {}
    movement_by_sale_line = {}
    movement_by_adjustment = {}
    for movement in movements:
        if movement.business_id != business.pk or movement.actor_id not in (owner.pk, staff.pk):
            _fail("Stock Movement ownership or actor drifted")
        if movement.kind == StockMovement.Kind.PURCHASE:
            if movement.purchase_line_id is None or movement.sale_line_id or movement.stock_adjustment_id or movement.reversal_of_id:
                _fail("Purchase movement provenance drifted")
            movement_by_purchase_line[movement.purchase_line_id] = movement
        elif movement.kind == StockMovement.Kind.SALE:
            if movement.sale_line_id is None or movement.purchase_line_id or movement.stock_adjustment_id or movement.reversal_of_id:
                _fail("Sale movement provenance drifted")
            movement_by_sale_line[movement.sale_line_id] = movement
        elif movement.kind == StockMovement.Kind.ADJUSTMENT:
            if movement.stock_adjustment_id is None or movement.purchase_line_id or movement.sale_line_id or movement.reversal_of_id:
                _fail("Adjustment movement provenance drifted")
            movement_by_adjustment[movement.stock_adjustment_id] = movement
        elif movement.kind == StockMovement.Kind.REVERSAL:
            if movement.reversal_of_id is None or movement.purchase_line_id or movement.sale_line_id or movement.stock_adjustment_id:
                _fail("Reversal movement provenance drifted")
        else:
            _fail("unexpected Stock Movement kind")
    for purchase in purchases:
        for line in purchase.lines.select_related("product"):
            movement = movement_by_purchase_line.get(line.pk)
            if movement is None or movement.product_id != line.product_id or movement.quantity_change != line.quantity or movement.actor_id != staff.pk:
                _fail(f"Purchase movement drifted for {purchase.reference}")
            reversal = StockMovement.objects.filter(reversal_of=movement).first()
            if purchase.status == Purchase.Status.VOIDED:
                if reversal is None or reversal.quantity_change != -line.quantity or reversal.actor_id != owner.pk:
                    _fail(f"Purchase reversal drifted for {purchase.reference}")
            elif reversal is not None:
                _fail(f"unexpected Purchase reversal for {purchase.reference}")
    for sale in sales:
        for line in sale.lines.select_related("product"):
            movement = movement_by_sale_line.get(line.pk)
            if movement is None or movement.product_id != line.product_id or movement.quantity_change != -line.quantity or movement.actor_id != staff.pk:
                _fail(f"Sale movement drifted for {sale.reference}")
            reversal = StockMovement.objects.filter(reversal_of=movement).first()
            if sale.status == Sale.Status.VOIDED:
                if reversal is None or reversal.quantity_change != line.quantity or reversal.actor_id != owner.pk:
                    _fail(f"Sale reversal drifted for {sale.reference}")
            elif reversal is not None:
                _fail(f"unexpected Sale reversal for {sale.reference}")
    for adjustment in adjustments:
        movement = movement_by_adjustment.get(adjustment.pk)
        if movement is None or movement.product_id != adjustment.product_id or movement.quantity_change != adjustment.quantity_change or movement.actor_id != adjustment.actor_id:
            _fail("Stock Adjustment movement provenance drifted")
    net_by_product = Counter()
    for movement in movements:
        net_by_product[movement.product_id] += movement.quantity_change
    for product in products:
        if net_by_product[product.pk] != product.stock_on_hand:
            _fail(f"Stock Movement reconciliation failed for {product.sku}")

    expected_events = [("business.created", owner.pk, "businesses.Business", str(business.pk))]
    expected_events.append(("membership.staff_added", owner.pk, "businesses.Membership", str(by_user[staff.pk].pk)))
    expected_events.extend(("product.created", owner.pk, "catalogue.Product", str(product.pk)) for product in products)
    expected_events.append(("product.deactivated", owner.pk, "catalogue.Product", str(product_by_sku["DEMO-PAP-090"].pk)))
    expected_events.extend(("purchase.completed", staff.pk, "purchases.Purchase", str(purchase.pk)) for purchase in purchases)
    expected_events.append(("purchase.voided", owner.pk, "purchases.Purchase", str(purchase_by_reference["DEMO-PUR-VOID"].pk)))
    expected_events.extend(("sale.completed", staff.pk, "sales.Sale", str(sale.pk)) for sale in sales)
    expected_events.append(("sale.voided", owner.pk, "sales.Sale", str(sale_by_reference["DEMO-SAL-VOID"].pk)))
    expected_events.append(("expense.recorded", staff.pk, "expenses.Expense", str(original.pk)))
    expected_events.append(("expense.corrected", owner.pk, "expenses.Expense", str(replacement.pk)))
    expected_events.append(("stock.adjusted", staff.pk, "inventory.StockAdjustment", str(manual[0].pk)))
    actual_events = [
        (event.action, event.actor_id, event.object_type, event.object_identifier)
        for event in AuditEvent.objects.filter(business=business)
    ]
    if Counter(actual_events) != Counter(expected_events):
        _fail("Audit Event attribution or affected-object identity drifted")


@transaction.atomic
def seed_demo_business():
    """Create or verify the canonical Demo Business and reset its credentials.

    The first run is one transaction. Existing state is validated completely
    before either named user's password is reset, so drift failures cannot
    partially change credentials.
    """
    user_model = get_user_model()
    business_matches = list(
        Business.objects.select_for_update()
        .filter(name=DEMO_BUSINESS_NAME)
        .order_by("pk")
    )
    owner = user_model.objects.select_for_update().filter(email__iexact=DEMO_OWNER_EMAIL).first()
    staff = user_model.objects.select_for_update().filter(email__iexact=DEMO_STAFF_EMAIL).first()

    if not business_matches and owner is None and staff is None:
        owner = user_model.objects.create_user(
            email=DEMO_OWNER_EMAIL,
            password=DEMO_OWNER_PASSWORD,
            first_name="Adaeze",
            last_name="Demo",
        )
        staff = user_model.objects.create_user(
            email=DEMO_STAFF_EMAIL,
            password=DEMO_STAFF_PASSWORD,
            first_name="Bayo",
            last_name="Sample",
        )
        return _create_canonical_dataset(owner=owner, staff=staff)

    if len(business_matches) != 1 or owner is None or staff is None:
        _fail("canonical Business and both named users must be present together")
    business = business_matches[0]
    if (
        owner.email != DEMO_OWNER_EMAIL
        or owner.first_name != "Adaeze"
        or owner.last_name != "Demo"
        or not owner.is_active
        or owner.is_staff
        or owner.is_superuser
    ):
        _fail("Demo Owner identity drifted")
    if (
        staff.email != DEMO_STAFF_EMAIL
        or staff.first_name != "Bayo"
        or staff.last_name != "Sample"
        or not staff.is_active
        or staff.is_staff
        or staff.is_superuser
    ):
        _fail("Demo Staff Member identity drifted")
    if Membership.objects.filter(user__in=(owner, staff)).exclude(business=business).exists():
        _fail("a named demo user belongs to another Business")
    _verify_canonical_dataset(business=business, owner=owner, staff=staff)

    owner.set_password(DEMO_OWNER_PASSWORD)
    owner.save(update_fields=["password"])
    staff.set_password(DEMO_STAFF_PASSWORD)
    staff.save(update_fields=["password"])
    return business

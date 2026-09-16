from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone

from catalogue.models import Product
from inventory.models import StockMovement
from reports.filters import month_bounds_for_date, parse_inclusive_date_range


LAGOS = ZoneInfo("Africa/Lagos")
REPORTABLE_KINDS = ("all",) + tuple(value for value, _ in StockMovement.Kind.choices)


def current_month_bounds():
    return month_bounds_for_date(timezone.localtime(timezone.now(), LAGOS).date())


@dataclass(frozen=True)
class MovementReportFilters:
    kind: str
    product_id: int | None
    date_from: date | None
    date_to: date | None
    errors: tuple[str, ...] = ()
    kind_input: str = ""
    product_input: str = ""
    date_from_input: str = ""
    date_to_input: str = ""

    @classmethod
    def from_query_params(cls, query_params, *, business=None):
        kind_input = query_params.get("kind") or "all"
        errors = []
        if kind_input not in REPORTABLE_KINDS:
            errors.append("Choose all, adjustment, purchase, sale, or reversal movements.")

        product_input = query_params.get("product") or ""
        product_id = None
        if product_input:
            try:
                product_id = int(product_input)
            except (TypeError, ValueError):
                product_id = None
            if product_id is None or product_id <= 0:
                errors.append("Choose a Product from this Business.")
            elif business is not None and not Product.objects.filter(
                pk=product_id, business=business
            ).exists():
                errors.append("Choose a Product from this Business.")

        date_range = parse_inclusive_date_range(
            query_params, default_bounds=current_month_bounds
        )
        return cls(
            kind=kind_input,
            product_id=product_id,
            date_from=date_range.date_from,
            date_to=date_range.date_to,
            errors=tuple(errors) + date_range.errors,
            kind_input=kind_input,
            product_input=product_input,
            date_from_input=date_range.date_from_input,
            date_to_input=date_range.date_to_input,
        )

    @property
    def is_valid(self):
        return not self.errors

    @property
    def query_params(self):
        params = {"kind": self.kind}
        if self.product_id:
            params["product"] = self.product_id
        if self.date_from:
            params["date_from"] = self.date_from.isoformat()
        if self.date_to:
            params["date_to"] = self.date_to.isoformat()
        return params

    @property
    def query_string(self):
        return urlencode(self.query_params)

    @property
    def kind_value(self):
        return self.kind_input or self.kind

    @property
    def kind_is_invalid(self):
        return self.kind not in REPORTABLE_KINDS

    @property
    def product_value(self):
        return self.product_input

    @property
    def product_is_invalid(self):
        return bool(self.product_input) and any(
            error == "Choose a Product from this Business." for error in self.errors
        )

    @property
    def date_from_value(self):
        return self.date_from_input or (
            self.date_from.isoformat() if self.date_from else ""
        )

    @property
    def date_to_value(self):
        return self.date_to_input or (
            self.date_to.isoformat() if self.date_to else ""
        )


def _local_start(value):
    return datetime.combine(value, time.min, tzinfo=LAGOS)


def _local_end(value):
    return _local_start(value + timedelta(days=1))


@dataclass(frozen=True)
class MovementReportRow:
    movement: StockMovement

    @property
    def product(self):
        return self.movement.product

    @property
    def sku(self):
        return self.product.sku or "No SKU"

    @property
    def kind_label(self):
        return self.movement.get_kind_display()

    @property
    def lagos_timestamp(self):
        return timezone.localtime(self.movement.created_at, LAGOS)

    @property
    def lagos_timestamp_display(self):
        return self.lagos_timestamp.strftime("%Y-%m-%d %H:%M:%S %z")

    @property
    def origin_label(self):
        movement = self.movement
        if movement.kind == StockMovement.Kind.ADJUSTMENT:
            return f"Stock Adjustment #{movement.stock_adjustment_id}"
        if movement.kind == StockMovement.Kind.PURCHASE:
            purchase = movement.purchase_line.purchase
            return purchase.reference or f"Purchase #{purchase.pk}"
        if movement.kind == StockMovement.Kind.SALE:
            sale = movement.sale_line.sale
            return sale.reference or f"Sale #{sale.pk}"
        original = movement.reversal_of
        if original.kind == StockMovement.Kind.PURCHASE:
            purchase = original.purchase_line.purchase
            return f"Reversal of voided Purchase {purchase.reference or f'#{purchase.pk}'}"
        sale = original.sale_line.sale
        return f"Reversal of voided Sale {sale.reference or f'#{sale.pk}'}"

    @property
    def origin_url(self):
        movement = self.movement
        if movement.kind == StockMovement.Kind.ADJUSTMENT:
            return reverse("adjustment_detail", args=[movement.stock_adjustment_id])
        if movement.kind == StockMovement.Kind.PURCHASE:
            return reverse("purchase_detail", args=[movement.purchase_line.purchase_id])
        if movement.kind == StockMovement.Kind.SALE:
            return reverse("sale_detail", args=[movement.sale_line.sale_id])
        original = movement.reversal_of
        if original.kind == StockMovement.Kind.PURCHASE:
            return reverse("purchase_detail", args=[original.purchase_line.purchase_id])
        return reverse("sale_detail", args=[original.sale_line.sale_id])


@dataclass(frozen=True)
class MovementReport:
    filters: MovementReportFilters
    rows: tuple[MovementReportRow, ...]
    net_change: int
    products: tuple[Product, ...]


def build_movement_report(*, business, filters):
    products = tuple(Product.objects.filter(business=business).order_by("name", "pk"))
    product_error = "Choose a Product from this Business."
    if (
        filters.product_id
        and not any(product.pk == filters.product_id for product in products)
        and product_error not in filters.errors
    ):
        filters = replace(
            filters,
            errors=filters.errors + (product_error,),
        )
    if not filters.is_valid:
        return MovementReport(filters=filters, rows=(), net_change=0, products=products)

    movements = StockMovement.objects.filter(business=business)
    if filters.kind != "all":
        movements = movements.filter(kind=filters.kind)
    if filters.product_id:
        movements = movements.filter(product_id=filters.product_id)
    if filters.date_from:
        movements = movements.filter(created_at__gte=_local_start(filters.date_from))
    if filters.date_to:
        movements = movements.filter(created_at__lt=_local_end(filters.date_to))

    movements = movements.select_related(
        "product",
        "stock_adjustment",
        "purchase_line__purchase",
        "sale_line__sale",
        "reversal_of__purchase_line__purchase",
        "reversal_of__sale_line__sale",
    )
    rows = tuple(MovementReportRow(movement=movement) for movement in movements)
    return MovementReport(
        filters=filters,
        rows=rows,
        net_change=sum(row.movement.quantity_change for row in rows),
        products=products,
    )

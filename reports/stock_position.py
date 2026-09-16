from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode

from django.db.models import F

from catalogue.models import Product


MONEY_PLACES = Decimal("0.01")
PRODUCT_STATUSES = ("active", "inactive", "all")
STOCK_STATES = ("positive", "low", "zero", "all")


def money(value):
    return value.quantize(MONEY_PLACES)


@dataclass(frozen=True)
class StockPositionReportFilters:
    product_status: str
    stock_state: str
    errors: tuple[str, ...] = ()

    @classmethod
    def from_query_params(cls, query_params):
        product_status = query_params.get("product_status") or "all"
        stock_state = query_params.get("stock_state") or "positive"
        errors = []
        if product_status not in PRODUCT_STATUSES:
            errors.append("Choose active, inactive, or all Products.")
        if stock_state not in STOCK_STATES:
            errors.append("Choose positive, low, zero, or all stock.")
        return cls(
            product_status=product_status,
            stock_state=stock_state,
            errors=tuple(errors),
        )

    @property
    def is_valid(self):
        return not self.errors

    @property
    def query_params(self):
        return {
            "product_status": self.product_status,
            "stock_state": self.stock_state,
        }

    @property
    def query_string(self):
        return urlencode(self.query_params)


@dataclass(frozen=True)
class StockPositionReportRow:
    product: Product
    value: Decimal

    @property
    def sku(self):
        return self.product.sku or "No SKU"

    @property
    def active_state(self):
        return "Active" if self.product.is_active else "Inactive"


@dataclass(frozen=True)
class StockPositionReport:
    filters: StockPositionReportFilters
    rows: tuple[StockPositionReportRow, ...]
    total: Decimal


def build_stock_position_report(*, business, filters):
    """Return one current, Business-scoped stock snapshot for both presenters."""
    if not filters.is_valid:
        return StockPositionReport(filters=filters, rows=(), total=Decimal("0.00"))

    products = Product.objects.for_business(business)
    if filters.product_status == "active":
        products = products.filter(is_active=True)
    elif filters.product_status == "inactive":
        products = products.filter(is_active=False)

    if filters.stock_state == "positive":
        products = products.filter(stock_on_hand__gt=0)
    elif filters.stock_state == "low":
        products = products.filter(stock_on_hand__lte=F("low_stock_threshold"))
    elif filters.stock_state == "zero":
        products = products.filter(stock_on_hand=0)

    rows = tuple(
        StockPositionReportRow(
            product=product,
            value=money(product.stock_on_hand * product.unit_cost),
        )
        for product in products
    )
    return StockPositionReport(
        filters=filters,
        rows=rows,
        total=money(sum((row.value for row in rows), Decimal("0.00"))),
    )

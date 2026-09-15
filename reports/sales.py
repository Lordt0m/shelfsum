from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from django.utils.dateparse import parse_date

from sales.models import Sale


MONEY_PLACES = Decimal("0.01")
REPORTABLE_STATUSES = (Sale.Status.COMPLETED, Sale.Status.VOIDED)


def money(value):
    return value.quantize(MONEY_PLACES)


@dataclass(frozen=True)
class SalesReportFilters:
    status: str
    date_from: date | None
    date_to: date | None
    errors: tuple[str, ...] = ()

    @classmethod
    def from_query_params(cls, query_params):
        errors = []
        status = query_params.get("status") or Sale.Status.COMPLETED
        if status not in REPORTABLE_STATUSES:
            errors.append("Choose completed or voided Sales.")
        date_from = cls._parse_date(query_params.get("date_from"), "Enter a valid start date.", errors)
        date_to = cls._parse_date(query_params.get("date_to"), "Enter a valid end date.", errors)
        if date_from and date_to and date_to < date_from:
            errors.append("End date cannot be earlier than start date.")
        return cls(status=status, date_from=date_from, date_to=date_to, errors=tuple(errors))

    @staticmethod
    def _parse_date(value, error_message, errors):
        if not value:
            return None
        parsed = parse_date(value)
        if parsed is None:
            errors.append(error_message)
        return parsed

    @property
    def is_valid(self):
        return not self.errors

    @property
    def query_params(self):
        params = {"status": self.status}
        if self.date_from:
            params["date_from"] = self.date_from.isoformat()
        if self.date_to:
            params["date_to"] = self.date_to.isoformat()
        return params

    @property
    def query_string(self):
        return urlencode(self.query_params)


@dataclass(frozen=True)
class SalesReportRow:
    sale: Sale
    revenue: Decimal
    cost_of_goods_sold: Decimal
    gross_margin: Decimal

    @property
    def customer(self):
        return self.sale.customer_name or "Walk-in customer"

    @property
    def stable_reference(self):
        return self.sale.reference or f"Sale #{self.sale.pk}"


@dataclass(frozen=True)
class SalesReport:
    filters: SalesReportFilters
    rows: tuple[SalesReportRow, ...]
    revenue: Decimal
    cost_of_goods_sold: Decimal
    gross_margin: Decimal

    @property
    def has_active_totals(self):
        return self.filters.status == Sale.Status.COMPLETED


def build_sales_report(*, business, filters):
    """Return one scoped Sales result used by both HTML and CSV presenters."""
    if not filters.is_valid:
        return SalesReport(filters=filters, rows=(), revenue=Decimal("0.00"), cost_of_goods_sold=Decimal("0.00"), gross_margin=Decimal("0.00"))

    sales = Sale.objects.filter(business=business, status=filters.status)
    if filters.date_from:
        sales = sales.filter(sale_date__gte=filters.date_from)
    if filters.date_to:
        sales = sales.filter(sale_date__lte=filters.date_to)

    rows = []
    for sale in sales.prefetch_related("lines"):
        revenue = money(sum((line.quantity * line.unit_price for line in sale.lines.all()), Decimal("0.00")))
        cost_of_goods_sold = money(sum((line.quantity * line.cost_snapshot for line in sale.lines.all() if line.cost_snapshot is not None), Decimal("0.00")))
        rows.append(SalesReportRow(sale=sale, revenue=revenue, cost_of_goods_sold=cost_of_goods_sold, gross_margin=money(revenue - cost_of_goods_sold)))

    active_rows = rows if filters.status == Sale.Status.COMPLETED else ()
    revenue = money(sum((row.revenue for row in active_rows), Decimal("0.00")))
    cost_of_goods_sold = money(sum((row.cost_of_goods_sold for row in active_rows), Decimal("0.00")))
    return SalesReport(filters=filters, rows=tuple(rows), revenue=revenue, cost_of_goods_sold=cost_of_goods_sold, gross_margin=money(revenue - cost_of_goods_sold))

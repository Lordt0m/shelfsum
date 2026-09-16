from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from django.utils import timezone

from purchases.models import Purchase
from reports.filters import month_bounds_for_date, parse_inclusive_date_range


MONEY_PLACES = Decimal("0.01")
REPORTABLE_STATUSES = (Purchase.Status.COMPLETED, Purchase.Status.VOIDED)


def money(value):
    return value.quantize(MONEY_PLACES)


def current_month_bounds():
    return month_bounds_for_date(timezone.localdate())


@dataclass(frozen=True)
class PurchaseReportFilters:
    status: str
    date_from: date | None
    date_to: date | None
    errors: tuple[str, ...] = ()
    date_from_input: str = ""
    date_to_input: str = ""

    @classmethod
    def from_query_params(cls, query_params):
        status = query_params.get("status") or Purchase.Status.COMPLETED
        status_errors = () if status in REPORTABLE_STATUSES else (
            "Choose completed or voided Purchases.",
        )
        date_range = parse_inclusive_date_range(
            query_params, default_bounds=current_month_bounds
        )
        return cls(
            status=status,
            date_from=date_range.date_from,
            date_to=date_range.date_to,
            errors=status_errors + date_range.errors,
            date_from_input=date_range.date_from_input,
            date_to_input=date_range.date_to_input,
        )

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


@dataclass(frozen=True)
class PurchaseReportRow:
    purchase: Purchase
    total: Decimal

    @property
    def stable_reference(self):
        return self.purchase.reference or f"Purchase #{self.purchase.pk}"

    @property
    def supplier(self):
        return self.purchase.supplier_name or "No supplier recorded"


@dataclass(frozen=True)
class PurchaseReport:
    filters: PurchaseReportFilters
    rows: tuple[PurchaseReportRow, ...]
    total: Decimal

    @property
    def has_active_totals(self):
        return self.filters.status == Purchase.Status.COMPLETED


def build_purchase_report(*, business, filters):
    """Return one Business-scoped Purchase result used by HTML and CSV."""
    if not filters.is_valid:
        return PurchaseReport(filters=filters, rows=(), total=Decimal("0.00"))

    purchases = Purchase.objects.filter(business=business, status=filters.status)
    if filters.date_from:
        purchases = purchases.filter(purchase_date__gte=filters.date_from)
    if filters.date_to:
        purchases = purchases.filter(purchase_date__lte=filters.date_to)

    rows = tuple(
        PurchaseReportRow(
            purchase=purchase,
            total=money(
                sum(
                    (line.quantity * line.unit_cost for line in purchase.lines.all()),
                    Decimal("0.00"),
                )
            ),
        )
        for purchase in purchases.prefetch_related("lines")
    )
    total = money(
        sum(
            (row.total for row in rows if filters.status == Purchase.Status.COMPLETED),
            Decimal("0.00"),
        )
    )
    return PurchaseReport(filters=filters, rows=rows, total=total)

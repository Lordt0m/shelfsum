from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from django.utils import timezone

from expenses.models import Expense
from reports.filters import month_bounds_for_date, parse_inclusive_date_range


MONEY_PLACES = Decimal("0.01")
REPORTABLE_STATUSES = (Expense.Status.RECORDED, Expense.Status.VOIDED)


def money(value):
    return value.quantize(MONEY_PLACES)


def current_month_bounds():
    return month_bounds_for_date(timezone.localdate())


@dataclass(frozen=True)
class ExpenseReportFilters:
    status: str
    date_from: date | None
    date_to: date | None
    errors: tuple[str, ...] = ()
    date_from_input: str = ""
    date_to_input: str = ""

    @classmethod
    def from_query_params(cls, query_params):
        status = query_params.get("status") or Expense.Status.RECORDED
        status_errors = () if status in REPORTABLE_STATUSES else (
            "Choose recorded or voided Expenses.",
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
class ExpenseReportRow:
    expense: Expense

    @property
    def stable_reference(self):
        return f"Expense #{self.expense.pk}"

    @property
    def category(self):
        return self.expense.get_category_display()


@dataclass(frozen=True)
class ExpenseReport:
    filters: ExpenseReportFilters
    rows: tuple[ExpenseReportRow, ...]
    total: Decimal

    @property
    def has_active_totals(self):
        return self.filters.status == Expense.Status.RECORDED


def build_expense_report(*, business, filters):
    """Return one Business-scoped Expense result used by both presenters."""
    if not filters.is_valid:
        return ExpenseReport(filters=filters, rows=(), total=Decimal("0.00"))

    expenses = Expense.objects.filter(business=business, status=filters.status)
    if filters.date_from:
        expenses = expenses.filter(date__gte=filters.date_from)
    if filters.date_to:
        expenses = expenses.filter(date__lte=filters.date_to)

    rows = tuple(ExpenseReportRow(expense=expense) for expense in expenses)
    total = money(
        sum(
            (row.expense.amount for row in rows if filters.status == Expense.Status.RECORDED),
            Decimal("0.00"),
        )
    )
    return ExpenseReport(filters=filters, rows=rows, total=total)

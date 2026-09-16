from django.shortcuts import render

from businesses.access import membership_required
from reports.csv import csv_response, safe_csv_text
from reports.expense import ExpenseReportFilters, build_expense_report
from reports.purchase import PurchaseReportFilters, build_purchase_report
from reports.sales import SalesReportFilters, build_sales_report
from reports.stock_position import (
    StockPositionReportFilters,
    build_stock_position_report,
)
from reports.movement import MovementReportFilters, build_movement_report


CSV_HEADINGS = ("Sale date", "Sale reference / ID", "Customer", "Status", "Revenue", "Estimated COGS", "Estimated gross margin")

_csv_text = safe_csv_text


def _sales_report(request):
    filters = SalesReportFilters.from_query_params(request.GET)
    return build_sales_report(business=request.business, filters=filters)


@membership_required
def sales_report(request):
    return render(request, "reports/sales_report.html", {"report": _sales_report(request)})


@membership_required
def sales_report_csv(request):
    report = _sales_report(request)
    return csv_response(
        headings=CSV_HEADINGS,
        filename="sales-report.csv",
        rows=(
            (
                row.sale.sale_date.isoformat(),
                safe_csv_text(row.stable_reference),
                safe_csv_text(row.customer),
                safe_csv_text(row.sale.get_status_display()),
                f"{row.revenue:.2f}",
                f"{row.cost_of_goods_sold:.2f}",
                f"{row.gross_margin:.2f}",
            )
            for row in report.rows
        ),
    )


PURCHASE_CSV_HEADINGS = (
    "Purchase date",
    "Purchase reference / ID",
    "Supplier",
    "Status",
    "Quantity by unit cost total",
)

STOCK_POSITION_CSV_HEADINGS = (
    "Product name",
    "SKU",
    "Active state",
    "Stock on Hand",
    "Current unit cost",
    "Current stock value",
)

MOVEMENT_CSV_HEADINGS = (
    "Lagos timestamp",
    "Product",
    "SKU",
    "Kind",
    "Quantity change",
    "Origin",
)


def _purchase_report(request):
    filters = PurchaseReportFilters.from_query_params(request.GET)
    return build_purchase_report(business=request.business, filters=filters)


@membership_required
def reports_index(request):
    return render(request, "reports/index.html")


def _expense_report(request):
    filters = ExpenseReportFilters.from_query_params(request.GET)
    return build_expense_report(business=request.business, filters=filters)


@membership_required
def expense_report(request):
    return render(
        request,
        "reports/expense_report.html",
        {"report": _expense_report(request)},
    )


EXPENSE_CSV_HEADINGS = (
    "Expense date",
    "Expense ID",
    "Category",
    "Description",
    "Status",
    "Amount",
)


@membership_required
def expense_report_csv(request):
    report = _expense_report(request)
    return csv_response(
        headings=EXPENSE_CSV_HEADINGS,
        filename="expenses-report.csv",
        rows=(
            (
                row.expense.date.isoformat(),
                safe_csv_text(row.stable_reference),
                safe_csv_text(row.category),
                safe_csv_text(row.expense.description),
                safe_csv_text(row.expense.get_status_display()),
                f"{row.expense.amount:.2f}",
            )
            for row in report.rows
        ),
    )


@membership_required
def purchase_report(request):
    return render(
        request,
        "reports/purchase_report.html",
        {"report": _purchase_report(request)},
    )


@membership_required
def purchase_report_csv(request):
    report = _purchase_report(request)
    return csv_response(
        headings=PURCHASE_CSV_HEADINGS,
        filename="purchases-report.csv",
        rows=(
            (
                row.purchase.purchase_date.isoformat(),
                safe_csv_text(row.stable_reference),
                safe_csv_text(row.supplier),
                safe_csv_text(row.purchase.get_status_display()),
                f"{row.total:.2f}",
            )
            for row in report.rows
        ),
    )


def _stock_position_report(request):
    filters = StockPositionReportFilters.from_query_params(request.GET)
    return build_stock_position_report(business=request.business, filters=filters)


@membership_required
def stock_position_report(request):
    return render(
        request,
        "reports/stock_position_report.html",
        {"report": _stock_position_report(request)},
    )


@membership_required
def stock_position_report_csv(request):
    report = _stock_position_report(request)
    return csv_response(
        headings=STOCK_POSITION_CSV_HEADINGS,
        filename="stock-position-report.csv",
        rows=(
            (
                safe_csv_text(row.product.name),
                safe_csv_text(row.sku),
                safe_csv_text(row.active_state),
                str(row.product.stock_on_hand),
                f"{row.product.unit_cost:.2f}",
                f"{row.value:.2f}",
            )
            for row in report.rows
        ),
    )


def _movement_report(request):
    filters = MovementReportFilters.from_query_params(
        request.GET, business=request.business
    )
    return build_movement_report(business=request.business, filters=filters)


@membership_required
def movement_report(request):
    return render(
        request,
        "reports/movement_report.html",
        {"report": _movement_report(request)},
    )


@membership_required
def movement_report_csv(request):
    report = _movement_report(request)
    return csv_response(
        headings=MOVEMENT_CSV_HEADINGS,
        filename="product-movements-report.csv",
        rows=(
            (
                row.lagos_timestamp.isoformat(),
                safe_csv_text(row.product.name),
                safe_csv_text(row.sku),
                safe_csv_text(row.kind_label),
                str(row.movement.quantity_change),
                safe_csv_text(row.origin_label),
            )
            for row in report.rows
        ),
    )

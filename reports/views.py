import csv

from django.http import HttpResponse
from django.shortcuts import render

from businesses.access import membership_required
from reports.sales import SalesReportFilters, build_sales_report


CSV_HEADINGS = ("Sale date", "Sale reference / ID", "Customer", "Status", "Revenue", "Estimated COGS", "Estimated gross margin")


def _sales_report(request):
    filters = SalesReportFilters.from_query_params(request.GET)
    return build_sales_report(business=request.business, filters=filters)


@membership_required
def sales_report(request):
    return render(request, "reports/sales_report.html", {"report": _sales_report(request)})


def _csv_text(value):
    value = str(value)
    return f"'{value}" if value[:1] in {"=", "+", "-", "@"} else value


@membership_required
def sales_report_csv(request):
    report = _sales_report(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="sales-report.csv"'
    writer = csv.writer(response)
    writer.writerow(CSV_HEADINGS)
    for row in report.rows:
        writer.writerow((row.sale.sale_date.isoformat(), _csv_text(row.stable_reference), _csv_text(row.customer), _csv_text(row.sale.get_status_display()), f"{row.revenue:.2f}", f"{row.cost_of_goods_sold:.2f}", f"{row.gross_margin:.2f}"))
    return response

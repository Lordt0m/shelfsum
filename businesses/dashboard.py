from calendar import monthrange
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.urls import reverse
from django.utils import timezone

from auditing.models import AuditEvent
from catalogue.models import Product
from expenses.models import Expense
from sales.models import Sale, SaleLine


LAGOS = ZoneInfo("Africa/Lagos")
MONEY = DecimalField(max_digits=24, decimal_places=2)


def _total(queryset, expression):
    return queryset.aggregate(total=Sum(expression))["total"] or Decimal("0")


def _activity_link(event):
    routes = {
        "catalogue.Product": "product_detail",
        "purchases.Purchase": "purchase_detail",
        "sales.Sale": "sale_detail",
        "expenses.Expense": "expense_detail",
        "inventory.StockAdjustment": "adjustment_detail",
    }
    route = routes.get(event.object_type)
    return reverse(route, args=[event.object_identifier]) if route else None


def dashboard_context(*, business):
    """Return read-only, membership-scoped operational dashboard data."""
    today = timezone.localtime(timezone.now(), LAGOS).date()
    period_start = date(today.year, today.month, 1)
    period_end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    sale_lines = SaleLine.objects.filter(
        sale__business=business,
        sale__status=Sale.Status.COMPLETED,
        sale__sale_date__range=(period_start, period_end),
    )
    revenue = _total(
        sale_lines,
        ExpressionWrapper(F("quantity") * F("unit_price"), output_field=MONEY),
    )
    cost_of_goods_sold = _total(
        sale_lines,
        ExpressionWrapper(F("quantity") * F("cost_snapshot"), output_field=MONEY),
    )
    recorded_expenses = Expense.objects.filter(
        business=business,
        status=Expense.Status.RECORDED,
        date__range=(period_start, period_end),
    )
    expenses = _total(recorded_expenses, F("amount"))
    stock_value = _total(
        Product.objects.filter(business=business, stock_on_hand__gt=0),
        ExpressionWrapper(F("stock_on_hand") * F("unit_cost"), output_field=MONEY),
    )
    low_stock = Product.objects.filter(
        business=business,
        is_active=True,
        stock_on_hand__lte=F("low_stock_threshold"),
    )
    recent_activity = list(
        AuditEvent.objects.filter(business=business).select_related("actor")[:8]
    )
    for event in recent_activity:
        event.record_url = _activity_link(event)
    dates = f"date_from={period_start.isoformat()}&date_to={period_end.isoformat()}"
    return {
        "dashboard": {
            "period_start": period_start,
            "period_end": period_end,
            "revenue": revenue,
            "cost_of_goods_sold": cost_of_goods_sold,
            "expenses": expenses,
            "profit": revenue - cost_of_goods_sold - expenses,
            "stock_value": stock_value,
            "low_stock_count": low_stock.count(),
            "recent_activity": recent_activity,
            "sales_url": f'{reverse("sale_list")}?status=completed&{dates}',
            "expenses_url": f'{reverse("expense_list")}?status=recorded&{dates}',
            "low_stock_url": f'{reverse("product_list")}?status=active&stock=low',
        }
    }

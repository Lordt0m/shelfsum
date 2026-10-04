"""Read-only movement presentation; never writes a balance or ledger row."""

from zoneinfo import ZoneInfo

from django.db.models import Max, Min, OuterRef, Q, Subquery, Sum
from django.utils import timezone

from inventory.models import StockMovement


def movement_history_date_params(queryset):
    """Link a history list to its actual recorded date range, including older stock."""
    bounds = queryset.aggregate(first=Min("created_at"), last=Max("created_at"))
    lagos = ZoneInfo("Africa/Lagos")
    return {
        "date_from": timezone.localtime(bounds["first"], lagos).date().isoformat() if bounds["first"] else "",
        "date_to": timezone.localtime(bounds["last"], lagos).date().isoformat() if bounds["last"] else "",
    }


def movement_history_queryset(*, business):
    # Correlate against the COMPLETE product ledger before the caller applies
    # dates, kind filters or pagination. Timestamp ties are ordered by ID.
    preceding = (
        StockMovement.objects.filter(business=business, product_id=OuterRef("product_id"))
        .filter(Q(created_at__lt=OuterRef("created_at")) | Q(created_at=OuterRef("created_at"), pk__lte=OuterRef("pk")))
        .order_by().values("product_id").annotate(balance=Sum("quantity_change")).values("balance")
    )
    return StockMovement.objects.filter(business=business).annotate(
        ledger_balance=Subquery(preceding)
    ).select_related(
        "product", "actor", "stock_adjustment", "purchase_line__purchase",
        "sale_line__sale", "reversal", "reversal_of__purchase_line__purchase",
        "reversal_of__sale_line__sale",
    )

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from auditing.services import record_audit_event
from businesses.rules import ensure_business_write_allowed
from catalogue.models import Product
from inventory.models import StockAdjustment, StockMovement


@transaction.atomic
def _record_stock_adjustment(
    *, business, actor, product, quantity_change, reason, notes="", allow_opening=False
):
    ensure_business_write_allowed(business=business, actor=actor)
    if quantity_change == 0:
        raise ValidationError("A Stock Adjustment cannot have a zero quantity.")
    if isinstance(quantity_change, bool) or not isinstance(quantity_change, int):
        raise ValidationError("Stock Adjustment quantities must be whole numbers.")
    valid_reasons = {choice for choice, _ in StockAdjustment.Reason.choices}
    if reason not in valid_reasons:
        raise ValidationError("Choose a supported Stock Adjustment reason.")
    if reason == StockAdjustment.Reason.OPENING and not allow_opening:
        raise ValidationError("Opening stock is recorded when creating a Product.")
    if reason != StockAdjustment.Reason.OPENING and not product.is_active:
        raise ValidationError("Only active Products can receive Stock Adjustments.")
    if product.business_id != business.pk:
        raise ValidationError("The Product does not belong to this Business.")

    locked_product = Product.objects.select_for_update().get(
        pk=product.pk, business=business
    )
    if reason != StockAdjustment.Reason.OPENING and not locked_product.is_active:
        raise ValidationError("Only active Products can receive Stock Adjustments.")
    resulting_stock = locked_product.stock_on_hand + quantity_change
    if resulting_stock < 0:
        raise ValidationError("This change would make Stock on Hand negative.")

    adjustment = StockAdjustment.objects.create(
        business=business,
        product=locked_product,
        quantity_change=quantity_change,
        reason=reason,
        notes=notes,
        actor=actor,
    )
    Product.objects.filter(pk=locked_product.pk).update(
        stock_on_hand=F("stock_on_hand") + quantity_change
    )
    StockMovement.objects.create(
        business=business,
        product=locked_product,
        quantity_change=quantity_change,
        kind=StockMovement.Kind.ADJUSTMENT,
        stock_adjustment=adjustment,
        actor=actor,
    )
    locked_product.refresh_from_db(fields=["stock_on_hand"])
    if reason != StockAdjustment.Reason.OPENING:
        record_audit_event(
            business=business,
            actor=actor,
            action="stock.adjusted",
            affected_object=adjustment,
            summary=f"Adjusted {locked_product.name} by {quantity_change} units ({adjustment.get_reason_display()}).",
        )
    return adjustment


def record_stock_adjustment(
    *, business, actor, product, quantity_change, reason, notes=""
):
    """Record a deliberate post-creation Stock Adjustment."""
    return _record_stock_adjustment(
        business=business,
        actor=actor,
        product=product,
        quantity_change=quantity_change,
        reason=reason,
        notes=notes,
    )


def _record_opening_stock(*, business, actor, product, quantity_change, notes=""):
    """Internal catalogue-creation path for a Product's opening Stock."""
    return _record_stock_adjustment(
        business=business,
        actor=actor,
        product=product,
        quantity_change=quantity_change,
        reason=StockAdjustment.Reason.OPENING,
        notes=notes,
        allow_opening=True,
    )

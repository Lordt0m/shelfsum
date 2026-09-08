from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from businesses.rules import ensure_business_write_allowed
from catalogue.models import Product
from inventory.models import StockAdjustment, StockMovement


@transaction.atomic
def record_stock_adjustment(
    *, business, actor, product, quantity_change, reason, notes=""
):
    ensure_business_write_allowed(business=business, actor=actor)
    if quantity_change == 0:
        raise ValidationError("A Stock Adjustment cannot have a zero quantity.")
    if product.business_id != business.pk:
        raise ValidationError("The Product does not belong to this Business.")

    locked_product = Product.objects.select_for_update().get(
        pk=product.pk, business=business
    )
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
    return adjustment

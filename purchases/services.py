from django.core.exceptions import ValidationError
from django.db import transaction

from auditing.services import record_audit_event
from businesses.rules import ensure_business_write_allowed
from catalogue.models import Product
from inventory.models import StockMovement
from purchases.models import Purchase


@transaction.atomic
def complete_purchase(*, business, actor, purchase):
    """Complete one draft Purchase and record its entire stock trace atomically."""
    ensure_business_write_allowed(business=business, actor=actor)

    if purchase.business_id != business.pk:
        raise ValidationError("The Purchase does not belong to this Business.")

    locked_purchase = Purchase.objects.select_for_update().get(
        pk=purchase.pk, business=business
    )
    if locked_purchase.status != Purchase.Status.DRAFT:
        raise ValidationError("This Purchase has already been completed.")

    lines = list(locked_purchase.lines.all().order_by("product_id", "pk"))
    if not lines:
        raise ValidationError("A Purchase must contain at least one line.")
    if any(line.quantity <= 0 or line.unit_cost < 0 for line in lines):
        raise ValidationError(
            "Every line must have a positive whole quantity and non-negative unit cost."
        )

    product_ids = [line.product_id for line in lines]
    locked_products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=product_ids, business=business)
        .order_by("pk")
    }
    if len(locked_products) != len(set(product_ids)):
        raise ValidationError("Every line must reference a Product in this Business.")

    locked_purchase.status = Purchase.Status.COMPLETED
    locked_purchase._completion_authorized = True
    try:
        locked_purchase.save(update_fields=["status", "updated_at"])
    finally:
        del locked_purchase._completion_authorized

    for line in lines:
        product = locked_products[line.product_id]
        if not product.is_active:
            raise ValidationError(
                "Every line must reference an active Product in this Business."
            )

    for line in lines:
        product = locked_products[line.product_id]
        product.stock_on_hand += line.quantity
        product.unit_cost = line.unit_cost
        product.save(update_fields=["stock_on_hand", "unit_cost", "updated_at"])
        StockMovement.objects.create(
            business=business,
            product=product,
            quantity_change=line.quantity,
            kind=StockMovement.Kind.PURCHASE,
            purchase_line=line,
            actor=actor,
        )

    record_audit_event(
        business=business,
        actor=actor,
        action="purchase.completed",
        affected_object=locked_purchase,
        summary=f"Completed Purchase {locked_purchase.pk} for {locked_purchase.total}.",
    )
    return locked_purchase

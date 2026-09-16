from django.core.exceptions import ValidationError
from django.db import transaction

from auditing.services import record_audit_event
from businesses.rules import ensure_business_write_allowed
from catalogue.models import Product
from inventory.models import StockMovement
from purchases.models import Purchase
from purchases.models import PurchaseLine


def _lock_purchase(*, business, purchase_id):
    """Lock the Purchase parent before any edit, completion, or void work."""
    return Purchase.objects.select_for_update().get(pk=purchase_id, business=business)


def _lock_purchase_lines(*, purchase):
    """Lock existing lines in the same parent-first order as every writer."""
    return list(
        PurchaseLine.objects.select_for_update()
        .filter(purchase=purchase)
        .order_by("product_id", "pk")
    )


def _validated_draft_lines(*, business, formset):
    """Extract and recheck create intent against the explicit Business."""
    line_data = []
    for form in formset.forms:
        cleaned_data = getattr(form, "cleaned_data", None)
        if not cleaned_data or cleaned_data.get("DELETE"):
            continue
        product = cleaned_data.get("product")
        if product is None:
            continue
        line_data.append(
            (
                product.pk,
                cleaned_data.get("quantity"),
                cleaned_data.get("unit_cost"),
            )
        )

    if not line_data:
        raise ValidationError("Add at least one Product line.")

    products = {
        product.pk: product
        for product in Product.objects.filter(
            pk__in={product_id for product_id, _, _ in line_data},
            business=business,
        ).order_by("pk")
    }
    if len(products) != len({product_id for product_id, _, _ in line_data}):
        raise ValidationError("The Product must belong to this Business.")
    if any(not product.is_active for product in products.values()):
        raise ValidationError(
            "Every line must reference an active Product in this Business."
        )
    return line_data, products


@transaction.atomic
def create_draft_purchase(*, business, actor, form, formset):
    """Create a draft Purchase and its lines as one guarded transaction."""
    ensure_business_write_allowed(business=business, actor=actor)
    line_data, products = _validated_draft_lines(business=business, formset=formset)

    purchase = Purchase(
        business=business,
        creator=actor,
        status=Purchase.Status.DRAFT,
        **{field: form.cleaned_data[field] for field in form.Meta.fields},
    )
    purchase.save()
    for product_id, quantity, unit_cost in line_data:
        PurchaseLine.objects.create(
            purchase=purchase,
            product=products[product_id],
            quantity=quantity,
            unit_cost=unit_cost,
        )
    return purchase


@transaction.atomic
def save_draft_purchase(*, business, actor, purchase, form, formset):
    """Persist a validated draft edit without allowing a stale terminal write."""
    ensure_business_write_allowed(business=business, actor=actor)
    if purchase.business_id != business.pk:
        raise ValidationError("The Purchase does not belong to this Business.")

    locked_purchase = _lock_purchase(business=business, purchase_id=purchase.pk)
    if locked_purchase.status != Purchase.Status.DRAFT:
        raise ValidationError("This Purchase has already been completed.")

    # Completion, voiding, and editing all use parent then line locks.  A stale
    # formset therefore cannot write after a competing terminal transition.
    _lock_purchase_lines(purchase=locked_purchase)
    submitted_purchase = form.save(commit=False)
    for field in form.Meta.fields:
        setattr(locked_purchase, field, getattr(submitted_purchase, field))
    locked_purchase.save()
    formset.instance = locked_purchase
    formset.save()
    return locked_purchase


@transaction.atomic
def complete_purchase(*, business, actor, purchase):
    """Complete one draft Purchase and record its entire stock trace atomically."""
    ensure_business_write_allowed(business=business, actor=actor)

    if purchase.business_id != business.pk:
        raise ValidationError("The Purchase does not belong to this Business.")

    locked_purchase = _lock_purchase(business=business, purchase_id=purchase.pk)
    if locked_purchase.status != Purchase.Status.DRAFT:
        raise ValidationError("This Purchase has already been completed.")

    lines = _lock_purchase_lines(purchase=locked_purchase)
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


@transaction.atomic
def void_purchase(*, business, actor, purchase):
    """Void a completed Purchase by applying immutable reversing movements."""
    ensure_business_write_allowed(business=business, actor=actor)
    if purchase.business_id != business.pk:
        raise ValidationError("The Purchase does not belong to this Business.")

    locked_purchase = _lock_purchase(business=business, purchase_id=purchase.pk)
    if locked_purchase.status == Purchase.Status.VOIDED:
        raise ValidationError("This Purchase has already been voided.")
    if locked_purchase.status != Purchase.Status.COMPLETED:
        raise ValidationError("Only a completed Purchase can be voided.")

    lines = _lock_purchase_lines(purchase=locked_purchase)
    if not lines:
        raise ValidationError("A completed Purchase must contain lines.")
    movements = list(
        StockMovement.objects.select_for_update()
        .filter(purchase_line_id__in=[line.pk for line in lines])
        .order_by("product_id", "pk")
    )
    movement_by_line = {movement.purchase_line_id: movement for movement in movements}
    if len(movements) != len(lines) or set(movement_by_line) != {line.pk for line in lines}:
        raise ValidationError("The Purchase movement history is incomplete.")

    product_ids = sorted({line.product_id for line in lines})
    locked_products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=product_ids, business=business)
        .order_by("pk")
    }
    if len(locked_products) != len(product_ids):
        raise ValidationError("Every Purchase Product must belong to this Business.")
    for line in lines:
        product = locked_products[line.product_id]
        movement = movement_by_line[line.pk]
        if movement.kind != StockMovement.Kind.PURCHASE or movement.product_id != product.pk or movement.quantity_change != line.quantity:
            raise ValidationError("The Purchase movement history does not match its lines.")
        if product.stock_on_hand < line.quantity:
            raise ValidationError(
                f"Voiding this Purchase would make Stock on Hand negative for {product.name}."
            )

    # Reversal validation reads the persisted owner state, rather than trusting
    # a transient service flag.  Persist it only after all origin and stock
    # validations are complete so any following failure rolls it back.
    locked_purchase.status = Purchase.Status.VOIDED
    locked_purchase._void_authorized = True
    try:
        locked_purchase.save(update_fields=["status", "updated_at"])
    finally:
        del locked_purchase._void_authorized

    for line in lines:
        product = locked_products[line.product_id]
        StockMovement.objects.create(
            business=business,
            product=product,
            quantity_change=-line.quantity,
            kind=StockMovement.Kind.REVERSAL,
            reversal_of=movement_by_line[line.pk],
            actor=actor,
        )

    for line in lines:
        product = locked_products[line.product_id]
        product.stock_on_hand -= line.quantity
        product.save(update_fields=["stock_on_hand", "updated_at"])
    record_audit_event(
        business=business,
        actor=actor,
        action="purchase.voided",
        affected_object=locked_purchase,
        summary=f"Voided Purchase {locked_purchase.pk} for {locked_purchase.total}.",
    )
    return locked_purchase

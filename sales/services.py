from django.core.exceptions import ValidationError
from django.db import transaction

from auditing.services import record_audit_event
from businesses.rules import ensure_business_write_allowed
from catalogue.models import Product
from inventory.models import StockMovement
from sales.models import Sale, SaleLine


def _lock_sale(*, business, sale_id):
    """Return the Sale row locked before any draft mutation or completion."""
    return Sale.objects.select_for_update().get(pk=sale_id, business=business)


def _lock_sale_lines(*, sale):
    """Lock a Sale's existing lines after its parent, in a stable order."""
    return list(
        SaleLine.objects.select_for_update()
        .filter(sale=sale)
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
                cleaned_data.get("unit_price"),
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
def create_draft_sale(*, business, actor, form, formset):
    """Create a draft Sale and its lines as one guarded transaction."""
    ensure_business_write_allowed(business=business, actor=actor)
    line_data, products = _validated_draft_lines(business=business, formset=formset)

    sale = Sale(
        business=business,
        creator=actor,
        status=Sale.Status.DRAFT,
        **{field: form.cleaned_data[field] for field in form.Meta.fields},
    )
    sale.save()
    for product_id, quantity, unit_price in line_data:
        SaleLine.objects.create(
            sale=sale,
            product=products[product_id],
            quantity=quantity,
            unit_price=unit_price,
        )
    return sale


@transaction.atomic
def save_draft_sale(*, business, actor, sale, form, formset):
    """Persist an already-validated draft edit while serializing completion.

    Forms are intentionally validated before entering this short transaction.  The
    parent Sale is then locked and its state is rechecked before formset writes
    can alter any line, so a stale edit can never follow a completion.
    """
    ensure_business_write_allowed(business=business, actor=actor)
    if sale.business_id != business.pk:
        raise ValidationError("The Sale does not belong to this Business.")

    locked_sale = _lock_sale(business=business, sale_id=sale.pk)
    if locked_sale.status != Sale.Status.DRAFT:
        raise ValidationError("This Sale has already been completed.")

    # Completion and editing both acquire parent then line locks.  This avoids a
    # parent/child lock inversion while protecting formset updates and deletes.
    _lock_sale_lines(sale=locked_sale)
    submitted_sale = form.save(commit=False)
    for field in form.Meta.fields:
        setattr(locked_sale, field, getattr(submitted_sale, field))
    locked_sale.save()
    formset.instance = locked_sale
    formset.save()
    return locked_sale


@transaction.atomic
def complete_sale(*, business, actor, sale):
    """Complete a draft Sale with deterministic Product locks and an atomic ledger trace."""
    ensure_business_write_allowed(business=business, actor=actor)
    if sale.business_id != business.pk:
        raise ValidationError("The Sale does not belong to this Business.")
    locked_sale = _lock_sale(business=business, sale_id=sale.pk)
    if locked_sale.status != Sale.Status.DRAFT:
        raise ValidationError("This Sale has already been completed.")
    lines = _lock_sale_lines(sale=locked_sale)
    if not lines:
        raise ValidationError("A Sale must contain at least one line.")
    if any(line.quantity <= 0 or line.unit_price < 0 for line in lines):
        raise ValidationError("Every line must have a positive whole quantity and non-negative unit price.")
    product_ids = [line.product_id for line in lines]
    locked_products = {product.pk: product for product in Product.objects.select_for_update().filter(pk__in=product_ids, business=business).order_by("pk")}
    if len(locked_products) != len(set(product_ids)):
        raise ValidationError("Every line must reference a Product in this Business.")
    for line in lines:
        product = locked_products[line.product_id]
        if not product.is_active:
            raise ValidationError("Every line must reference an active Product in this Business.")
        if line.quantity > product.stock_on_hand:
            raise ValidationError(f"Insufficient available Stock on Hand for {product.name}.")
    for line in lines:
        line.cost_snapshot = locked_products[line.product_id].unit_cost
        line.save(update_fields=["cost_snapshot"])
    locked_sale.status = Sale.Status.COMPLETED
    locked_sale._completion_authorized = True
    try:
        locked_sale.save(update_fields=["status", "updated_at"])
    finally:
        del locked_sale._completion_authorized
    for line in lines:
        product = locked_products[line.product_id]
        product.stock_on_hand -= line.quantity
        product.save(update_fields=["stock_on_hand", "updated_at"])
        StockMovement.objects.create(business=business, product=product, quantity_change=-line.quantity, kind=StockMovement.Kind.SALE, sale_line=line, actor=actor)
    record_audit_event(business=business, actor=actor, action="sale.completed", affected_object=locked_sale, summary=f"Completed Sale {locked_sale.pk} for {locked_sale.total}.")
    return locked_sale


@transaction.atomic
def void_sale(*, business, actor, sale):
    """Void a completed Sale and restore its quantities via immutable reversals."""
    ensure_business_write_allowed(business=business, actor=actor)
    if sale.business_id != business.pk:
        raise ValidationError("The Sale does not belong to this Business.")
    locked_sale = _lock_sale(business=business, sale_id=sale.pk)
    if locked_sale.status == Sale.Status.VOIDED:
        raise ValidationError("This Sale has already been voided.")
    if locked_sale.status != Sale.Status.COMPLETED:
        raise ValidationError("Only a completed Sale can be voided.")

    lines = _lock_sale_lines(sale=locked_sale)
    if not lines:
        raise ValidationError("A completed Sale must contain lines.")
    movements = list(
        StockMovement.objects.select_for_update()
        .filter(sale_line_id__in=[line.pk for line in lines])
        .order_by("product_id", "pk")
    )
    movement_by_line = {movement.sale_line_id: movement for movement in movements}
    if len(movements) != len(lines) or set(movement_by_line) != {line.pk for line in lines}:
        raise ValidationError("The Sale movement history is incomplete.")

    product_ids = sorted({line.product_id for line in lines})
    locked_products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=product_ids, business=business)
        .order_by("pk")
    }
    if len(locked_products) != len(product_ids):
        raise ValidationError("Every Sale Product must belong to this Business.")
    for line in lines:
        movement = movement_by_line[line.pk]
        if movement.kind != StockMovement.Kind.SALE or movement.product_id != line.product_id or movement.quantity_change != -line.quantity:
            raise ValidationError("The Sale movement history does not match its lines.")

    # Reversal validation deliberately reads the persisted owning Sale state.
    # Make the authorized transition after all checks and locks, knowing the
    # enclosing transaction restores it if a reversal, stock update, or audit
    # write fails.
    locked_sale.status = Sale.Status.VOIDED
    locked_sale._void_authorized = True
    try:
        locked_sale.save(update_fields=["status", "updated_at"])
    finally:
        del locked_sale._void_authorized

    for line in lines:
        product = locked_products[line.product_id]
        StockMovement.objects.create(
            business=business,
            product=product,
            quantity_change=line.quantity,
            kind=StockMovement.Kind.REVERSAL,
            reversal_of=movement_by_line[line.pk],
            actor=actor,
        )

    for line in lines:
        product = locked_products[line.product_id]
        product.stock_on_hand += line.quantity
        product.save(update_fields=["stock_on_hand", "updated_at"])
    record_audit_event(
        business=business,
        actor=actor,
        action="sale.voided",
        affected_object=locked_sale,
        summary=f"Voided Sale {locked_sale.pk} for {locked_sale.total}.",
    )
    return locked_sale

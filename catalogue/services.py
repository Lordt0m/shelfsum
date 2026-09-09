from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from auditing.services import record_audit_event
from businesses.rules import ensure_business_write_allowed
from catalogue.models import Product
from inventory.models import StockAdjustment
from inventory.services import record_stock_adjustment


@dataclass(frozen=True)
class ProductCreation:
    name: str
    sku: str
    description: str
    selling_price: Decimal
    unit_cost: Decimal
    opening_quantity: int
    low_stock_threshold: int


@dataclass(frozen=True)
class ProductUpdate:
    name: str
    sku: str
    description: str
    selling_price: Decimal
    unit_cost: Decimal
    low_stock_threshold: int


def _locked_product_for_business(*, business, product):
    if product.business_id != business.pk:
        raise ValidationError("The Product does not belong to this Business.")
    return Product.objects.select_for_update().get(pk=product.pk, business=business)


@transaction.atomic
def create_product(*, business, actor, details):
    ensure_business_write_allowed(business=business, actor=actor)
    if details.selling_price < 0 or details.unit_cost < 0:
        raise ValidationError("Product money values cannot be negative.")
    if details.opening_quantity < 0 or details.low_stock_threshold < 0:
        raise ValidationError("Product quantities cannot be negative.")

    product = Product.objects.create(
        business=business,
        name=details.name,
        sku=details.sku,
        description=details.description,
        selling_price=details.selling_price,
        unit_cost=details.unit_cost,
        low_stock_threshold=details.low_stock_threshold,
    )
    if details.opening_quantity:
        record_stock_adjustment(
            business=business,
            actor=actor,
            product=product,
            quantity_change=details.opening_quantity,
            reason=StockAdjustment.Reason.OPENING,
            notes="Opening quantity recorded during Product creation.",
        )
        product.refresh_from_db(fields=["stock_on_hand"])

    record_audit_event(
        business=business,
        actor=actor,
        action="product.created",
        affected_object=product,
        summary=f"Created Product {product.name} with {product.stock_on_hand} units.",
    )
    return product


@transaction.atomic
def update_product(*, business, actor, product, details):
    ensure_business_write_allowed(business=business, actor=actor)
    if details.selling_price < 0 or details.unit_cost < 0:
        raise ValidationError("Product money values cannot be negative.")
    if details.low_stock_threshold < 0:
        raise ValidationError("Product quantities cannot be negative.")

    locked_product = _locked_product_for_business(
        business=business, product=product
    )
    locked_product.name = details.name
    locked_product.sku = details.sku
    locked_product.description = details.description
    locked_product.selling_price = details.selling_price
    locked_product.unit_cost = details.unit_cost
    locked_product.low_stock_threshold = details.low_stock_threshold
    locked_product.save()
    record_audit_event(
        business=business,
        actor=actor,
        action="product.updated",
        affected_object=locked_product,
        summary=f"Updated catalogue details for Product {locked_product.name}.",
    )
    return locked_product


@transaction.atomic
def deactivate_product(*, business, actor, product):
    ensure_business_write_allowed(business=business, actor=actor)
    locked_product = _locked_product_for_business(
        business=business, product=product
    )
    if not locked_product.is_active:
        return locked_product
    locked_product.is_active = False
    locked_product.save(update_fields=["is_active", "updated_at"])
    record_audit_event(
        business=business,
        actor=actor,
        action="product.deactivated",
        affected_object=locked_product,
        summary=f"Deactivated Product {locked_product.name}.",
    )
    return locked_product

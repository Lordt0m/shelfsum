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

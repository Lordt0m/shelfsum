from django.conf import settings
from django.db import models
from django.db.models import Q

from businesses.models import Business
from catalogue.models import Product
from core.models import ImmutableModel


class StockAdjustment(ImmutableModel):
    immutable_error = "Stock Adjustments are immutable."
    class Reason(models.TextChoices):
        OPENING = "opening", "Opening stock"
        DAMAGE = "damage", "Damaged stock"
        MISSING = "missing", "Missing stock"
        FOUND = "found", "Found stock"
        CORRECTION = "correction", "Count correction"

    business = models.ForeignKey(Business, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_adjustments")
    quantity_change = models.IntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    notes = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(quantity_change=0), name="nonzero_stock_adjustment"
            )
        ]


class StockMovement(ImmutableModel):
    immutable_error = "Stock Movements are immutable."

    class Kind(models.TextChoices):
        ADJUSTMENT = "adjustment", "Stock Adjustment"

    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="stock_movements")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_movements")
    quantity_change = models.IntegerField()
    kind = models.CharField(max_length=20, choices=Kind.choices)
    stock_adjustment = models.OneToOneField(
        StockAdjustment,
        on_delete=models.PROTECT,
        related_name="movement",
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.CheckConstraint(condition=~Q(quantity_change=0), name="nonzero_stock_movement")
        ]

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from businesses.models import Business
from catalogue.models import Product
from core.models import ImmutableModel, ImmutableQuerySet


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


class StockMovementQuerySet(ImmutableQuerySet):
    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        for movement in objs:
            movement.full_clean()
        return super().bulk_create(objs, *args, **kwargs)


class StockMovement(ImmutableModel):
    immutable_error = "Stock Movements are immutable."

    class Kind(models.TextChoices):
        ADJUSTMENT = "adjustment", "Stock Adjustment"
        PURCHASE = "purchase", "Purchase"

    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="stock_movements")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_movements")
    quantity_change = models.IntegerField()
    kind = models.CharField(max_length=20, choices=Kind.choices)
    stock_adjustment = models.OneToOneField(
        StockAdjustment,
        on_delete=models.PROTECT,
        related_name="movement",
        null=True,
        blank=True,
    )
    purchase_line = models.OneToOneField(
        "purchases.PurchaseLine",
        on_delete=models.PROTECT,
        related_name="movement",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = StockMovementQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=~Q(quantity_change=0), name="nonzero_stock_movement"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind="adjustment",
                        stock_adjustment__isnull=False,
                        purchase_line__isnull=True,
                    )
                    | Q(
                        kind="purchase",
                        stock_adjustment__isnull=True,
                        purchase_line__isnull=False,
                    )
                ),
                name="stock_movement_has_matching_origin",
            ),
        ]

    def clean(self):
        errors = {}

        def add_error(field, message):
            errors.setdefault(field, []).append(message)

        if self.kind == self.Kind.PURCHASE:
            if self.purchase_line_id is None:
                add_error("purchase_line", "Purchase movements require a Purchase line.")
            if self.stock_adjustment_id is not None:
                add_error(
                    "stock_adjustment",
                    "Purchase movements cannot also reference a Stock Adjustment.",
                )
            if self.purchase_line_id is not None:
                try:
                    purchase_line = self.purchase_line
                except self._meta.get_field("purchase_line").related_model.DoesNotExist:
                    add_error("purchase_line", "Purchase line does not exist.")
                else:
                    purchase = purchase_line.purchase
                    if purchase.status != purchase.Status.COMPLETED:
                        add_error(
                            "purchase_line",
                            "Purchase movements require a completed Purchase.",
                        )
                    if self.business_id != purchase.business_id:
                        add_error(
                            "business",
                            "Purchase movement Business must match its Purchase.",
                        )
                    if self.product_id != purchase_line.product_id:
                        add_error(
                            "product",
                            "Purchase movement Product must match its Purchase line.",
                        )
                    if self.quantity_change != purchase_line.quantity:
                        add_error(
                            "quantity_change",
                            "Purchase movement quantity must match its Purchase line.",
                        )
        elif self.kind == self.Kind.ADJUSTMENT:
            if self.stock_adjustment_id is None:
                add_error(
                    "stock_adjustment", "Adjustment movements require a Stock Adjustment."
                )
            if self.purchase_line_id is not None:
                add_error(
                    "purchase_line",
                    "Adjustment movements cannot also reference a Purchase line.",
                )
            if self.stock_adjustment_id is not None:
                try:
                    adjustment = self.stock_adjustment
                except StockAdjustment.DoesNotExist:
                    add_error("stock_adjustment", "Stock Adjustment does not exist.")
                else:
                    if self.business_id != adjustment.business_id:
                        add_error(
                            "business",
                            "Adjustment movement Business must match its Stock Adjustment.",
                        )
                    if self.product_id != adjustment.product_id:
                        add_error(
                            "product",
                            "Adjustment movement Product must match its Stock Adjustment.",
                        )
                    if self.quantity_change != adjustment.quantity_change:
                        add_error(
                            "quantity_change",
                            "Adjustment movement quantity must match its Stock Adjustment.",
                        )
        else:
            add_error("kind", "Stock movements require a supported origin kind.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.full_clean()
        return super().save(*args, **kwargs)

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from businesses.models import Business
from catalogue.models import Product
from core.models import ImmutableModel, ImmutableQuerySet


class StockAdjustmentQuerySet(ImmutableQuerySet):
    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        for adjustment in objs:
            adjustment._validate_quantity_change()
            adjustment.full_clean()
        return super().bulk_create(objs, *args, **kwargs)


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

    objects = StockAdjustmentQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(quantity_change=0), name="nonzero_stock_adjustment"
            )
        ]

    def save(self, *args, **kwargs):
        if self._state.adding:
            self._validate_quantity_change()
            self.full_clean()
        return super().save(*args, **kwargs)

    def _validate_quantity_change(self):
        if isinstance(self.quantity_change, bool) or not isinstance(
            self.quantity_change, int
        ):
            raise ValidationError(
                {"quantity_change": "Stock Adjustment quantities must be whole numbers."}
            )

    def clean(self):
        errors = {}
        if isinstance(self.quantity_change, bool) or not isinstance(self.quantity_change, int):
            errors["quantity_change"] = "Stock Adjustment quantities must be whole numbers."
        if self.quantity_change == 0:
            errors["quantity_change"] = "A Stock Adjustment cannot have a zero quantity."
        if self.product_id and self.business_id:
            try:
                if Product.objects.only("business_id").get(pk=self.product_id).business_id != self.business_id:
                    errors["product"] = "The Product must belong to this Business."
            except Product.DoesNotExist:
                errors["product"] = "The Product does not exist."
        if errors:
            raise ValidationError(errors)


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
        SALE = "sale", "Sale"
        REVERSAL = "reversal", "Reversal"

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
    sale_line = models.OneToOneField(
        "sales.SaleLine",
        on_delete=models.PROTECT,
        related_name="movement",
        null=True,
        blank=True,
    )
    reversal_of = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        related_name="reversal",
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
                        sale_line__isnull=True,
                        reversal_of__isnull=True,
                    )
                    | Q(
                        kind="purchase",
                        stock_adjustment__isnull=True,
                        purchase_line__isnull=False,
                        sale_line__isnull=True,
                        reversal_of__isnull=True,
                    )
                    | Q(
                        kind="sale",
                        stock_adjustment__isnull=True,
                        purchase_line__isnull=True,
                        sale_line__isnull=False,
                        reversal_of__isnull=True,
                    )
                    | Q(
                        kind="reversal",
                        stock_adjustment__isnull=True,
                        purchase_line__isnull=True,
                        sale_line__isnull=True,
                        reversal_of__isnull=False,
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
            if self.sale_line_id is not None:
                add_error("sale_line", "Purchase movements cannot also reference a Sale line.")
            if self.reversal_of_id is not None:
                add_error("reversal_of", "Purchase movements cannot reference a reversal origin.")
            if self.purchase_line_id is not None:
                try:
                    purchase_line_model = self._meta.get_field("purchase_line").related_model
                    purchase_line = purchase_line_model.objects.select_related("purchase").get(
                        pk=self.purchase_line_id
                    )
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
        elif self.kind == self.Kind.SALE:
            if self.sale_line_id is None:
                add_error("sale_line", "Sale movements require a Sale line.")
            if self.stock_adjustment_id is not None or self.purchase_line_id is not None:
                add_error("sale_line", "Sale movements cannot also reference another origin.")
            if self.reversal_of_id is not None:
                add_error("reversal_of", "Sale movements cannot reference a reversal origin.")
            if self.sale_line_id is not None:
                try:
                    sale_line_model = self._meta.get_field("sale_line").related_model
                    sale_line = sale_line_model.objects.select_related("sale").get(
                        pk=self.sale_line_id
                    )
                except self._meta.get_field("sale_line").related_model.DoesNotExist:
                    add_error("sale_line", "Sale line does not exist.")
                else:
                    # Check persisted line values and parent state rather than
                    # a caller-supplied related-object cache.
                    sale = sale_line.sale
                    if sale.status != sale.Status.COMPLETED:
                        add_error("sale_line", "Sale movements require a completed Sale.")
                    if self.business_id != sale.business_id:
                        add_error("business", "Sale movement Business must match its Sale.")
                    if self.product_id != sale_line.product_id:
                        add_error("product", "Sale movement Product must match its Sale line.")
                    if self.quantity_change != -sale_line.quantity:
                        add_error("quantity_change", "Sale movement quantity must match its Sale line.")
        elif self.kind == self.Kind.REVERSAL:
            if self.reversal_of_id is None:
                add_error("reversal_of", "Reversal movements require an original movement.")
            if (
                self.stock_adjustment_id is not None
                or self.purchase_line_id is not None
                or self.sale_line_id is not None
            ):
                add_error("reversal_of", "Reversal movements cannot also reference another origin.")
            if self.reversal_of_id is not None:
                try:
                    original = type(self).objects.select_related(
                        "purchase_line__purchase", "sale_line__sale"
                    ).get(pk=self.reversal_of_id)
                except type(self).DoesNotExist:
                    add_error("reversal_of", "Original Stock Movement does not exist.")
                else:
                    if original.kind not in {self.Kind.PURCHASE, self.Kind.SALE}:
                        add_error("reversal_of", "Only Purchase and Sale movements can be reversed.")
                    if original.reversal_of_id is not None:
                        add_error("reversal_of", "A reversal movement cannot itself be reversed.")
                    if type(self).objects.filter(reversal_of_id=original.pk).exists():
                        add_error("reversal_of", "The original Stock Movement has already been reversed.")
                    if self.business_id != original.business_id:
                        add_error("business", "Reversal movement Business must match its original.")
                    if self.product_id != original.product_id:
                        add_error("product", "Reversal movement Product must match its original.")
                    if self.quantity_change != -original.quantity_change:
                        add_error("quantity_change", "Reversal movement quantity must negate its original.")
                    # Re-fetching the original with its persisted owner avoids
                    # accepting a caller-populated relation cache.  A reversal
                    # is valid only while the owning document's authorized
                    # void transaction has persisted VOIDED.
                    if original.kind == self.Kind.PURCHASE:
                        purchase_line_model = self._meta.get_field(
                            "purchase_line"
                        ).related_model
                        try:
                            purchase = purchase_line_model.objects.select_related(
                                "purchase"
                            ).get(pk=original.purchase_line_id).purchase
                        except purchase_line_model.DoesNotExist:
                            purchase = None
                        if (
                            purchase is None
                            or purchase.status != purchase.Status.VOIDED
                        ):
                            add_error(
                                "reversal_of",
                                "Purchase reversals require a voided Purchase.",
                            )
                    elif original.kind == self.Kind.SALE:
                        sale_line_model = self._meta.get_field("sale_line").related_model
                        try:
                            sale = sale_line_model.objects.select_related("sale").get(
                                pk=original.sale_line_id
                            ).sale
                        except sale_line_model.DoesNotExist:
                            sale = None
                        if sale is None or sale.status != sale.Status.VOIDED:
                            add_error(
                                "reversal_of",
                                "Sale reversals require a voided Sale.",
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
            if self.sale_line_id is not None:
                add_error(
                    "sale_line",
                    "Adjustment movements cannot also reference a Sale line.",
                )
            if self.reversal_of_id is not None:
                add_error("reversal_of", "Adjustment movements cannot reference a reversal origin.")
            if self.stock_adjustment_id is not None:
                try:
                    adjustment = StockAdjustment.objects.get(pk=self.stock_adjustment_id)
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

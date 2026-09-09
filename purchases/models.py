from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from businesses.models import Business
from catalogue.models import Product


class CompletedPurchaseQuerySet(models.QuerySet):
    """Prevent ORM bulk operations from bypassing completed-record immutability."""

    def _reject_if_completed(self):
        if self.filter(status=Purchase.Status.COMPLETED).exists():
            raise TypeError(Purchase.immutable_error)

    def update(self, **kwargs):
        if kwargs.get("status") == Purchase.Status.COMPLETED:
            raise TypeError(Purchase.immutable_error)
        self._reject_if_completed()
        return super().update(**kwargs)

    def delete(self):
        self._reject_if_completed()
        return super().delete()

    def bulk_update(self, objs, fields, batch_size=None):
        purchase_ids = [purchase.pk for purchase in objs if purchase.pk is not None]
        if any(purchase.status == Purchase.Status.COMPLETED for purchase in objs):
            raise TypeError(Purchase.immutable_error)
        if self.model.objects.filter(
            pk__in=purchase_ids, status=Purchase.Status.COMPLETED
        ).exists():
            raise TypeError(Purchase.immutable_error)
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        if any(purchase.status == Purchase.Status.COMPLETED for purchase in objs):
            raise TypeError(Purchase.immutable_error)
        return super().bulk_create(objs, *args, **kwargs)


class Purchase(models.Model):
    immutable_error = "Completed Purchases are immutable."

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"

    business = models.ForeignKey(
        Business, on_delete=models.PROTECT, related_name="purchases"
    )
    purchase_date = models.DateField()
    supplier_name = models.CharField(max_length=120, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_purchases",
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CompletedPurchaseQuerySet.as_manager()

    class Meta:
        ordering = ("-purchase_date", "-pk")

    @property
    def total(self):
        return sum((line.line_total for line in self.lines.all()), Decimal("0"))

    def save(self, *args, **kwargs):
        if self._state.adding and self.status != self.Status.DRAFT:
            raise TypeError(self.immutable_error)
        if (
            not self._state.adding
            and self.status == self.Status.COMPLETED
            and type(self).objects.filter(pk=self.pk, status=self.Status.DRAFT).exists()
            and not getattr(self, "_completion_authorized", False)
        ):
            raise TypeError("Complete Purchases through the completion service.")
        if (
            not self._state.adding
            and type(self).objects.filter(
                pk=self.pk, status=self.Status.COMPLETED
            ).exists()
        ):
            raise TypeError(self.immutable_error)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED or type(self).objects.filter(
            pk=self.pk, status=self.Status.COMPLETED
        ).exists():
            raise TypeError(self.immutable_error)
        return super().delete(*args, **kwargs)


class CompletedPurchaseLineQuerySet(models.QuerySet):
    """Protect completed Purchase lines from instance and bulk ORM mutations."""

    def _reject_if_completed(self):
        if self.filter(purchase__status=Purchase.Status.COMPLETED).exists():
            raise TypeError(PurchaseLine.immutable_error)

    def update(self, **kwargs):
        target_purchase = kwargs.get("purchase")
        target_purchase_id = kwargs.get(
            "purchase_id",
            getattr(target_purchase, "pk", target_purchase),
        )
        if Purchase.objects.filter(
            pk=target_purchase_id, status=Purchase.Status.COMPLETED
        ).exists():
            raise TypeError(PurchaseLine.immutable_error)
        self._reject_if_completed()
        raise TypeError("Purchase lines must be changed through instance saves.")

    def delete(self):
        self._reject_if_completed()
        return super().delete()

    def bulk_update(self, objs, fields, batch_size=None):
        line_ids = [line.pk for line in objs if line.pk is not None]
        target_purchase_ids = {line.purchase_id for line in objs if line.purchase_id}
        if Purchase.objects.filter(
            pk__in=target_purchase_ids, status=Purchase.Status.COMPLETED
        ).exists():
            raise TypeError(PurchaseLine.immutable_error)
        if self.model.objects.filter(
            pk__in=line_ids, purchase__status=Purchase.Status.COMPLETED
        ).exists():
            raise TypeError(PurchaseLine.immutable_error)
        for line in objs:
            line.full_clean()
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        purchase_ids = {line.purchase_id for line in objs if line.purchase_id}
        if Purchase.objects.filter(
            pk__in=purchase_ids, status=Purchase.Status.COMPLETED
        ).exists():
            raise TypeError(PurchaseLine.immutable_error)
        for line in objs:
            line.full_clean()
        return super().bulk_create(objs, *args, **kwargs)


class PurchaseLine(models.Model):
    immutable_error = "Completed Purchase lines are immutable."

    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="purchase_lines"
    )
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)

    objects = CompletedPurchaseLineQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("purchase", "product"), name="unique_purchase_product"
            )
        ]

    @property
    def line_total(self):
        if self.quantity is None or self.unit_cost is None:
            return Decimal("0")
        return self.quantity * self.unit_cost

    def clean(self):
        errors = {}
        if self.quantity is not None and self.quantity <= 0:
            errors["quantity"] = "Quantity must be a positive whole number."
        if self.unit_cost is not None and self.unit_cost < 0:
            errors["unit_cost"] = "Unit cost cannot be negative."
        if (
            self.purchase_id
            and self.product_id
            and self.purchase.business_id != self.product.business_id
        ):
            errors["product"] = "The Product must belong to this Business."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        completed_purchase = Purchase.objects.filter(
            pk=self.purchase_id, status=Purchase.Status.COMPLETED
        ).exists()
        completed_existing_line = (
            not self._state.adding
            and type(self).objects.filter(
                pk=self.pk, purchase__status=Purchase.Status.COMPLETED
            ).exists()
        )
        if completed_purchase or completed_existing_line:
            raise TypeError(self.immutable_error)
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if Purchase.objects.filter(
            pk=self.purchase_id, status=Purchase.Status.COMPLETED
        ).exists():
            raise TypeError(self.immutable_error)
        return super().delete(*args, **kwargs)

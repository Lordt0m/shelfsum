from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

from businesses.models import Business
from catalogue.models import Product


class CompletedPurchaseQuerySet(models.QuerySet):
    """Prevent ORM bulk operations from bypassing completed-record immutability."""

    def _locked_ids(self):
        return list(
            self.order_by("pk")
            .select_for_update(of=("self",))
            .values_list("pk", flat=True)
        )

    def _reject_if_completed(self):
        if self.filter(status__in=Purchase.terminal_statuses()).exists():
            raise TypeError(Purchase.immutable_error)

    def update(self, **kwargs):
        if "status" in kwargs:
            raise TypeError(Purchase.immutable_error)
        with transaction.atomic():
            ids = self._locked_ids()
            if Purchase.objects.filter(
                pk__in=ids, status__in=Purchase.terminal_statuses()
            ).exists():
                raise TypeError(Purchase.immutable_error)
            return models.QuerySet.update(self.filter(pk__in=ids), **kwargs)

    def delete(self):
        with transaction.atomic():
            ids = self._locked_ids()
            if Purchase.objects.filter(
                pk__in=ids, status__in=Purchase.terminal_statuses()
            ).exists():
                raise TypeError(Purchase.immutable_error)
            return models.QuerySet.delete(self.filter(pk__in=ids))

    def bulk_update(self, objs, fields, batch_size=None):
        objs = list(objs)
        if "status" in fields:
            raise TypeError(Purchase.immutable_error)
        purchase_ids = [purchase.pk for purchase in objs if purchase.pk is not None]
        with transaction.atomic():
            self.filter(pk__in=purchase_ids)._locked_ids()
            if any(
                purchase.status in Purchase.terminal_statuses()
                for purchase in objs
            ) or self.model.objects.filter(
                pk__in=purchase_ids, status__in=Purchase.terminal_statuses()
            ).exists():
                raise TypeError(Purchase.immutable_error)
            return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        with transaction.atomic():
            if any(purchase.status in Purchase.terminal_statuses() for purchase in objs):
                raise TypeError(Purchase.immutable_error)
            return super().bulk_create(objs, *args, **kwargs)


class Purchase(models.Model):
    immutable_error = "Completed Purchases are immutable."

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"
        VOIDED = "voided", "Voided"

    @classmethod
    def terminal_statuses(cls):
        return (cls.Status.COMPLETED, cls.Status.VOIDED)

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
        if not isinstance(self.status, str):
            raise TypeError(self.immutable_error)
        if self._state.adding:
            return super().save(*args, **kwargs)
        with transaction.atomic():
            locked_purchase = type(self).objects.select_for_update().get(pk=self.pk)
            if (
                locked_purchase.status in self.terminal_statuses()
                and not getattr(self, "_void_authorized", False)
            ):
                raise TypeError(self.immutable_error)
            if self.status == self.Status.COMPLETED and not getattr(
                self, "_completion_authorized", False
            ):
                raise TypeError("Complete Purchases through the completion service.")
            if self.status == self.Status.VOIDED and not getattr(
                self, "_void_authorized", False
            ):
                raise TypeError("Void Purchases through the voiding service.")
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            locked_purchase = type(self).objects.select_for_update().get(pk=self.pk)
            if locked_purchase.status in self.terminal_statuses():
                raise TypeError(self.immutable_error)
            return super().delete(*args, **kwargs)


class CompletedPurchaseLineQuerySet(models.QuerySet):
    """Protect completed Purchase lines from instance and bulk ORM mutations."""

    def _locked_purchase_ids(self):
        line_ids = list(self.order_by("pk").values_list("pk", flat=True))
        purchase_ids = list(
            dict.fromkeys(
                PurchaseLine.objects.filter(pk__in=line_ids)
                .order_by("purchase_id", "pk")
                .values_list("purchase_id", flat=True)
            )
        )
        list(
            Purchase.objects.select_for_update()
            .filter(pk__in=purchase_ids)
            .order_by("pk")
        )
        locked_line_ids = list(
            PurchaseLine.objects.select_for_update()
            .filter(pk__in=line_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        return locked_line_ids, purchase_ids

    def _reject_if_completed(self):
        if self.filter(purchase__status__in=Purchase.terminal_statuses()).exists():
            raise TypeError(PurchaseLine.immutable_error)

    def update(self, **kwargs):
        target_purchase = kwargs.get("purchase")
        target_purchase_id = kwargs.get(
            "purchase_id",
            getattr(target_purchase, "pk", target_purchase),
        )
        if Purchase.objects.filter(
            pk=target_purchase_id, status__in=Purchase.terminal_statuses()
        ).exists():
            raise TypeError(PurchaseLine.immutable_error)
        self._reject_if_completed()
        raise TypeError("Purchase lines must be changed through instance saves.")

    def delete(self):
        with transaction.atomic():
            line_ids, purchase_ids = self._locked_purchase_ids()
            if Purchase.objects.filter(
                pk__in=purchase_ids, status__in=Purchase.terminal_statuses()
            ).exists():
                raise TypeError(PurchaseLine.immutable_error)
            return models.QuerySet.delete(self.filter(pk__in=line_ids))

    def bulk_update(self, objs, fields, batch_size=None):
        objs = list(objs)
        line_ids = [line.pk for line in objs if line.pk is not None]
        purchase_ids = {line.purchase_id for line in objs if line.purchase_id}
        if Purchase.objects.filter(
            pk__in=purchase_ids, status__in=Purchase.terminal_statuses()
        ).exists() or self.model.objects.filter(
            pk__in=line_ids, purchase__status__in=Purchase.terminal_statuses()
        ).exists():
            raise TypeError(PurchaseLine.immutable_error)
        # Retain the existing validation contract for bad draft payloads while
        # still making otherwise valid updates go through instance saves.
        for line in objs:
            line.full_clean()
        raise TypeError("Purchase lines must be changed through instance saves.")

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        purchase_ids = {line.purchase_id for line in objs if line.purchase_id}
        with transaction.atomic():
            list(Purchase.objects.select_for_update().filter(pk__in=purchase_ids).order_by("pk"))
            if Purchase.objects.filter(
                pk__in=purchase_ids, status__in=Purchase.terminal_statuses()
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
        with transaction.atomic():
            locked_purchase = Purchase.objects.select_for_update().get(pk=self.purchase_id)
            if locked_purchase.status in Purchase.terminal_statuses():
                raise TypeError(self.immutable_error)
            if not self._state.adding:
                existing_line = type(self).objects.select_for_update().get(pk=self.pk)
                if existing_line.purchase_id != self.purchase_id:
                    raise TypeError("Purchase lines cannot be reassigned.")
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            locked_purchase = Purchase.objects.select_for_update().get(pk=self.purchase_id)
            if locked_purchase.status in Purchase.terminal_statuses():
                raise TypeError(self.immutable_error)
            if not self._state.adding:
                type(self).objects.select_for_update().get(pk=self.pk)
            return super().delete(*args, **kwargs)

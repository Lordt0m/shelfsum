from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

from businesses.models import Business
from catalogue.models import Product


class CompletedSaleQuerySet(models.QuerySet):
    def _locked_ids(self):
        return list(
            self.order_by("pk")
            .select_for_update(of=("self",))
            .values_list("pk", flat=True)
        )

    def _reject_if_completed(self):
        if self.filter(status=Sale.Status.COMPLETED).exists():
            raise TypeError(Sale.immutable_error)

    def update(self, **kwargs):
        if "status" in kwargs:
            raise TypeError(Sale.immutable_error)
        with transaction.atomic():
            ids = self._locked_ids()
            if Sale.objects.filter(pk__in=ids, status=Sale.Status.COMPLETED).exists():
                raise TypeError(Sale.immutable_error)
            return models.QuerySet.update(self.filter(pk__in=ids), **kwargs)

    def delete(self):
        with transaction.atomic():
            ids = self._locked_ids()
            if Sale.objects.filter(pk__in=ids, status=Sale.Status.COMPLETED).exists():
                raise TypeError(Sale.immutable_error)
            return models.QuerySet.delete(self.filter(pk__in=ids))

    def bulk_update(self, objs, fields, batch_size=None):
        objs = list(objs)
        if "status" in fields:
            raise TypeError(Sale.immutable_error)
        ids = [obj.pk for obj in objs if obj.pk is not None]
        with transaction.atomic():
            self.filter(pk__in=ids)._locked_ids()
            if any(obj.status == Sale.Status.COMPLETED for obj in objs) or self.model.objects.filter(pk__in=ids, status=Sale.Status.COMPLETED).exists():
                raise TypeError(Sale.immutable_error)
            return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        with transaction.atomic():
            if any(obj.status == Sale.Status.COMPLETED for obj in objs):
                raise TypeError(Sale.immutable_error)
            return super().bulk_create(objs, *args, **kwargs)


class Sale(models.Model):
    immutable_error = "Completed Sales are immutable."

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"

    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="sales")
    sale_date = models.DateField()
    customer_name = models.CharField(max_length=120, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_sales")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CompletedSaleQuerySet.as_manager()

    class Meta:
        ordering = ("-sale_date", "-pk")

    @property
    def total(self):
        return sum((line.line_total for line in self.lines.all()), Decimal("0"))

    def save(self, *args, **kwargs):
        if self._state.adding and self.status != self.Status.DRAFT:
            raise TypeError(self.immutable_error)
        if self._state.adding:
            return super().save(*args, **kwargs)
        with transaction.atomic():
            locked_sale = type(self).objects.select_for_update().get(pk=self.pk)
            if locked_sale.status == self.Status.COMPLETED:
                raise TypeError(self.immutable_error)
            if self.status == self.Status.COMPLETED and not getattr(self, "_completion_authorized", False):
                raise TypeError("Complete Sales through the completion service.")
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            locked_sale = type(self).objects.select_for_update().get(pk=self.pk)
            if locked_sale.status == self.Status.COMPLETED:
                raise TypeError(self.immutable_error)
            return super().delete(*args, **kwargs)


class CompletedSaleLineQuerySet(models.QuerySet):
    def _locked_sale_ids(self):
        """Lock the exact selected parents before their exact selected lines.

        Avoid ``DISTINCT`` plus an ordering column that is not selected: that
        shape is not portable to PostgreSQL.  The ordered values are small and
        are deduplicated in Python before the parent lock query.
        """
        line_ids = list(self.order_by("pk").values_list("pk", flat=True))
        sale_ids = list(
            dict.fromkeys(
                SaleLine.objects.filter(pk__in=line_ids)
                .order_by("sale_id", "pk")
                .values_list("sale_id", flat=True)
            )
        )
        list(Sale.objects.select_for_update().filter(pk__in=sale_ids).order_by("pk"))
        locked_line_ids = list(
            SaleLine.objects.select_for_update()
            .filter(pk__in=line_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        return locked_line_ids, sale_ids

    def _reject_if_completed(self):
        if self.filter(sale__status=Sale.Status.COMPLETED).exists():
            raise TypeError(SaleLine.immutable_error)

    def update(self, **kwargs):
        target = kwargs.get("sale")
        target_id = kwargs.get("sale_id", getattr(target, "pk", target))
        if Sale.objects.filter(pk=target_id, status=Sale.Status.COMPLETED).exists():
            raise TypeError(SaleLine.immutable_error)
        self._reject_if_completed()
        raise TypeError("Sale lines must be changed through instance saves.")

    def delete(self):
        with transaction.atomic():
            line_ids, sale_ids = self._locked_sale_ids()
            if Sale.objects.filter(pk__in=sale_ids, status=Sale.Status.COMPLETED).exists():
                raise TypeError(SaleLine.immutable_error)
            return models.QuerySet.delete(self.filter(pk__in=line_ids))

    def bulk_update(self, objs, fields, batch_size=None):
        objs = list(objs)
        ids = [obj.pk for obj in objs if obj.pk is not None]
        sale_ids = {obj.sale_id for obj in objs if obj.sale_id}
        if Sale.objects.filter(pk__in=sale_ids, status=Sale.Status.COMPLETED).exists() or self.model.objects.filter(pk__in=ids, sale__status=Sale.Status.COMPLETED).exists():
            raise TypeError(SaleLine.immutable_error)
        raise TypeError("Sale lines must be changed through instance saves.")

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        sale_ids = {obj.sale_id for obj in objs if obj.sale_id}
        with transaction.atomic():
            list(Sale.objects.select_for_update().filter(pk__in=sale_ids).order_by("pk"))
            if Sale.objects.filter(pk__in=sale_ids, status=Sale.Status.COMPLETED).exists():
                raise TypeError(SaleLine.immutable_error)
            for obj in objs:
                obj.full_clean()
            return super().bulk_create(objs, *args, **kwargs)


class SaleLine(models.Model):
    immutable_error = "Completed Sale lines are immutable."
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sale_lines")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    objects = CompletedSaleLineQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("sale", "product"), name="unique_sale_product")]

    @property
    def unit_cost_snapshot(self):
        return self.cost_snapshot

    @unit_cost_snapshot.setter
    def unit_cost_snapshot(self, value):
        self.cost_snapshot = value

    @property
    def line_total(self):
        if self.quantity is None or self.unit_price is None:
            return Decimal("0")
        return self.quantity * self.unit_price

    def clean(self):
        errors = {}
        if self.quantity is not None and self.quantity <= 0:
            errors["quantity"] = "Quantity must be a positive whole number."
        if self.unit_price is not None and self.unit_price < 0:
            errors["unit_price"] = "Unit price cannot be negative."
        if self.cost_snapshot is not None and self.cost_snapshot < 0:
            errors["cost_snapshot"] = "Cost snapshot cannot be negative."
        if self.sale_id and self.product_id and self.sale.business_id != self.product.business_id:
            errors["product"] = "The Product must belong to this Business."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            locked_sale = Sale.objects.select_for_update().get(pk=self.sale_id)
            if locked_sale.status == Sale.Status.COMPLETED:
                raise TypeError(self.immutable_error)
            if not self._state.adding:
                existing_line = type(self).objects.select_for_update().get(pk=self.pk)
                if existing_line.sale_id != self.sale_id:
                    raise TypeError("Sale lines cannot be reassigned.")
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            locked_sale = Sale.objects.select_for_update().get(pk=self.sale_id)
            if locked_sale.status == Sale.Status.COMPLETED:
                raise TypeError(self.immutable_error)
            if not self._state.adding:
                type(self).objects.select_for_update().get(pk=self.pk)
            return super().delete(*args, **kwargs)

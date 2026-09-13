from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from businesses.models import Business


class ExpenseQuerySet(models.QuerySet):
    def _reject(self):
        raise TypeError(Expense.immutable_error)

    def update(self, **kwargs):
        if self.filter(status__in=Expense.terminal_statuses()).exists():
            self._reject()
        return super().update(**kwargs)

    def delete(self):
        if self.filter(status__in=Expense.terminal_statuses()).exists():
            self._reject()
        return super().delete()

    def bulk_update(self, objs, fields, batch_size=None):
        ids = [o.pk for o in objs if o.pk]
        has_terminal_expense = self.model.objects.filter(
            pk__in=ids, status__in=Expense.terminal_statuses()
        ).exists()
        has_terminal_payload = any(
            expense.status in Expense.terminal_statuses() for expense in objs
        )
        if "status" in fields or has_terminal_expense or has_terminal_payload:
            self._reject()
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        if any(o.status != Expense.Status.RECORDED for o in objs):
            self._reject()
        for expense in objs:
            expense.full_clean()
        return super().bulk_create(objs, *args, **kwargs)


class Expense(models.Model):
    immutable_error = "Recorded and voided Expenses are immutable."

    class Category(models.TextChoices):
        RENT = "rent", "Rent"
        UTILITIES = "utilities", "Utilities"
        TRANSPORT = "transport", "Transport"
        MAINTENANCE = "maintenance", "Maintenance"
        SUPPLIES = "supplies", "Supplies"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        RECORDED = "recorded", "Recorded"
        VOIDED = "voided", "Voided"
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="expenses")
    date = models.DateField()
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.CharField(max_length=240)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="expenses_recorded")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RECORDED)
    correction_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="replacement")
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ExpenseQuerySet.as_manager()

    class Meta:
        ordering = ("-date", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="expense_positive_amount"
            )
        ]

    @classmethod
    def terminal_statuses(cls):
        return (cls.Status.RECORDED, cls.Status.VOIDED)
    def clean(self):
        errors = {}
        if self.amount is not None and self.amount <= Decimal("0"):
            errors["amount"] = "Amount must be greater than zero."
        if self.correction_of_id and self.correction_of_id == self.pk:
            errors["correction_of"] = "An Expense cannot correct itself."
        if self.correction_of_id and self.correction_of_id != self.pk:
            try:
                original = type(self).objects.only("business_id", "status").get(
                    pk=self.correction_of_id
                )
            except type(self).DoesNotExist:
                errors["correction_of"] = "The original Expense does not exist."
            else:
                if original.business_id != self.business_id:
                    errors["correction_of"] = (
                        "A replacement Expense must belong to the original Business."
                    )
                elif original.status != self.Status.VOIDED:
                    errors["correction_of"] = (
                        "A replacement Expense requires a voided original Expense."
                    )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self._state.adding and self.status != self.Status.RECORDED:
            raise ValidationError({"status": "New Expenses must be recorded."})
        if not self._state.adding:
            raise TypeError(self.immutable_error)
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError(self.immutable_error)

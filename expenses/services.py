from django.core.exceptions import ValidationError
from django.db import models, transaction

from auditing.services import record_audit_event
from businesses.rules import ensure_business_write_allowed

from .models import Expense


@transaction.atomic
def record_expense(*, business, actor, details):
    ensure_business_write_allowed(business=business, actor=actor)
    expense = Expense.objects.create(business=business, actor=actor, **details)
    record_audit_event(
        business=business,
        actor=actor,
        action="expense.recorded",
        affected_object=expense,
        summary=f"Recorded Expense: {expense.description} ({expense.amount})",
    )
    return expense


@transaction.atomic
def void_expense(*, business, actor, expense):
    if expense.business_id != business.pk:
        raise ValidationError("The Expense does not belong to this Business.")
    ensure_business_write_allowed(business=business, actor=actor)
    locked = Expense.objects.select_for_update().get(
        pk=expense.pk, business=business
    )
    if locked.status != Expense.Status.RECORDED:
        raise ValidationError("This Expense has already been voided.")
    # Explicit lifecycle update is the only permitted mutation.
    models.QuerySet.update(
        type(locked).objects.filter(pk=locked.pk), status=Expense.Status.VOIDED
    )
    locked.status = Expense.Status.VOIDED
    record_audit_event(
        business=business,
        actor=actor,
        action="expense.voided",
        affected_object=locked,
        summary=f"Voided Expense: {locked.description} ({locked.amount})",
    )
    return locked


@transaction.atomic
def correct_expense(*, business, actor, expense, details):
    if expense.business_id != business.pk:
        raise ValidationError("The Expense does not belong to this Business.")
    ensure_business_write_allowed(business=business, actor=actor)
    locked = Expense.objects.select_for_update().get(
        pk=expense.pk, business=business
    )
    if locked.status != Expense.Status.RECORDED:
        raise ValidationError("Only a recorded Expense can be corrected.")
    models.QuerySet.update(
        type(locked).objects.filter(pk=locked.pk), status=Expense.Status.VOIDED
    )
    locked.status = Expense.Status.VOIDED
    replacement = Expense.objects.create(
        business=business, actor=actor, correction_of=locked, **details
    )
    record_audit_event(
        business=business,
        actor=actor,
        action="expense.corrected",
        affected_object=replacement,
        summary=f"Corrected Expense {locked.pk} with Expense {replacement.pk}.",
    )
    return replacement

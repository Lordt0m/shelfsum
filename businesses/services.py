from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from auditing.services import record_audit_event
from businesses.models import Business, Membership
from businesses.rules import ensure_business_write_allowed


class MembershipAssignmentError(ValidationError):
    """A user-facing reason an Owner cannot add a Staff Member."""


class BusinessCreationError(ValidationError):
    """A user-facing reason an account cannot create another Business."""


def _locked_owner_membership(*, business, actor):
    ensure_business_write_allowed(business=business, actor=actor)
    membership = Membership.objects.select_for_update().filter(
        business=business,
        user=actor,
        role=Membership.Role.OWNER,
        is_active=True,
    ).first()
    if membership is None:
        raise PermissionDenied("An active Owner membership is required.")
    return membership


@transaction.atomic
def create_business_for_owner(*, actor, name, phone_number="", address=""):
    """Create a Business and its active Owner membership as one unit."""
    user_model = get_user_model()
    locked_actor = user_model.objects.select_for_update().get(pk=actor.pk)
    if Membership.objects.select_for_update().filter(user=locked_actor).exists():
        raise BusinessCreationError("Your account already belongs to a Business.")

    business = Business.objects.create(
        name=name,
        phone_number=phone_number,
        address=address,
    )
    Membership.objects.create(
        user=locked_actor,
        business=business,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    record_audit_event(
        business=business,
        actor=locked_actor,
        action="business.created",
        affected_object=business,
        summary=f"Created Business {business.name}.",
    )
    return business


@transaction.atomic
def update_business_settings(*, business, actor, name, phone_number, address):
    """Update validated Business settings for its active Owner."""
    locked_business = Business.objects.select_for_update().get(pk=business.pk)
    _locked_owner_membership(business=locked_business, actor=actor)

    values = {
        "name": name,
        "phone_number": phone_number,
        "address": address,
    }
    changed_fields = [
        field for field, value in values.items()
        if getattr(locked_business, field) != value
    ]
    if not changed_fields:
        return locked_business

    for field in changed_fields:
        setattr(locked_business, field, values[field])
    locked_business.save(update_fields=[*changed_fields, "updated_at"])
    record_audit_event(
        business=locked_business,
        actor=actor,
        action="business.updated",
        affected_object=locked_business,
        summary="Updated Business settings.",
    )
    return locked_business


@transaction.atomic
def add_staff_member(*, business, actor, email):
    """Assign an already registered, unassigned user to this Business."""
    locked_business = Business.objects.select_for_update().get(pk=business.pk)
    _locked_owner_membership(business=locked_business, actor=actor)

    normalized_email = email.strip().lower()
    if normalized_email == actor.email:
        raise MembershipAssignmentError("You cannot add yourself as a Staff Member.")

    user_model = get_user_model()
    try:
        user = user_model.objects.select_for_update().get(email__iexact=normalized_email)
    except user_model.DoesNotExist as error:
        raise MembershipAssignmentError(
            "No registered user has that email address."
        ) from error

    existing_membership = Membership.objects.select_for_update().filter(user=user).first()
    if existing_membership is not None:
        if existing_membership.business_id == locked_business.pk:
            raise MembershipAssignmentError("That user already belongs to this Business.")
        raise MembershipAssignmentError(
            "That user is already assigned to another Business."
        )

    membership = Membership.objects.create(
        user=user,
        business=locked_business,
        role=Membership.Role.STAFF,
    )
    record_audit_event(
        business=locked_business,
        actor=actor,
        action="membership.staff_added",
        affected_object=membership,
        summary=f"Added Staff Member {user.email}.",
    )
    return membership


@transaction.atomic
def deactivate_staff_member(*, business, actor, membership):
    """Deactivate a Staff Member without deleting their historical attribution."""
    locked_business = Business.objects.select_for_update().get(pk=business.pk)
    _locked_owner_membership(business=locked_business, actor=actor)
    if membership.business_id != locked_business.pk:
        raise ValidationError("The Staff Member does not belong to this Business.")

    locked_membership = Membership.objects.select_for_update().get(
        pk=membership.pk,
        business=locked_business,
        role=Membership.Role.STAFF,
    )
    if not locked_membership.is_active:
        return locked_membership

    locked_membership.is_active = False
    locked_membership.save(update_fields=["is_active"])
    record_audit_event(
        business=locked_business,
        actor=actor,
        action="membership.staff_deactivated",
        affected_object=locked_membership,
        summary=f"Deactivated Staff Member {locked_membership.user.email}.",
    )
    return locked_membership

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from businesses.access import (
    demo_business_read_only,
    inactive_membership_response,
    membership_for,
    membership_required,
    owner_required,
)
from businesses.forms import BusinessForm, StaffMemberForm
from businesses.models import Business, Membership
from businesses.services import (
    MembershipAssignmentError,
    add_staff_member,
    deactivate_staff_member,
)
from businesses.dashboard import dashboard_context


@login_required
def create_business(request):
    membership = membership_for(request.user)
    if membership is not None and not membership.is_active:
        return inactive_membership_response(request)
    if membership is not None:
        return redirect("business_home")

    form = BusinessForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = get_user_model().objects.select_for_update().get(
                    pk=request.user.pk
                )
                if Membership.objects.filter(user=user).exists():
                    return redirect("business_home")
                business = form.save()
                Membership.objects.create(
                    user=user,
                    business=business,
                    role=Membership.Role.OWNER,
                )
        except IntegrityError:
            messages.error(request, "Your account already belongs to a Business.")
            return redirect("business_home")
        messages.success(request, "Your Business is ready.")
        return redirect("business_home")

    return render(request, "businesses/create.html", {"form": form})


@membership_required
def business_home(request):
    context = {"business": request.business, "membership": request.membership}
    context.update(dashboard_context(business=request.business))
    return render(request, "businesses/home.html", context)


@owner_required
@demo_business_read_only
def business_settings(request):
    form = BusinessForm(request.POST or None, instance=request.business)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Business settings updated.")
        return redirect("business_settings")
    return render(
        request,
        "businesses/settings.html",
        {"form": form, "business": request.business},
    )


@owner_required
def staff_member_list(request):
    staff_members = Membership.objects.filter(
        business=request.business, role=Membership.Role.STAFF
    ).select_related("user")
    return render(
        request,
        "businesses/staff_member_list.html",
        {"staff_members": staff_members, "business": request.business},
    )


@owner_required
@demo_business_read_only
def staff_member_add(request):
    form = StaffMemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            add_staff_member(
                business=request.business,
                actor=request.user,
                email=form.cleaned_data["email"],
            )
        except MembershipAssignmentError as error:
            form.add_error("email", error)
        else:
            messages.success(request, "Staff Member added.")
            return redirect("staff_member_list")
    return render(request, "businesses/staff_member_add.html", {"form": form})


@owner_required
@demo_business_read_only
def staff_member_deactivate(request, membership_id):
    membership = get_object_or_404(
        Membership.objects.select_related("user"),
        pk=membership_id,
        business=request.business,
        role=Membership.Role.STAFF,
    )
    if request.method == "POST":
        deactivate_staff_member(
            business=request.business, actor=request.user, membership=membership
        )
        messages.success(request, "Staff Member deactivated.")
    return redirect("staff_member_list")

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from businesses.access import membership_required, owner_required
from businesses.forms import BusinessForm
from businesses.models import Business, Membership


@login_required
def create_business(request):
    if Membership.objects.filter(user=request.user).exists():
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
    return render(
        request,
        "businesses/home.html",
        {"business": request.business, "membership": request.membership},
    )


@owner_required
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

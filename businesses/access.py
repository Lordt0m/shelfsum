from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from businesses.models import Membership


def active_membership_for(user):
    if not user.is_authenticated:
        return None
    return (
        Membership.objects.select_related("business")
        .filter(user=user, is_active=True)
        .first()
    )


def membership_required(view_function):
    @wraps(view_function)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        membership = active_membership_for(request.user)
        if membership is None:
            return redirect("business_create")
        request.membership = membership
        request.business = membership.business
        return view_function(request, *args, **kwargs)

    return wrapped


def owner_required(view_function):
    @membership_required
    @wraps(view_function)
    def wrapped(request, *args, **kwargs):
        if request.membership.role != Membership.Role.OWNER:
            raise PermissionDenied
        return view_function(request, *args, **kwargs)

    return wrapped

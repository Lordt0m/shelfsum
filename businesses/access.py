from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from businesses.models import Membership
from businesses.rules import DemoBusinessReadOnly, ensure_business_write_allowed


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def membership_for(user):
    if not user.is_authenticated:
        return None
    return (
        Membership.objects.select_related("business")
        .filter(user=user)
        .first()
    )


def inactive_membership_response(request):
    return render(
        request,
        "businesses/access_blocked.html",
        {
            "page_title": "Business access inactive",
            "explanation": (
                "Your Business access is inactive. An Owner must restore it before "
                "you can use Business pages."
            ),
        },
        status=403,
    )


def membership_required(view_function):
    @wraps(view_function)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        membership = membership_for(request.user)
        if membership is None:
            return redirect("business_create")
        if not membership.is_active:
            return inactive_membership_response(request)
        request.membership = membership
        request.business = membership.business
        read_only_response = demo_write_block_response(request)
        if read_only_response is not None:
            return read_only_response
        return view_function(request, *args, **kwargs)

    return wrapped


def demo_business_read_only(view_function):
    @wraps(view_function)
    def wrapped(request, *args, **kwargs):
        read_only_response = demo_write_block_response(request)
        if read_only_response is not None:
            return read_only_response
        return view_function(request, *args, **kwargs)

    return wrapped


def demo_write_block_response(request):
    """Return the shared Demo denial response for an unsafe request, if needed."""
    if request.method in SAFE_METHODS:
        return None
    business = getattr(request, "business", None)
    if business is None:
        membership = membership_for(request.user)
        if membership is None:
            return None
        request.membership = membership
        request.business = membership.business
        business = membership.business
    try:
        ensure_business_write_allowed(business=business, actor=request.user)
    except DemoBusinessReadOnly:
        return render(
            request,
            "businesses/access_blocked.html",
            {
                "page_title": "Demo Business is read-only",
                "explanation": (
                    "This fictional Demo Business is read-only so every visitor "
                    "sees the same reliable data."
                ),
            },
            status=403,
        )
    return None


def owner_required(view_function):
    @membership_required
    @wraps(view_function)
    def wrapped(request, *args, **kwargs):
        if request.membership.role != Membership.Role.OWNER:
            raise PermissionDenied
        return view_function(request, *args, **kwargs)

    return wrapped

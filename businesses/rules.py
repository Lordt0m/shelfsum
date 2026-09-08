from django.core.exceptions import PermissionDenied

from businesses.models import Membership


class DemoBusinessReadOnly(PermissionDenied):
    pass


def ensure_business_write_allowed(*, business, actor):
    if business.is_demo:
        raise DemoBusinessReadOnly("The Demo Business is read-only.")
    if not Membership.objects.filter(
        business=business, user=actor, is_active=True
    ).exists():
        raise PermissionDenied("An active Business membership is required.")

from django.conf import settings
from django.db import models

from businesses.models import Business
from core.models import ImmutableModel


class AuditEvent(ImmutableModel):
    immutable_error = "Audit Events are append-only."
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80)
    object_identifier = models.CharField(max_length=80)
    summary = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

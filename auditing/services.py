from businesses.rules import ensure_business_write_allowed
from auditing.models import AuditEvent


def record_audit_event(
    *, business, actor, action, affected_object, summary
):
    ensure_business_write_allowed(business=business, actor=actor)
    return AuditEvent.objects.create(
        business=business,
        actor=actor,
        action=action,
        object_type=affected_object._meta.label,
        object_identifier=str(affected_object.pk),
        summary=summary,
    )

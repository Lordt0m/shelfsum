from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone
from django.utils.dateparse import parse_date

from auditing.models import AuditEvent


LAGOS = ZoneInfo("Africa/Lagos")


@dataclass(frozen=True)
class AuditEventFilters:
    actor_id: int | None
    action: str
    date_from: date | None
    date_to: date | None
    errors: tuple[str, ...] = ()
    actor_input: str = ""
    action_input: str = ""
    date_from_input: str = ""
    date_to_input: str = ""

    @property
    def is_valid(self):
        return not self.errors

    @property
    def actor_value(self):
        return self.actor_input

    @property
    def actor_is_invalid(self):
        return bool(self.actor_input) and any(
            error == "Choose an actor from this Business." for error in self.errors
        )

    @property
    def action_value(self):
        return self.action_input or self.action

    @property
    def date_from_value(self):
        return self.date_from_input or (self.date_from.isoformat() if self.date_from else "")

    @property
    def date_to_value(self):
        return self.date_to_input or (self.date_to.isoformat() if self.date_to else "")


def _parse_date(value, *, message, errors):
    if not value:
        return None
    try:
        parsed = parse_date(value)
    except ValueError:
        parsed = None
    if parsed is None:
        errors.append(message)
    return parsed


def _local_start(value):
    return datetime.combine(value, time.min, tzinfo=LAGOS)


def _local_end(value):
    return _local_start(value + timedelta(days=1))


@dataclass(frozen=True)
class AuditEventRow:
    event: AuditEvent

    @property
    def lagos_timestamp_display(self):
        return timezone.localtime(self.event.created_at, LAGOS).strftime("%Y-%m-%d %H:%M:%S %z")


@dataclass(frozen=True)
class AuditEventBrowser:
    filters: AuditEventFilters
    rows: tuple[AuditEventRow, ...]
    actors: tuple
    actions: tuple[str, ...]


def build_audit_event_browser(*, business, query_params):
    """Return a current-Business, read-only Audit Event browser."""
    events = AuditEvent.objects.filter(business=business)
    actors = tuple(
        events.order_by("actor__email", "actor_id").values_list("actor_id", "actor__email").distinct()
    )
    actions = tuple(events.order_by("action").values_list("action", flat=True).distinct())
    errors = []
    actor_input = query_params.get("actor") or ""
    actor_id = None
    actor_ids = {actor[0] for actor in actors}
    if actor_input:
        try:
            actor_id = int(actor_input)
        except (TypeError, ValueError):
            actor_id = None
        if actor_id is None or actor_id not in actor_ids:
            errors.append("Choose an actor from this Business.")

    action_input = query_params.get("action") or ""
    action = action_input
    if action_input and action_input not in actions:
        errors.append("Choose an action from this Business.")

    date_from_input = query_params.get("date_from") or ""
    date_to_input = query_params.get("date_to") or ""
    date_from = _parse_date(date_from_input, message="Enter a valid start date.", errors=errors)
    date_to = _parse_date(date_to_input, message="Enter a valid end date.", errors=errors)
    if date_from and date_to and date_to < date_from:
        errors.append("End date cannot be earlier than start date.")
    filters = AuditEventFilters(
        actor_id=actor_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        errors=tuple(errors),
        actor_input=actor_input,
        action_input=action_input,
        date_from_input=date_from_input,
        date_to_input=date_to_input,
    )
    if not filters.is_valid:
        return AuditEventBrowser(filters=filters, rows=(), actors=actors, actions=actions)

    if actor_id:
        events = events.filter(actor_id=actor_id)
    if action:
        events = events.filter(action=action)
    if date_from:
        events = events.filter(created_at__gte=_local_start(date_from))
    if date_to:
        events = events.filter(created_at__lt=_local_end(date_to))
    rows = tuple(AuditEventRow(event=event) for event in events.select_related("actor"))
    return AuditEventBrowser(filters=filters, rows=rows, actors=actors, actions=actions)

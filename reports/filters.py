from dataclasses import dataclass
from datetime import date

from django.utils.dateparse import parse_date


@dataclass(frozen=True)
class ReportDateRange:
    date_from: date | None
    date_to: date | None
    errors: tuple[str, ...] = ()
    date_from_input: str = ""
    date_to_input: str = ""

    @property
    def is_valid(self):
        return not self.errors

    @property
    def date_from_value(self):
        return self.date_from_input or (
            self.date_from.isoformat() if self.date_from else ""
        )

    @property
    def date_to_value(self):
        return self.date_to_input or (
            self.date_to.isoformat() if self.date_to else ""
        )


def month_bounds_for_date(today):
    first = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    return first, next_month - date.resolution


def parse_inclusive_date_range(query_params, *, default_bounds):
    """Parse optional inclusive dates, defaulting only when both are omitted."""
    date_from_input = query_params.get("date_from") or ""
    date_to_input = query_params.get("date_to") or ""
    errors = []

    def parse(value, message):
        if not value:
            return None
        try:
            parsed = parse_date(value)
        except ValueError:
            parsed = None
        if parsed is None:
            errors.append(message)
        return parsed

    date_from = parse(date_from_input, "Enter a valid start date.")
    date_to = parse(date_to_input, "Enter a valid end date.")
    if not date_from_input and not date_to_input:
        date_from, date_to = default_bounds()
    if date_from and date_to and date_to < date_from:
        errors.append("End date cannot be earlier than start date.")

    return ReportDateRange(
        date_from=date_from,
        date_to=date_to,
        errors=tuple(errors),
        date_from_input=date_from_input,
        date_to_input=date_to_input,
    )

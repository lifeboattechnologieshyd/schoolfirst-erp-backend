import datetime
from collections.abc import Mapping
from dataclasses import dataclass

from dateutil.rrule import DAILY, FR, MO, MONTHLY, SA, SU, TH, TU, WE, WEEKLY, YEARLY, rrule

from apps.calendar.enums import RecurringFrequency

# Keys are derived from the enum so adding a new frequency here is caught
# at import time, not at runtime.
FREQ_MAP = {
    RecurringFrequency.DAILY: DAILY,
    RecurringFrequency.WEEKLY: WEEKLY,
    RecurringFrequency.MONTHLY: MONTHLY,
    RecurringFrequency.YEARLY: YEARLY,
}

WEEKDAY_MAP = {
    "MO": MO,
    "TU": TU,
    "WE": WE,
    "TH": TH,
    "FR": FR,
    "SA": SA,
    "SU": SU,
}


@dataclass(frozen=True)
class RecurrenceRuleData:
    frequency: RecurringFrequency
    interval: int | None = None
    by_day: tuple[str, ...] = ()
    by_month_day: tuple[int, ...] = ()
    count: int | None = None
    until: str | None = None


def _coerce_int(value: object, field_name: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"rrule {field_name} must be an integer.")


def _coerce_optional_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    return _coerce_int(value, field_name)


def coerce_recurrence_rule(rrule_value: Mapping[str, object] | RecurrenceRuleData | None) -> RecurrenceRuleData | None:
    if rrule_value is None:
        return None
    if isinstance(rrule_value, RecurrenceRuleData):
        return rrule_value

    frequency = rrule_value.get("frequency")
    if not frequency:
        raise ValueError("rrule frequency is required.")
    normalized_frequency = RecurringFrequency(str(frequency))

    raw_by_day = rrule_value.get("by_day")
    by_day = tuple(str(day) for day in raw_by_day) if isinstance(raw_by_day, list) else ()

    raw_by_month_day = rrule_value.get("by_month_day")
    by_month_day = (
        tuple(_coerce_int(day, "by_month_day") for day in raw_by_month_day)
        if isinstance(raw_by_month_day, list)
        else ()
    )

    interval = _coerce_optional_int(rrule_value.get("interval"), "interval")
    count = _coerce_optional_int(rrule_value.get("count"), "count")
    until = rrule_value.get("until")

    return RecurrenceRuleData(
        frequency=normalized_frequency,
        interval=interval,
        by_day=by_day,
        by_month_day=by_month_day,
        count=count,
        until=str(until) if until else None,
    )


def serialize_recurrence_rule(rrule_value: RecurrenceRuleData | None) -> dict[str, object] | None:
    if rrule_value is None:
        return None

    serialized: dict[str, object] = {"frequency": rrule_value.frequency}
    if rrule_value.interval is not None:
        serialized["interval"] = rrule_value.interval
    if rrule_value.by_day:
        serialized["by_day"] = list(rrule_value.by_day)
    if rrule_value.by_month_day:
        serialized["by_month_day"] = list(rrule_value.by_month_day)
    if rrule_value.count is not None:
        serialized["count"] = rrule_value.count
    if rrule_value.until:
        serialized["until"] = rrule_value.until
    return serialized


def build_rrule_obj(rrule_dict: Mapping[str, object] | RecurrenceRuleData, dtstart: datetime.datetime):
    """Convert an rrule dict to a dateutil rrule object."""
    normalized_rule = coerce_recurrence_rule(rrule_dict)
    if normalized_rule is None:
        raise ValueError("rrule is required.")

    kwargs: dict = {
        "freq": FREQ_MAP[normalized_rule.frequency],
        "dtstart": dtstart,
    }
    if normalized_rule.interval:
        kwargs["interval"] = normalized_rule.interval
    if normalized_rule.by_day:
        kwargs["byweekday"] = [WEEKDAY_MAP[day] for day in normalized_rule.by_day]
    if normalized_rule.by_month_day:
        kwargs["bymonthday"] = list(normalized_rule.by_month_day)
    if normalized_rule.count:
        kwargs["count"] = normalized_rule.count
    if normalized_rule.until:
        until_date = datetime.date.fromisoformat(normalized_rule.until)
        if dtstart.tzinfo is not None:
            kwargs["until"] = datetime.datetime.combine(until_date, datetime.time.max, tzinfo=datetime.UTC)
        else:
            kwargs["until"] = datetime.datetime.combine(until_date, datetime.time.max)
    return rrule(**kwargs)


def expand_occurrences(
    rrule_dict: Mapping[str, object] | RecurrenceRuleData,
    dtstart: datetime.datetime,
    from_date: datetime.date,
    to_date: datetime.date,
) -> list[datetime.date]:
    """Expand a recurrence rule into occurrence dates within [from_date, to_date]."""
    rule = build_rrule_obj(rrule_dict, dtstart)
    if dtstart.tzinfo is not None:
        from_dt = datetime.datetime.combine(from_date, datetime.time.min).replace(tzinfo=datetime.UTC)
        to_dt = datetime.datetime.combine(to_date, datetime.time.max).replace(tzinfo=datetime.UTC)
    else:
        from_dt = datetime.datetime.combine(from_date, datetime.time.min)
        to_dt = datetime.datetime.combine(to_date, datetime.time.max)
    return [dt.date() for dt in rule.between(from_dt, to_dt, inc=True)]

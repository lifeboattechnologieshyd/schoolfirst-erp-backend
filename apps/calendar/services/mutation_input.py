from __future__ import annotations

import datetime
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from apps.calendar.utils import RecurrenceRuleData, coerce_recurrence_rule, serialize_recurrence_rule


@dataclass(frozen=True)
class CalendarMutationInput:
    field_values: dict[str, object] = field(default_factory=dict)
    recurrence_rule: RecurrenceRuleData | None = None
    recurrence_date: datetime.date | None = None
    attachments: list[str] | None = None
    has_recurrence_rule: bool = False
    has_recurrence_date: bool = False
    has_attachments: bool = False

    @classmethod
    def from_validated_data(cls, validated_data: Mapping[str, object] | CalendarMutationInput) -> CalendarMutationInput:
        if isinstance(validated_data, cls):
            return validated_data

        data = dict(cast(Mapping[str, object], validated_data))
        has_recurrence_rule = "rrule" in data
        raw_recurrence_rule = data.pop("rrule", None)
        has_recurrence_date = "recurrence_date" in data
        raw_recurrence_date = data.pop("recurrence_date", None)
        has_attachments = "attachments" in data
        raw_attachments = data.pop("attachments", None)

        recurrence_rule = (
            raw_recurrence_rule
            if raw_recurrence_rule is None or isinstance(raw_recurrence_rule, RecurrenceRuleData)
            else cast(Mapping[str, object], raw_recurrence_rule)
            if isinstance(raw_recurrence_rule, Mapping)
            else None
        )
        recurrence_date = raw_recurrence_date if isinstance(raw_recurrence_date, datetime.date) else None
        attachments = [str(path) for path in raw_attachments] if isinstance(raw_attachments, list) else None

        return cls(
            field_values=data,
            recurrence_rule=coerce_recurrence_rule(recurrence_rule),
            recurrence_date=recurrence_date,
            attachments=attachments,
            has_recurrence_rule=has_recurrence_rule,
            has_recurrence_date=has_recurrence_date,
            has_attachments=has_attachments,
        )

    def get(self, key: str, default: object = None) -> object:
        return self.field_values.get(key, default)

    def has_field(self, key: str) -> bool:
        return key in self.field_values

    def to_model_values(self, include_recurrence_rule: bool = True) -> dict[str, object]:
        model_values = dict(self.field_values)
        if include_recurrence_rule and self.has_recurrence_rule:
            model_values["rrule"] = serialize_recurrence_rule(self.recurrence_rule)
        return model_values

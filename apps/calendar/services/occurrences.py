import copy
import datetime

from apps.calendar.utils import expand_occurrences


class CalendarOccurrenceManager:
    def __init__(self, service):
        self.service = service

    def assert_valid_occurrence_date(self, obj, occurrence_date: datetime.date) -> None:
        parent_fk_id_field = f"{self.service.parent_fk_field}_id"
        if getattr(obj, parent_fk_id_field, None):
            if obj.recurrence_date != occurrence_date:
                raise ValueError(
                    self.service._validation_error(
                        "occurrence_date",
                        "occurrence_date does not match the selected override record.",
                    )
                )
            return

        if obj.rrule is None:
            raise ValueError(
                self.service._validation_error(
                    "occurrence_date",
                    "occurrence_date is only valid for recurring items.",
                )
            )

        anchor = self.service._get_anchor(obj)
        if anchor is None:
            raise ValueError(
                self.service._validation_error(
                    "occurrence_date",
                    "occurrence_date is only valid for recurring items.",
                )
            )

        valid_occurrences = expand_occurrences(obj.rrule, anchor, occurrence_date, occurrence_date)
        if occurrence_date not in valid_occurrences:
            raise ValueError(
                self.service._validation_error(
                    "occurrence_date",
                    "occurrence_date is not a valid occurrence for this item.",
                )
            )

    def get_or_create_override(self, obj, occurrence_date: datetime.date):
        self.assert_valid_occurrence_date(obj, occurrence_date)

        parent_fk_id_field = f"{self.service.parent_fk_field}_id"
        if getattr(obj, parent_fk_id_field, None):
            return obj, False

        lookup = {self.service.parent_fk_field: obj, "recurrence_date": occurrence_date}
        override = self.service.model.objects.filter(**lookup).first()
        if override is not None:
            return override, False

        override = self.service.model.objects.create(**self.service._occurrence_override_defaults(obj, occurrence_date))
        return override, True

    def resolve_target(self, obj, occurrence_date: datetime.date | None = None):
        if obj.is_deleted_instance:
            raise ValueError(self.service._validation_error("occurrence_date", "Cannot access a deleted occurrence."))

        if occurrence_date is None:
            return obj

        target, _ = self.get_or_create_override(obj, occurrence_date)
        if target.is_deleted_instance:
            raise ValueError(self.service._validation_error("occurrence_date", "Cannot access a deleted occurrence."))
        return target

    def expand_parent(self, parent, from_date: datetime.date, to_date: datetime.date) -> list:
        anchor = self.service._get_anchor(parent)
        if anchor is None:
            return []

        overrides = {
            override.recurrence_date: override
            for override in self.service.model.objects.filter(
                **{self.service.parent_fk_field: parent},
                recurrence_date__gte=from_date,
                recurrence_date__lte=to_date,
            )
        }

        results = []
        for occurrence_date in expand_occurrences(parent.rrule, anchor, from_date, to_date):
            if occurrence_date in overrides:
                override = overrides[occurrence_date]
                if not override.is_deleted_instance:
                    results.append(override)
                continue

            virtual = copy.copy(parent)
            virtual._is_virtual = True
            self.service._apply_anchor_to_virtual(virtual, parent, occurrence_date)
            results.append(virtual)

        return results

    def parent_has_visible_occurrence(self, parent, from_date: datetime.date, to_date: datetime.date) -> bool:
        anchor = self.service._get_anchor(parent)
        if anchor is None:
            return False

        overrides = {
            override.recurrence_date: override
            for override in self.service.model.objects.filter(
                **{self.service.parent_fk_field: parent},
                recurrence_date__gte=from_date,
                recurrence_date__lte=to_date,
            )
        }

        for occurrence_date in expand_occurrences(parent.rrule, anchor, from_date, to_date):
            override = overrides.get(occurrence_date)
            if override is None:
                return True
            if not override.is_deleted_instance:
                return True

        return False

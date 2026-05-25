import datetime
from copy import deepcopy

from django.db.models import Q

from apps.calendar.models import Event
from apps.calendar.services.mutation_input import CalendarMutationInput
from apps.calendar.services.recurrence import BaseCalendarItemService
from apps.calendar.utils import coerce_recurrence_rule, serialize_recurrence_rule


class EventService(BaseCalendarItemService):
    model = Event
    parent_fk_field = "parent_event"
    attachment_folder_prefix = "events"

    @staticmethod
    def _shift_datetime_to_occurrence(
        anchor_datetime: datetime.datetime,
        occurrence_date: datetime.date,
    ) -> datetime.datetime:
        return anchor_datetime.replace(
            year=occurrence_date.year,
            month=occurrence_date.month,
            day=occurrence_date.day,
        )

    @classmethod
    def _shift_end_at_to_occurrence(
        cls,
        source_start_at: datetime.datetime,
        source_end_at: datetime.datetime | None,
        occurrence_start_at: datetime.datetime,
    ) -> datetime.datetime | None:
        if source_end_at is None:
            return None
        return occurrence_start_at + (source_end_at - source_start_at)

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def _get_non_recurring_qs(self, from_date: datetime.date, to_date: datetime.date):
        return Event.objects.filter(
            self._access_filter(),
            parent_event__isnull=True,
            rrule__isnull=True,
            start_at__date__gte=from_date,
            start_at__date__lte=to_date,
        )

    def _get_recurring_parents_qs(self, from_date: datetime.date, to_date: datetime.date):
        return Event.objects.filter(
            self._access_filter(),
            parent_event__isnull=True,
            rrule__isnull=False,
            start_at__date__lte=to_date,
        ).filter(Q(recurrence_end_date__isnull=True) | Q(recurrence_end_date__gte=from_date))

    def _get_anchor(self, parent) -> datetime.datetime | None:
        return parent.start_at

    def _apply_anchor_to_virtual(self, virtual, parent, occ_date: datetime.date) -> None:
        virtual.recurrence_date = occ_date
        virtual.comment_count = 0
        virtual.start_at = self._shift_datetime_to_occurrence(parent.start_at, occ_date)
        virtual.end_at = self._shift_end_at_to_occurrence(parent.start_at, parent.end_at, virtual.start_at)

    def _this_and_future_new_data(
        self, source_obj, mutation_input: CalendarMutationInput, recurrence_date: datetime.date
    ) -> dict:
        new_start = self._shift_datetime_to_occurrence(source_obj.start_at, recurrence_date)
        effective_start_value = mutation_input.get("start_at", new_start)
        effective_start = effective_start_value if isinstance(effective_start_value, datetime.datetime) else new_start
        new_rrule = (
            mutation_input.recurrence_rule
            if mutation_input.has_recurrence_rule
            else coerce_recurrence_rule(source_obj.rrule)
        )
        return {
            "creator_id": source_obj.creator_id,
            "title": mutation_input.get("title", source_obj.title),
            "description": mutation_input.get("description", source_obj.description),
            "event_type": mutation_input.get("event_type", source_obj.event_type),
            "access_type": mutation_input.get("access_type", source_obj.access_type),
            "access_family_ids": deepcopy(mutation_input.get("access_family_ids", source_obj.access_family_ids)),
            "access_close_group_ids": deepcopy(
                mutation_input.get("access_close_group_ids", source_obj.access_close_group_ids)
            ),
            "access_user_ids": deepcopy(mutation_input.get("access_user_ids", source_obj.access_user_ids)),
            "start_at": effective_start,
            "end_at": (
                mutation_input.get("end_at")
                if mutation_input.has_field("end_at")
                else (
                    self._shift_end_at_to_occurrence(source_obj.start_at, source_obj.end_at, effective_start)
                    if source_obj.end_at
                    else None
                )
            ),
            "all_day": mutation_input.get("all_day", source_obj.all_day),
            "reminder_datetime": mutation_input.get("reminder_datetime", source_obj.reminder_datetime),
            "reminder_types": deepcopy(mutation_input.get("reminder_types", source_obj.reminder_types)),
            "location": deepcopy(mutation_input.get("location", source_obj.location)),
            "attachments": deepcopy(source_obj.attachments),
            "parent_event": None,
            "rrule": serialize_recurrence_rule(new_rrule),
            "recurrence_date": None,
            "recurrence_end_date": self._extract_recurrence_end_date(new_rrule),
            "is_deleted_instance": False,
            "comment_count": 0,
        }

    def _tombstone_defaults(self, obj) -> dict:
        return {
            "creator_id": obj.creator_id,
            "title": obj.title,
            "start_at": obj.start_at,
            "end_at": obj.end_at,
            "rrule": None,
            "recurrence_end_date": None,
            "is_deleted_instance": True,
        }

    def _occurrence_override_defaults(self, obj, occurrence_date: datetime.date) -> dict:
        start_at = self._shift_datetime_to_occurrence(obj.start_at, occurrence_date)
        end_at = self._shift_end_at_to_occurrence(obj.start_at, obj.end_at, start_at)

        return {
            "creator_id": obj.creator_id,
            "title": obj.title,
            "description": obj.description,
            "event_type": obj.event_type,
            "access_type": obj.access_type,
            "access_family_ids": deepcopy(obj.access_family_ids),
            "access_close_group_ids": deepcopy(obj.access_close_group_ids),
            "access_user_ids": deepcopy(obj.access_user_ids),
            "start_at": start_at,
            "end_at": end_at,
            "all_day": obj.all_day,
            "reminder_datetime": obj.reminder_datetime,
            "reminder_types": deepcopy(obj.reminder_types),
            "location": deepcopy(obj.location),
            "attachments": deepcopy(obj.attachments),
            "parent_event": obj,
            "rrule": None,
            "recurrence_date": occurrence_date,
            "recurrence_end_date": None,
            "is_deleted_instance": False,
            "comment_count": 0,
        }

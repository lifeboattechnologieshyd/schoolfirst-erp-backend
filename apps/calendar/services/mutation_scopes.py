import datetime
from dataclasses import replace

from apps.calendar.services.mutation_input import CalendarMutationInput
from apps.calendar.utils import coerce_recurrence_rule, serialize_recurrence_rule


class BaseMutationScope:
    name = None

    def __init__(self, service):
        self.service = service

    def require_occurrence_date(self, occurrence_date: datetime.date | None) -> datetime.date:
        if occurrence_date:
            return occurrence_date
        raise ValueError({"occurrence_date": f"occurrence_date is required for scope='{self.name}'"})

    def update(self, obj, mutation_input: CalendarMutationInput, occurrence_date: datetime.date | None):
        raise NotImplementedError

    def delete(self, obj, occurrence_date: datetime.date | None):
        raise NotImplementedError


class AllMutationScope(BaseMutationScope):
    name = "all"

    def update(self, obj, mutation_input: CalendarMutationInput, occurrence_date: datetime.date | None):
        del occurrence_date
        model_values = mutation_input.to_model_values()

        self.service._validate_specific_access_user_ids(
            model_values.get("access_type", obj.access_type),
            model_values.get("access_user_ids", obj.access_user_ids),
        )
        if mutation_input.has_recurrence_rule:
            model_values["recurrence_end_date"] = self.service._extract_recurrence_end_date(
                mutation_input.recurrence_rule
            )
        if mutation_input.has_attachments:
            model_values["attachments"] = (
                None
                if mutation_input.attachments is None
                else self.service._resolve_attachments(
                    mutation_input.attachments,
                    self.service._attachment_prefix(obj),
                    allowed_existing_prefixes=self.service._attachment_prefixes(obj),
                )
            )
        for attr, value in model_values.items():
            setattr(obj, attr, value)
        obj.save()
        return obj

    def delete(self, obj, occurrence_date: datetime.date | None):
        del occurrence_date
        obj.delete()


class ThisMutationScope(BaseMutationScope):
    name = "this"

    def update(self, obj, mutation_input: CalendarMutationInput, occurrence_date: datetime.date | None):
        occurrence_date = self.require_occurrence_date(occurrence_date)
        model_values = mutation_input.to_model_values(include_recurrence_rule=False)

        override, _ = self.service._get_or_create_occurrence_override(obj, occurrence_date)
        self.service._validate_specific_access_user_ids(
            model_values.get("access_type", override.access_type),
            model_values.get("access_user_ids", override.access_user_ids),
        )
        for attr, value in model_values.items():
            setattr(override, attr, value)
        override.rrule = None
        override.recurrence_end_date = None
        override.is_deleted_instance = False
        if mutation_input.has_attachments and mutation_input.attachments is not None:
            override.attachments = self.service._resolve_attachments(
                mutation_input.attachments,
                self.service._attachment_prefix(override),
                allowed_existing_prefixes=self.service._attachment_prefixes(obj, override),
            )
        override.save()
        return override

    def delete(self, obj, occurrence_date: datetime.date | None):
        occurrence_date = self.require_occurrence_date(occurrence_date)

        override, _ = self.service._get_or_create_occurrence_override(obj, occurrence_date)
        for attr, value in self.service._tombstone_defaults(obj).items():
            setattr(override, attr, value)
        override.rrule = None
        override.recurrence_end_date = None
        override.is_deleted_instance = True
        override.save()


class ThisAndFutureMutationScope(BaseMutationScope):
    name = "this_and_future"

    def _truncate_parent_series(self, obj, occurrence_date: datetime.date) -> None:
        self.service._assert_valid_occurrence_date(obj, occurrence_date)
        until_str = (occurrence_date - datetime.timedelta(days=1)).isoformat()
        rrule_data = coerce_recurrence_rule(obj.rrule)
        if rrule_data is None:
            raise ValueError("Recurring parent must have an rrule.")

        updated_rrule = replace(rrule_data, until=until_str, count=None)
        obj.rrule = serialize_recurrence_rule(updated_rrule)
        obj.recurrence_end_date = self.service._extract_recurrence_end_date(updated_rrule)
        obj.save()

        self.service.model.objects.filter(
            **{self.service.parent_fk_field: obj},
            recurrence_date__gte=occurrence_date,
        ).delete()

    def update(self, obj, mutation_input: CalendarMutationInput, occurrence_date: datetime.date | None):
        occurrence_date = self.require_occurrence_date(occurrence_date)
        self._truncate_parent_series(obj, occurrence_date)

        new_data = self.service._this_and_future_new_data(obj, mutation_input, occurrence_date)
        self.service._validate_specific_access_user_ids(
            new_data.get("access_type"),
            new_data.get("access_user_ids"),
        )
        new_obj = self.service.model.objects.create(**new_data)
        if mutation_input.has_attachments and mutation_input.attachments is not None:
            new_obj.attachments = self.service._resolve_attachments(
                mutation_input.attachments,
                self.service._attachment_prefix(new_obj),
                allowed_existing_prefixes=self.service._attachment_prefixes(obj, new_obj),
            )
            new_obj.save(update_fields=["attachments"])
        return new_obj

    def delete(self, obj, occurrence_date: datetime.date | None):
        occurrence_date = self.require_occurrence_date(occurrence_date)
        self._truncate_parent_series(obj, occurrence_date)


class CalendarMutationScopeRegistry:
    def __init__(self, service):
        self.service = service
        self._handlers = {
            handler.name: handler
            for handler in (
                AllMutationScope(service),
                ThisMutationScope(service),
                ThisAndFutureMutationScope(service),
            )
        }

    def update(self, obj, validated_data: dict | CalendarMutationInput, update_scope: str = "all"):
        mutation_input = CalendarMutationInput.from_validated_data(validated_data)
        scope_name = "all" if obj.rrule is None else update_scope
        occurrence_date = mutation_input.recurrence_date
        handler = self._handlers.get(scope_name)
        if handler is None:
            raise ValueError(f"Unknown update_scope: {update_scope}")
        return handler.update(obj, mutation_input, occurrence_date)

    def delete(self, obj, scope: str = "all", recurrence_date=None):
        scope_name = "all" if obj.rrule is None else scope
        handler = self._handlers.get(scope_name)
        if handler is None:
            raise ValueError(f"Unknown scope: {scope}")
        handler.delete(obj, recurrence_date)

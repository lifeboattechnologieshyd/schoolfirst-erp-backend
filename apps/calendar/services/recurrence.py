"""Shared recurrence-aware CRUD for Event and Task."""

import datetime
import posixpath
from typing import Any, Protocol, cast

from django.core.files.storage import default_storage
from django.db import models, transaction

from apps.calendar.services.access import AccessResolver
from apps.calendar.services.access_policy import validate_access_user_ids
from apps.calendar.services.mutation_input import CalendarMutationInput
from apps.calendar.services.mutation_scopes import CalendarMutationScopeRegistry
from apps.calendar.services.occurrences import CalendarOccurrenceManager
from apps.calendar.utils import RecurrenceRuleData, coerce_recurrence_rule
from shared.utils.files import move_file


class CalendarModelClass(Protocol):
    objects: models.Manager[Any]


class BaseCalendarItemService:
    model: CalendarModelClass | None = None
    parent_fk_field: str | None = None
    attachment_folder_prefix: str | None = None

    def __init__(self, user):
        self.user = user
        self.resolver = AccessResolver(user)
        self.occurrences = CalendarOccurrenceManager(self)
        self.mutation_scopes = CalendarMutationScopeRegistry(self)

    def _access_filter(self):
        return self.resolver.build_access_filter()

    def _model_class(self) -> CalendarModelClass:
        if self.model is None:
            raise NotImplementedError("Subclasses must define model")
        return self.model

    def get_visible_qs(self):
        return self._model_class().objects.filter(self._access_filter())

    def get_single(self, pk):
        return self.get_visible_qs().get(pk=pk)

    @staticmethod
    def _extract_recurrence_end_date(rrule: dict | RecurrenceRuleData | None) -> datetime.date | None:
        normalized_rule = coerce_recurrence_rule(rrule)
        if normalized_rule is None or not normalized_rule.until:
            return None
        return datetime.date.fromisoformat(normalized_rule.until)

    @staticmethod
    def _validation_error(field: str, message: str) -> dict:
        return {field: message}

    def _validate_specific_access_user_ids(
        self,
        access_type: str | None,
        access_user_ids: list[str] | None,
    ) -> None:
        error = validate_access_user_ids(
            access_user_ids=access_user_ids,
            allowed_user_ids=set(self.resolver.build_access_scope().access_user_id_candidates),
        )
        if error:
            raise ValueError(error)

    @staticmethod
    def _normalize_attachment_path(raw_path) -> str:
        if not isinstance(raw_path, str):
            raise ValueError(
                BaseCalendarItemService._validation_error("attachments", "Each attachment path must be a string.")
            )

        candidate = raw_path.strip()
        if not candidate or "\\" in candidate or "\x00" in candidate:
            raise ValueError(
                BaseCalendarItemService._validation_error("attachments", f"Invalid attachment path: {raw_path}")
            )

        normalized = posixpath.normpath(candidate)
        if normalized in {".", ".."} or normalized.startswith("/") or normalized.startswith("../"):
            raise ValueError(
                BaseCalendarItemService._validation_error("attachments", f"Invalid attachment path: {raw_path}")
            )

        return normalized

    def _attachment_prefix(self, obj) -> str:
        return f"{self.attachment_folder_prefix}/{obj.id}"

    def _attachment_prefixes(self, *objects) -> tuple[str, ...]:
        return tuple(self._attachment_prefix(obj) for obj in objects if obj is not None)

    def _resolve_attachments(
        self,
        attachments: list,
        dest_folder: str,
        allowed_existing_prefixes: tuple[str, ...] = (),
    ) -> list:
        if not isinstance(attachments, list):
            raise ValueError(self._validation_error("attachments", "attachments must be a list of file paths."))

        expected_temp_prefix = f"temp/{self.user.id}/"
        resolved = []

        for raw_path in attachments:
            path = self._normalize_attachment_path(raw_path)

            if path.startswith("temp/"):
                if not path.startswith(expected_temp_prefix):
                    raise ValueError(
                        self._validation_error(
                            "attachments", f"Attachment path does not belong to the current user: {raw_path}"
                        )
                    )
                if not default_storage.exists(path):
                    raise ValueError(
                        self._validation_error(
                            "attachments", f"Attachment path is invalid or no longer available: {raw_path}"
                        )
                    )
                moved_path = move_file(path, dest_folder)
                if not moved_path:
                    raise ValueError(
                        self._validation_error(
                            "attachments", f"Attachment path is invalid or no longer available: {raw_path}"
                        )
                    )
                resolved.append(moved_path)
                continue

            if any(path.startswith(f"{prefix}/") for prefix in allowed_existing_prefixes):
                if not default_storage.exists(path):
                    raise ValueError(
                        self._validation_error(
                            "attachments", f"Attachment path is invalid or no longer available: {raw_path}"
                        )
                    )
                resolved.append(path)
                continue

            raise ValueError(self._validation_error("attachments", f"Invalid attachment path: {raw_path}"))

        return resolved

    def _assert_valid_occurrence_date(self, obj, occurrence_date: datetime.date) -> None:
        self.occurrences.assert_valid_occurrence_date(obj, occurrence_date)

    def _get_non_recurring_qs(self, from_date: datetime.date, to_date: datetime.date):
        raise NotImplementedError

    def _get_recurring_parents_qs(self, from_date: datetime.date, to_date: datetime.date):
        raise NotImplementedError

    def _get_anchor(self, parent) -> datetime.datetime | None:
        raise NotImplementedError

    def _apply_anchor_to_virtual(self, virtual, parent, occ_date: datetime.date) -> None:
        raise NotImplementedError

    def _this_and_future_new_data(
        self, source_obj, mutation_input: CalendarMutationInput, recurrence_date: datetime.date
    ) -> dict:
        raise NotImplementedError

    def _tombstone_defaults(self, obj) -> dict:
        raise NotImplementedError

    def _occurrence_override_defaults(self, obj, occurrence_date: datetime.date) -> dict:
        raise NotImplementedError

    def _get_or_create_occurrence_override(self, obj, occurrence_date: datetime.date):
        return self.occurrences.get_or_create_override(obj, occurrence_date)

    def resolve_occurrence_target(self, obj, occurrence_date: datetime.date | None = None):
        return self.occurrences.resolve_target(obj, occurrence_date)

    def create(self, validated_data: dict | CalendarMutationInput):
        mutation_input = CalendarMutationInput.from_validated_data(validated_data)
        model_values = mutation_input.to_model_values()
        model_values["creator_id"] = self.user.id
        model_values["recurrence_end_date"] = self._extract_recurrence_end_date(mutation_input.recurrence_rule)

        raw_access_type = model_values.get("access_type")
        access_type = raw_access_type if isinstance(raw_access_type, str) else None

        raw_access_user_ids = model_values.get("access_user_ids")
        access_user_ids = (
            cast(list[str], raw_access_user_ids)
            if isinstance(raw_access_user_ids, list)
            and all(isinstance(user_id, str) for user_id in raw_access_user_ids)
            else None
        )

        self._validate_specific_access_user_ids(
            access_type,
            access_user_ids,
        )
        with transaction.atomic():
            obj = self._model_class().objects.create(**model_values)
            if mutation_input.attachments is not None:
                obj.attachments = self._resolve_attachments(mutation_input.attachments, self._attachment_prefix(obj))
                obj.save(update_fields=["attachments"])
        return obj

    def update(self, obj, validated_data: dict | CalendarMutationInput, update_scope: str = "all"):
        return self.mutation_scopes.update(obj, validated_data, update_scope)

    def delete(self, obj, scope: str = "all", recurrence_date=None):
        return self.mutation_scopes.delete(obj, scope, recurrence_date)

    def expand_for_range(self, from_date: datetime.date, to_date: datetime.date) -> list:
        non_recurring = list(self._get_non_recurring_qs(from_date, to_date))
        recurring_parents = list(self._get_recurring_parents_qs(from_date, to_date))

        results = list(non_recurring)

        for parent in recurring_parents:
            results.extend(self.occurrences.expand_parent(parent, from_date, to_date))

        return results

    def collapse_for_range(self, from_date: datetime.date, to_date: datetime.date) -> list:
        non_recurring = list(self._get_non_recurring_qs(from_date, to_date))
        recurring_parents = list(self._get_recurring_parents_qs(from_date, to_date))

        results = list(non_recurring)
        for parent in recurring_parents:
            if self.occurrences.parent_has_visible_occurrence(parent, from_date, to_date):
                results.append(parent)

        return results

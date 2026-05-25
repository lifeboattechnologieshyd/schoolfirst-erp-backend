import datetime
from copy import deepcopy
from typing import Any, cast

from django.db.models import Q
from django.utils import timezone

from apps.calendar.enums import TaskStatus
from apps.calendar.models import Task
from apps.calendar.services.access import assert_is_creator
from apps.calendar.services.mutation_input import CalendarMutationInput
from apps.calendar.services.recurrence import BaseCalendarItemService
from apps.calendar.utils import coerce_recurrence_rule, serialize_recurrence_rule


class TaskService(BaseCalendarItemService):
    model = Task
    parent_fk_field = "parent_task"
    attachment_folder_prefix = "tasks"

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def _get_non_recurring_qs(self, from_date: datetime.date, to_date: datetime.date):
        return Task.objects.filter(
            self._access_filter(),
            parent_task__isnull=True,
            rrule__isnull=True,
            is_visible=True,
        ).filter(
            Q(deadline_datetime__date__gte=from_date, deadline_datetime__date__lte=to_date)
            | Q(deadline_datetime__isnull=True)
        )

    def _get_recurring_parents_qs(self, from_date: datetime.date, to_date: datetime.date):
        return Task.objects.filter(
            self._access_filter(),
            parent_task__isnull=True,
            rrule__isnull=False,
            is_visible=True,
        ).filter(Q(recurrence_end_date__isnull=True) | Q(recurrence_end_date__gte=from_date))

    def _get_anchor(self, parent) -> datetime.datetime | None:
        return parent.deadline_datetime

    def _apply_anchor_to_virtual(self, virtual, parent, occ_date: datetime.date) -> None:
        virtual.recurrence_date = occ_date
        virtual.comment_count = 0
        if parent.deadline_datetime:
            virtual.deadline_datetime = parent.deadline_datetime.replace(
                year=occ_date.year,
                month=occ_date.month,
                day=occ_date.day,
            )

    def _this_and_future_new_data(
        self, source_obj, mutation_input: CalendarMutationInput, recurrence_date: datetime.date
    ) -> dict:
        new_rrule = (
            mutation_input.recurrence_rule
            if mutation_input.has_recurrence_rule
            else coerce_recurrence_rule(source_obj.rrule)
        )
        new_data = {
            "creator_id": source_obj.creator_id,
            "title": mutation_input.get("title", source_obj.title),
            "description": mutation_input.get("description", source_obj.description),
            "task_type": mutation_input.get("task_type", source_obj.task_type),
            "access_type": mutation_input.get("access_type", source_obj.access_type),
            "access_family_ids": deepcopy(mutation_input.get("access_family_ids", source_obj.access_family_ids)),
            "access_close_group_ids": deepcopy(
                mutation_input.get("access_close_group_ids", source_obj.access_close_group_ids)
            ),
            "access_user_ids": deepcopy(mutation_input.get("access_user_ids", source_obj.access_user_ids)),
            "status": mutation_input.get("status", source_obj.status),
            "done_by": mutation_input.get("done_by", source_obj.done_by),
            "completed_at": mutation_input.get("completed_at", source_obj.completed_at),
            "acknowledged_at": mutation_input.get("acknowledged_at", source_obj.acknowledged_at),
            "is_visible": mutation_input.get("is_visible", source_obj.is_visible),
            "priority": mutation_input.get("priority", source_obj.priority),
            "agent_assist": mutation_input.get("agent_assist", source_obj.agent_assist),
            "deadline_datetime": mutation_input.get("deadline_datetime", source_obj.deadline_datetime),
            "reminder_datetime": mutation_input.get("reminder_datetime", source_obj.reminder_datetime),
            "reminder_types": deepcopy(mutation_input.get("reminder_types", source_obj.reminder_types)),
            "location": deepcopy(mutation_input.get("location", source_obj.location)),
            "attachments": deepcopy(source_obj.attachments),
            "parent_task": None,
            "rrule": serialize_recurrence_rule(new_rrule),
            "recurrence_date": None,
            "recurrence_end_date": self._extract_recurrence_end_date(new_rrule),
            "is_deleted_instance": False,
            "comment_count": 0,
        }
        if mutation_input.has_field("deadline_datetime"):
            new_data["deadline_datetime"] = mutation_input.get("deadline_datetime")
        elif source_obj.deadline_datetime:
            new_data["deadline_datetime"] = source_obj.deadline_datetime.replace(
                year=recurrence_date.year,
                month=recurrence_date.month,
                day=recurrence_date.day,
            )
        return new_data

    def _tombstone_defaults(self, obj) -> dict:
        return {
            "creator_id": obj.creator_id,
            "title": obj.title,
            "rrule": None,
            "recurrence_end_date": None,
            "is_deleted_instance": True,
        }

    def _occurrence_override_defaults(self, obj, occurrence_date: datetime.date) -> dict:
        deadline_datetime = None
        if obj.deadline_datetime:
            deadline_datetime = obj.deadline_datetime.replace(
                year=occurrence_date.year,
                month=occurrence_date.month,
                day=occurrence_date.day,
            )

        return {
            "creator_id": obj.creator_id,
            "title": obj.title,
            "description": obj.description,
            "task_type": obj.task_type,
            "access_type": obj.access_type,
            "access_family_ids": deepcopy(obj.access_family_ids),
            "access_close_group_ids": deepcopy(obj.access_close_group_ids),
            "access_user_ids": deepcopy(obj.access_user_ids),
            "status": obj.status,
            "done_by": obj.done_by,
            "completed_at": obj.completed_at,
            "acknowledged_at": obj.acknowledged_at,
            "is_visible": obj.is_visible,
            "priority": obj.priority,
            "agent_assist": obj.agent_assist,
            "deadline_datetime": deadline_datetime,
            "reminder_datetime": obj.reminder_datetime,
            "reminder_types": deepcopy(obj.reminder_types),
            "location": deepcopy(obj.location),
            "attachments": deepcopy(obj.attachments),
            "parent_task": obj,
            "rrule": None,
            "recurrence_date": occurrence_date,
            "recurrence_end_date": None,
            "is_deleted_instance": False,
            "comment_count": 0,
        }

    # ------------------------------------------------------------------
    # Status update (any member with access)
    # ------------------------------------------------------------------

    def update_status(self, task: Task, new_status: str) -> Task:
        task.status = cast(Any, new_status)
        if new_status == TaskStatus.DONE:
            task.done_by = cast(Any, self.user.id)
            task.completed_at = cast(Any, timezone.now())
            if str(task.creator_id) == str(self.user.id):
                task.is_visible = cast(Any, False)
        else:
            task.done_by = cast(Any, None)
            task.completed_at = cast(Any, None)
        task.save()
        return task

    # ------------------------------------------------------------------
    # Completion review (creator only — accept or reject a done task)
    # ------------------------------------------------------------------

    def review_completion(self, task: Task, action: str) -> Task:
        """
        Creator reviews a task marked done by someone else.

        accept — hides the task (is_visible=False, acknowledged_at=now).
        reject — reverts to pending (status=pending, done_by/completed_at cleared,
                 is_visible=True, acknowledged_at cleared).

        Only callable when the task is in DONE status.
        """
        assert_is_creator(self.user, task)
        if task.status != TaskStatus.DONE:
            raise ValueError({"action": "Task must be in 'done' status to accept or reject."})
        if action == "accept":
            task.acknowledged_at = cast(Any, timezone.now())
            task.is_visible = cast(Any, False)
            task.save(update_fields=["acknowledged_at", "is_visible"])
        elif action == "reject":
            task.status = cast(Any, TaskStatus.PENDING)
            task.done_by = cast(Any, None)
            task.completed_at = cast(Any, None)
            task.acknowledged_at = cast(Any, None)
            task.is_visible = cast(Any, True)
            task.save(update_fields=["status", "done_by", "completed_at", "acknowledged_at", "is_visible"])
        else:
            raise ValueError({"action": "action must be 'accept' or 'reject'."})
        return task

    # Keep the old method name as an alias so existing internal callers aren't broken.
    def acknowledge(self, task: Task) -> Task:
        return self.review_completion(task, "accept")

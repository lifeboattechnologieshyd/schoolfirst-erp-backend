from apps.calendar.services.event import EventService
from apps.calendar.services.query_planner import (
    BaseCalendarListQuery,
    build_queryset_ordering,
    parse_query_bool,
    parse_sort_param,
    sort_items_by_fields,
)
from apps.calendar.services.task import TaskService

_ALLOWED_EVENT_SORT_FIELDS = frozenset({"start_at", "created_at", "updated_at"})
_DEFAULT_EVENT_SORT = ["start_at"]

_ALLOWED_TASK_SORT_FIELDS = frozenset({"deadline_datetime", "completed_at", "status", "priority", "created_at"})
_DEFAULT_TASK_SORT = ["deadline_datetime"]


class EventListQuery(BaseCalendarListQuery):
    def __init__(self, user):
        super().__init__(EventService(user))

    def build_ranged_items(self, params, from_date, to_date) -> list:
        order = parse_sort_param(params.get("sort"), _ALLOWED_EVENT_SORT_FIELDS, _DEFAULT_EVENT_SORT)
        results = self.service.collapse_for_range(from_date, to_date)
        if params.get("event_type"):
            results = [event for event in results if event.event_type == params["event_type"]]
        if params.get("creator_id"):
            results = [event for event in results if str(event.creator_id) == params["creator_id"]]
        if params.get("access_type"):
            results = [event for event in results if event.access_type == params["access_type"]]
        return sort_items_by_fields(results, order)

    def build_queryset(self, params, from_date, to_date):
        order = parse_sort_param(params.get("sort"), _ALLOWED_EVENT_SORT_FIELDS, _DEFAULT_EVENT_SORT)
        qs = self.service.get_visible_qs().filter(parent_event__isnull=True)

        if from_date:
            qs = qs.filter(start_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(start_at__date__lte=to_date)
        if params.get("event_type"):
            qs = qs.filter(event_type=params["event_type"])
        if params.get("creator_id"):
            qs = qs.filter(creator_id=params["creator_id"])
        if params.get("access_type"):
            qs = qs.filter(access_type=params["access_type"])

        return qs.order_by(*build_queryset_ordering(order))


def _filter_task_results(results: list, params):
    if params.get("status"):
        results = [task for task in results if task.status == params["status"]]
    if params.get("priority"):
        results = [task for task in results if task.priority == params["priority"]]
    if params.get("creator_id"):
        results = [task for task in results if str(task.creator_id) == params["creator_id"]]
    if params.get("access_type"):
        results = [task for task in results if task.access_type == params["access_type"]]

    agent_assist = parse_query_bool(params.get("agent_assist"))
    if agent_assist is not None:
        results = [task for task in results if task.agent_assist == agent_assist]

    is_visible = parse_query_bool(params.get("is_visible"))
    if is_visible is not None:
        results = [task for task in results if task.is_visible == is_visible]

    if params.get("task_type"):
        results = [task for task in results if task.task_type == params["task_type"]]

    return results


def _filter_task_queryset(qs, params, from_date, to_date):
    if from_date:
        qs = qs.filter(deadline_datetime__date__gte=from_date)
    if to_date:
        qs = qs.filter(deadline_datetime__date__lte=to_date)
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("priority"):
        qs = qs.filter(priority=params["priority"])
    if params.get("creator_id"):
        qs = qs.filter(creator_id=params["creator_id"])
    if params.get("access_type"):
        qs = qs.filter(access_type=params["access_type"])
    if params.get("agent_assist") is not None:
        qs = qs.filter(agent_assist=params["agent_assist"].lower() == "true")
    if params.get("is_visible") is not None:
        qs = qs.filter(is_visible=params["is_visible"].lower() == "true")
    if params.get("task_type"):
        qs = qs.filter(task_type=params["task_type"])

    return qs


class TaskListQuery(BaseCalendarListQuery):
    def __init__(self, user):
        super().__init__(TaskService(user))

    def build_ranged_items(self, params, from_date, to_date) -> list:
        order = parse_sort_param(params.get("sort"), _ALLOWED_TASK_SORT_FIELDS, _DEFAULT_TASK_SORT)
        results = _filter_task_results(self.service.collapse_for_range(from_date, to_date), params)
        return sort_items_by_fields(results, order)

    def build_queryset(self, params, from_date, to_date):
        order = parse_sort_param(params.get("sort"), _ALLOWED_TASK_SORT_FIELDS, _DEFAULT_TASK_SORT)
        qs = _filter_task_queryset(
            self.service.get_visible_qs().filter(parent_task__isnull=True),
            params,
            from_date,
            to_date,
        )
        return qs.order_by(*build_queryset_ordering(order))

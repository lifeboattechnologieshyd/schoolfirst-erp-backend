import datetime

from apps.calendar.enums import TaskStatus
from apps.calendar.models.general_event import GeneralEvent
from apps.calendar.services.event import EventService
from apps.calendar.services.query_planner import sort_items_by_field
from apps.calendar.services.task import TaskService


class CalendarSummaryService:
    def __init__(self, user):
        self.user = user

    def get_summary_view(
        self,
        from_date: datetime.date,
        to_date: datetime.date,
    ) -> dict:
        """
        Return a dict with raw model/virtual-occurrence lists.
        Serialization is the caller's responsibility so that request context
        (e.g. URL helpers, field visibility) can be threaded through.
        """
        event_service = EventService(self.user)
        task_service = TaskService(self.user)
        events = sort_items_by_field(event_service.collapse_for_range(from_date, to_date), "start_at")
        all_tasks = sort_items_by_field(task_service.collapse_for_range(from_date, to_date), "deadline_datetime")
        tasks = [t for t in all_tasks if t.status != TaskStatus.DONE]
        general_events = list(
            GeneralEvent.objects.filter(
                event_at__date__gte=from_date,
                event_at__date__lte=to_date,
            ).order_by("event_at")
        )

        return {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "events": events,
            "tasks": tasks,
            "general_events": general_events,
        }


class CalendarDayService:
    def __init__(self, user):
        self.user = user

    def get_day_view(self, date: datetime.date) -> dict:
        event_service = EventService(self.user)
        task_service = TaskService(self.user)

        events = sort_items_by_field(event_service.expand_for_range(date, date), "start_at")
        all_tasks = sort_items_by_field(task_service.expand_for_range(date, date), "deadline_datetime")
        tasks = [t for t in all_tasks if t.status != TaskStatus.DONE]
        general_events = list(
            GeneralEvent.objects.filter(
                event_at__date=date,
            ).order_by("event_at")
        )

        return {
            "date": date.isoformat(),
            "events": events,
            "tasks": tasks,
            "general_events": general_events,
        }

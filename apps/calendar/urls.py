from django.urls import path

from apps.calendar.views import (
    CalendarDayView,
    CommentDestroyView,
    EventCommentListCreateView,
    EventDetailView,
    EventListCreateView,
    TaskCommentListCreateView,
    TaskDetailView,
    TaskListCreateView,
    TaskStatusAcknowledgeView,
    TaskStatusView,
    UnifiedCalendarView,
)

urlpatterns = [
    # Unified calendar
    path("v1/calendar", UnifiedCalendarView.as_view(), name="calendar-unified"),
    path("v1/calendar/day", CalendarDayView.as_view(), name="calendar-day"),
    # Events
    path("v1/calendar/events", EventListCreateView.as_view(), name="calendar-event-list-create"),
    path("v1/calendar/events/<uuid:pk>", EventDetailView.as_view(), name="calendar-event-detail"),
    path(
        "v1/calendar/events/<uuid:pk>/comments",
        EventCommentListCreateView.as_view(),
        name="calendar-event-comments",
    ),
    # Tasks
    path("v1/calendar/tasks", TaskListCreateView.as_view(), name="calendar-task-list-create"),
    path("v1/calendar/tasks/<uuid:pk>", TaskDetailView.as_view(), name="calendar-task-detail"),
    path("v1/calendar/tasks/<uuid:pk>/status", TaskStatusView.as_view(), name="calendar-task-status"),
    path(
        "v1/calendar/tasks/<uuid:pk>/status/acknowledge",
        TaskStatusAcknowledgeView.as_view(),
        name="calendar-task-status-acknowledge",
    ),
    path("v1/calendar/tasks/<uuid:pk>/comments", TaskCommentListCreateView.as_view(), name="calendar-task-comments"),
    # Comments (delete only — creation is nested under events/tasks)
    path("v1/calendar/comments/<uuid:pk>", CommentDestroyView.as_view(), name="calendar-comment-destroy"),
]

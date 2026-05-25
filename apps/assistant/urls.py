"""
URL Configuration for the Assistant application.
Defines endpoints for threads, messages, and chat interactions.
"""

from django.urls import path

from apps.assistant.views import (
    ChatView,
    MessageListView,
    ThreadListCreateView,
    ThreadRetrieveUpdateDestroyView,
)

urlpatterns = [
    path("v1/assistant/threads", ThreadListCreateView.as_view(), name="thread-list-create"),
    path("v1/assistant/threads/<uuid:pk>", ThreadRetrieveUpdateDestroyView.as_view(), name="thread-detail"),
    path("v1/assistant/threads/<uuid:thread_id>/chat", ChatView.as_view(), name="thread-chat"),
    path("v1/assistant/threads/<uuid:thread_id>/messages", MessageListView.as_view(), name="thread-messages"),
]

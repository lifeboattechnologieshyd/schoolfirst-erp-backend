"""
Thread Management Views for the Assistant application.
Provides CRUD operations for conversation threads.
"""

from typing import Any

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.assistant.enums import ThreadStatus
from apps.assistant.models import Thread
from apps.assistant.serializers import ThreadSerializer
from shared.mixins.drf_views import CustomListCreateAPIView, CustomRetrieveUpdateDestroyAPIView


class ThreadListCreateView(CustomListCreateAPIView):
    """
    List all threads and create new threads.
    GET /api/assistant/threads/ - List all threads
    POST /api/assistant/threads/ - Create a new thread
    """

    serializer_class = ThreadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Thread]:
        # Return active threads belonging to the current user (exclude soft-deleted)
        return Thread.objects.filter(user_id=self.request.user.id).exclude(status=ThreadStatus.DELETED)

    def perform_create(self, serializer: BaseSerializer) -> None:
        # Assign current user to the thread
        serializer.save(user_id=self.request.user.id)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().create(request, *args, **kwargs)
        # Convert 201 Created to 200 OK for consistent API behavior
        if response.status_code == status.HTTP_201_CREATED:
            response.status_code = status.HTTP_200_OK
        return response


class ThreadRetrieveUpdateDestroyView(CustomRetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, and delete a specific thread.
    GET /api/assistant/threads/{id}/ - Retrieve thread details
    PATCH /api/assistant/threads/{id}/ - Update thread (partial)
    PUT /api/assistant/threads/{id}/ - Update thread (full)
    DELETE /api/assistant/threads/{id}/ - Delete thread
    """

    serializer_class = ThreadSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self) -> QuerySet[Thread]:
        # Return threads belonging to the current user
        return Thread.objects.filter(user_id=self.request.user.id)

from typing import Any

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.core.models.close_group import CloseGroupMember
from apps.core.models.user import UserMaster
from apps.core.serializers.close_group import (
    CloseGroupAddedMeSerializer,
    CloseGroupMemberAddSerializer,
    CloseGroupMemberSerializer,
)
from apps.core.services.close_group_service import CloseGroupService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomListAPIView, CustomListCreateAPIView, CustomRetrieveUpdateDestroyAPIView
from shared.mixins.pagination import CustomPageNumberPagination


class CloseGroupMemberListCreateView(CustomListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method == "POST":
            return CloseGroupMemberAddSerializer
        return CloseGroupMemberSerializer

    def get_queryset(self) -> QuerySet[CloseGroupMember]:
        close_group_id = self.kwargs["close_group_id"]
        return CloseGroupService.list_members(user=self.request.user, close_group_id=close_group_id)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            email = serializer.validated_data.get("email")
            close_group_id = self.kwargs["close_group_id"]
            member = CloseGroupService.add_member(user=self.request.user, email=email, close_group_id=close_group_id)
            response_serializer = CloseGroupMemberSerializer(member, context=self.get_serializer_context())
            return self.build_response(
                success=True,
                message="Member added to your close group.",
                data=response_serializer.data,
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(e.detail),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class CloseGroupMemberDeleteView(CustomRetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CloseGroupMemberSerializer
    lookup_url_kwarg = "member_id"

    def get_queryset(self) -> QuerySet[CloseGroupMember]:
        close_group_id = self.kwargs["close_group_id"]
        return CloseGroupService.list_members(user=self.request.user, close_group_id=close_group_id)

    def perform_destroy(self, instance: CloseGroupMember) -> None:
        close_group_id = self.kwargs["close_group_id"]
        CloseGroupService.remove_member(user=self.request.user, member_id=instance.id, close_group_id=close_group_id)


class CloseGroupAddedMeView(CustomListAPIView):
    """
    Return users who added me to their close group but I have not added back.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    serializer_class = CloseGroupAddedMeSerializer

    def get_queryset(self) -> list[UserMaster]:
        return CloseGroupService.list_added_me(user=self.request.user)

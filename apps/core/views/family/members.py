from typing import Any

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.core.models.family import FamilyMember
from apps.core.serializers.family import FamilyMemberAddSerializer, FamilyMemberSerializer
from apps.core.services.family_service import FamilyService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomListCreateAPIView, CustomRetrieveUpdateDestroyAPIView
from shared.mixins.pagination import CustomPageNumberPagination


class FamilyMemberListCreateView(CustomListCreateAPIView):
    """GET: list members. POST: add member by email."""

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method == "POST":
            return FamilyMemberAddSerializer
        return FamilyMemberSerializer

    def get_queryset(self) -> QuerySet[FamilyMember]:
        family_id = self.kwargs.get("family_id")
        return FamilyService.list_members(family_id=family_id, user_id=self.request.user.id)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            serializer = FamilyMemberAddSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            member = FamilyService.add_member(
                family_id=self.kwargs.get("family_id"),
                owner_id=request.user.id,
                email=serializer.validated_data.get("email"),
                relation=serializer.validated_data.get("relation"),
                first_name=serializer.validated_data.get("first_name"),
                last_name=serializer.validated_data.get("last_name"),
                gender=serializer.validated_data.get("gender"),
            )
            data = FamilyMemberSerializer(member, context=self.get_serializer_context()).data
            return self.build_response(
                success=True, message="Member added to your family.", data=data, status=status.HTTP_201_CREATED
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


class FamilyMemberDeleteView(CustomRetrieveUpdateDestroyAPIView):
    """DELETE: remove member (owner action)."""

    permission_classes = [IsAuthenticated]
    serializer_class = FamilyMemberSerializer
    lookup_url_kwarg = "member_id"

    def get_queryset(self) -> QuerySet[FamilyMember]:
        family_id = self.kwargs.get("family_id")
        return FamilyMember.objects.filter(family_id=family_id, family__owner=self.request.user)

    def perform_destroy(self, instance: FamilyMember) -> None:
        FamilyService.remove_member(
            family_id=self.kwargs.get("family_id"),
            owner_id=self.request.user.id,
            member_id=instance.id,
        )

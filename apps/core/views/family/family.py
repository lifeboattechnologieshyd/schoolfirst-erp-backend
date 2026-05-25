from typing import Any

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.core.models.family import Family
from apps.core.serializers.family import FamilyCreateSerializer, FamilyDetailSerializer, FamilySerializer
from apps.core.services.family_service import FamilyService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomListCreateAPIView, CustomRetrieveUpdateDestroyAPIView
from shared.mixins.pagination import CustomPageNumberPagination


class FamilyListCreateView(CustomListCreateAPIView):
    """GET: list user's families. POST: create family."""

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method == "POST":
            return FamilyCreateSerializer
        return FamilySerializer

    def get_queryset(self) -> QuerySet[Family]:
        return FamilyService.list_user_families(self.request.user.id)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            serializer = FamilyCreateSerializer(data=request.data, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            family = FamilyService.create_family(
                user=request.user,
                name=serializer.validated_data.get("name"),
                family_picture=serializer.validated_data.get("family_picture"),
            )
            data = FamilySerializer(family, context=self.get_serializer_context()).data
            return self.build_response(
                success=True, message="Family created successfully.", data=data, status=status.HTTP_201_CREATED
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


class FamilyDetailView(CustomRetrieveUpdateDestroyAPIView):
    """GET: family detail with members. DELETE: delete family."""

    permission_classes = [IsAuthenticated]
    serializer_class = FamilyDetailSerializer
    lookup_url_kwarg = "family_id"

    def get_object(self) -> Family:
        family_id = self.kwargs.get(self.lookup_url_kwarg)
        return FamilyService.get_family(family_id=family_id, user_id=self.request.user.id)

    def perform_destroy(self, instance: Family) -> None:
        family_id = self.kwargs.get(self.lookup_url_kwarg)
        FamilyService.delete_family(family_id=family_id, owner_id=self.request.user.id)

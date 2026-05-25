from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.models.close_group import CloseGroup
from apps.core.serializers.close_group import CloseGroupSerializer
from apps.core.services.close_group_service import CloseGroupService
from shared.mixins.drf_views import CustomListAPIView, CustomRetrieveAPIView


class CloseGroupListView(CustomListAPIView):
    """GET v1/close-group — list all close groups owned by the requesting user."""

    permission_classes = [IsAuthenticated]
    serializer_class = CloseGroupSerializer

    def get_queryset(self):
        return CloseGroup.objects.filter(owner=self.request.user, is_active=True)

    def list(self, request: Request, *args, **kwargs) -> Response:
        # Auto-create the default group if the user has none yet.
        CloseGroupService.get_or_create_default_group(request.user)
        return super().list(request, *args, **kwargs)


class CloseGroupDetailView(CustomRetrieveAPIView):
    """GET v1/close-group/<close_group_id> — single group detail (owner only)."""

    permission_classes = [IsAuthenticated]
    serializer_class = CloseGroupSerializer
    lookup_url_kwarg = "close_group_id"

    def get_queryset(self):
        return CloseGroup.objects.filter(owner=self.request.user, is_active=True)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return self.build_response(
            success=True,
            data=serializer.data,
            status=status.HTTP_200_OK,
        )

from typing import Any

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.temporary_share import ShareViewLog, TemporaryFileShare, TemporaryShareFile
from apps.docusafe.serializers.temporary_share import (
    CreateTemporaryShareSerializer,
    TemporaryFileShareDetailSerializer,
    TemporaryFileShareSerializer,
    TemporaryShareAccessSerializer,
)
from apps.docusafe.services.share_owner_service import CreateTemporaryShareRequest, DocusafeShareOwnerService
from apps.docusafe.services.share_public_access_service import (
    DocusafeSharePublicAccessService,
    PublicShareAccessRequest,
    PublicShareDownloadRequest,
)
from apps.docusafe.views.base import CustomAPIView
from shared.enums import GlobalAPIMessageCodes
from shared.helpers.request import get_client_ip
from shared.mixins.drf_views import (
    CustomListCreateAPIView,
    CustomRetrieveUpdateDestroyAPIView,
)
from shared.mixins.pagination import CustomPageNumberPagination


class TemporarySharesListCreateView(CustomListCreateAPIView):
    """
    List temporary shares created by the user (GET) or create a new one (POST).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method == "POST":
            return CreateTemporaryShareSerializer
        return TemporaryFileShareSerializer

    def get_queryset(self) -> QuerySet[TemporaryFileShare]:
        return DocusafeShareOwnerService.list_shares(user_id=self.request.user.id)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            share_request = CreateTemporaryShareRequest.from_validated_data(request.user.id, serializer.validated_data)
            share = DocusafeShareOwnerService.create_share(share_request)

            return self.build_response(
                success=True,
                message="Temporary share created successfully.",
                data=TemporaryFileShareDetailSerializer(share).data,
                status=status.HTTP_201_CREATED,
                errorCode=0,
                description="Temporary share created successfully.",
                total=0,
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


class TemporaryShareDetailUpdateDeleteView(CustomRetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific temporary share.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TemporaryFileShareDetailSerializer
    lookup_field = "id"

    def get_queryset(self) -> QuerySet[TemporaryFileShare]:
        return TemporaryFileShare.objects.filter(owner_id=self.request.user.id)

    def get_object(self) -> TemporaryFileShare:
        instance = super().get_object()
        # Pre-attach related data to avoid extra queries in the serializer.
        share_file_ids = list(TemporaryShareFile.objects.filter(share_id=instance.id).values_list("file_id", flat=True))
        instance._prefetched_files = list(DocusafeFile.objects.filter(id__in=share_file_ids))
        instance._prefetched_view_logs = list(ShareViewLog.objects.filter(share_id=instance.id))
        return instance

    def perform_destroy(self, instance: TemporaryFileShare) -> None:
        DocusafeShareOwnerService.delete_share(user_id=self.request.user.id, share_id=instance.id)


class TemporaryShareAccessView(CustomAPIView):
    """
    Public access endpoint for temporary shares.
    Requires password, no authentication needed.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            share_id = self.kwargs.get("id") or self.kwargs.get("share_id")
            serializer = TemporaryShareAccessSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            request_ip = get_client_ip(request)
            user_agent = request.META.get("HTTP_USER_AGENT", "")

            access_request = PublicShareAccessRequest.from_validated_data(
                share_id=share_id,
                request_ip=request_ip,
                user_agent=user_agent,
                validated_data=serializer.validated_data,
            )
            access_data = DocusafeSharePublicAccessService.verify_and_access(access_request)
            return self.build_response(
                success=True,
                message="Access granted.",
                data=access_data.to_response_data(),
                errorCode=0,
                description="Access granted.",
                total=0,
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


class TemporaryShareFileDownloadView(CustomAPIView):
    """
    Public access endpoint for downloading a specific file from a temporary share.
    Requires password, no authentication needed.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            share_id = self.kwargs.get("share_id") or self.kwargs.get("id")
            file_id = self.kwargs.get("file_id")
            serializer = TemporaryShareAccessSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            request_ip = get_client_ip(request)
            user_agent = request.META.get("HTTP_USER_AGENT", "")

            access_request = PublicShareDownloadRequest.from_validated_data(
                share_id=share_id,
                file_id=file_id,
                request_ip=request_ip,
                user_agent=user_agent,
                validated_data=serializer.validated_data,
            )
            response_data = DocusafeSharePublicAccessService.verify_and_download(access_request)
            return self.build_response(
                success=True,
                message="Download access granted.",
                data=response_data.to_response_data(),
                errorCode=0,
                description="Download access granted.",
                total=0,
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

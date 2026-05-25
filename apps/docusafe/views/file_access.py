from typing import Any

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.file_access import DocusafeFileAccess
from apps.docusafe.models.folder import DocusafeFolder
from apps.docusafe.serializers.file import DocusafeFileSerializer
from apps.docusafe.serializers.file_access import (
    DocusafeFileAccessSerializer,
    GrantAccessSerializer,
    RevokeAccessSerializer,
)
from apps.docusafe.serializers.folder import DocusafeFolderSerializer
from apps.docusafe.services.access_service import (
    DocusafeAccessService,
    GrantAccessRequest,
    RevokeAccessRequest,
)
from apps.docusafe.views.base import CustomAPIView
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomListAPIView
from shared.mixins.pagination import CustomPageNumberPagination


class GrantAccessView(CustomAPIView):
    """
    Grant read-only access to files.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            serializer = GrantAccessSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            access_request = GrantAccessRequest.from_validated_data(request.user.id, serializer.validated_data)
            grants = DocusafeAccessService.grant_access(access_request)

            return self.build_response(
                success=True,
                message=f"Access granted successfully for {grants.count} instances.",
                data={"count": grants.count},
                status=status.HTTP_201_CREATED,
                errorCode=0,
                description=f"Access granted successfully for {grants.count} instances.",
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


class RevokeAccessView(CustomAPIView):
    """
    Revoke access to files.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            serializer = RevokeAccessSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            access_request = RevokeAccessRequest.from_validated_data(request.user.id, serializer.validated_data)
            revoke_result = DocusafeAccessService.revoke_access(access_request)

            return self.build_response(
                success=True,
                message=f"Access revoked successfully for {revoke_result.count} instances.",
                data={"count": revoke_result.count},
                errorCode=0,
                description=f"Access revoked successfully for {revoke_result.count} instances.",
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


class FileAccessListView(CustomListAPIView):
    """
    List active access grants for a file.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DocusafeFileAccessSerializer
    pagination_class = CustomPageNumberPagination

    def get_queryset(self) -> QuerySet[DocusafeFileAccess]:
        return DocusafeAccessService.get_file_access_list(
            user_id=self.request.user.id,
            file_id=self.kwargs.get("file_id"),
        )


class SharedWithMeView(CustomListAPIView):
    """
    List folders that contain files shared with the user.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DocusafeFolderSerializer
    pagination_class = CustomPageNumberPagination

    def get_queryset(self) -> QuerySet[DocusafeFolder]:
        return DocusafeAccessService.get_shared_folders(user_id=self.request.user.id)


class SharedFilesInFolderView(CustomListAPIView):
    """
    List shared files in a specific folder.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DocusafeFileSerializer
    pagination_class = CustomPageNumberPagination

    def get_queryset(self) -> QuerySet[DocusafeFile]:
        return DocusafeAccessService.get_shared_files_in_folder(
            user_id=self.request.user.id,
            folder_id=self.kwargs.get("folder_id"),
        )

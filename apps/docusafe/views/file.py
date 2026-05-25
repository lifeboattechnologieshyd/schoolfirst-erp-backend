from typing import Any

import structlog
from django.db.models import QuerySet
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.temporary_share import TemporaryFileShare, TemporaryShareFile
from apps.docusafe.serializers.file import (
    BulkUploadInputSerializer,
    DocusafeFileDetailSerializer,
    DocusafeFileRetrieveSerializer,
    DocusafeFileSerializer,
)
from apps.docusafe.serializers.temporary_share import (
    CreateTemporaryShareSerializer,
    TemporaryFileShareDetailSerializer,
    TemporaryFileShareSerializer,
)
from apps.docusafe.services.file_service import DocusafeFileService
from apps.docusafe.services.share_owner_service import CreateTemporaryShareRequest, DocusafeShareOwnerService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import (
    CustomCreateAPIView,
    CustomListCreateAPIView,
    CustomRetrieveUpdateDestroyAPIView,
)
from shared.mixins.pagination import CustomPageNumberPagination

logger = structlog.getLogger("default")


class FileListUploadView(CustomListCreateAPIView):
    """
    API view for listing and uploading files within a folder.
    POST: Upload file (multipart).
    GET: List files in a folder.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method == "POST":
            return DocusafeFileDetailSerializer
        return DocusafeFileSerializer

    def get_queryset(self) -> QuerySet[DocusafeFile]:
        """
        List files in the folder.
        """
        user_id = self.request.user.id
        folder_id = self.kwargs.get("folder_id")
        return DocusafeFileService.list_files(user_id, folder_id)

    def perform_create(self, serializer: BaseSerializer) -> None:
        """
        Upload file using the service layer.
        """
        user_id = self.request.user.id
        folder_id = self.kwargs.get("folder_id")
        file_obj = self.request.FILES.get("file")

        if not file_obj:
            raise ValidationError({"file": ["No file provided."]})

        description = self.request.data.get("description")

        file_rec = DocusafeFileService.upload_file(
            user_id=user_id,
            folder_id=folder_id,
            file_obj=file_obj,
            description=description,
        )
        serializer.instance = file_rec


class BulkFileUploadView(CustomCreateAPIView):
    """
    API view for bulk uploading files within a folder.
    POST: Upload multiple files (multipart).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    serializer_class = DocusafeFileDetailSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Bulk upload files with partial success support.
        """
        user_id = request.user.id
        folder_id = self.kwargs.get("folder_id")
        files = request.FILES.getlist("files")

        # Fallback: if 'files' is empty, take all files (flexible for tests)
        if not files:
            files = list(request.FILES.values())

        if not files:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": "No files provided for bulk upload.",
                    "details": [{"type": "field", "field": "files", "message": "No files provided."}],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Parse and validate descriptions JSON using Serializer
        input_serializer = BulkUploadInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": "Invalid descriptions format.",
                    "details": self._format_validation_errors(input_serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        descriptions_list = input_serializer.validated_data.get("descriptions", [])

        # 2. Map files to descriptions by filename
        desc_map = {
            item.get("file_name"): item.get("description") for item in descriptions_list if isinstance(item, dict)
        }

        mapped_descriptions = []
        for file in files:
            desc = desc_map.get(file.name)
            if desc is None:
                return self.build_response(
                    success=False,
                    error={
                        "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                        "message": f"Description for file '{file.name}' is missing in JSON mapping.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            mapped_descriptions.append(desc)

        # 3. Perform bulk upload (partial success supported)
        created_files, failed_files = DocusafeFileService.upload_files_bulk(
            user_id=user_id,
            folder_id=folder_id,
            file_objs=files,
            descriptions=mapped_descriptions,
        )

        response_status = status.HTTP_201_CREATED if created_files else status.HTTP_400_BAD_REQUEST
        success = len(created_files) > 0

        return self.build_response(
            success=success,
            data={
                "success_files": DocusafeFileDetailSerializer(created_files, many=True).data,
                "failed_files": failed_files,
            },
            message=f"Successfully uploaded {len(created_files)} files. Failed: {len(failed_files)} files.",
            status=response_status,
        )


class FileDetailUpdateDeleteView(CustomRetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, and deleting a specific file.
    GET: File metadata.
    PATCH: Update file metadata.
    DELETE: Hard-delete file (S3 + DB).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DocusafeFileDetailSerializer
    lookup_url_kwarg = "file_id"

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method == "GET":
            return DocusafeFileRetrieveSerializer
        return DocusafeFileDetailSerializer

    def get_object(self) -> DocusafeFile:
        """
        Retrieve file using the service layer.
        """
        user_id = self.request.user.id
        folder_id = self.kwargs.get("folder_id")
        file_id = self.kwargs.get(self.lookup_url_kwarg)
        return DocusafeFileService.get_file(user_id, folder_id, file_id)

    def perform_update(self, serializer: BaseSerializer) -> None:
        """
        Update file using the service layer.
        """
        user_id = self.request.user.id
        folder_id = self.kwargs.get("folder_id")
        file_id = serializer.instance.id
        data = serializer.validated_data

        file_rec = DocusafeFileService.update_file(user_id=user_id, folder_id=folder_id, file_id=file_id, **data)
        serializer.instance = file_rec

    def perform_destroy(self, instance: DocusafeFile) -> None:
        """
        Delete file using the service layer.
        """
        user_id = self.request.user.id
        folder_id = self.kwargs.get("folder_id")
        DocusafeFileService.delete_file(user_id, folder_id, instance.id)


class FileSharesListView(CustomListCreateAPIView):
    """
    API view for listing temporary shares containing a specific file.
    Also allows creating a new share directly for this file (POST).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method == "POST":
            return CreateTemporaryShareSerializer
        return TemporaryFileShareSerializer

    def get_queryset(self) -> QuerySet[TemporaryFileShare]:
        """
        List active temporary shares for this file owned by the user.
        """

        user_id = self.request.user.id
        file_id = self.kwargs.get("file_id")

        # Verify file belongs to the user via service
        # If it raises 404/403, it won't proceed
        DocusafeFileService.get_file(user_id, self.kwargs.get("folder_id"), file_id)

        share_ids = TemporaryShareFile.objects.filter(file_id=file_id).values_list("share_id", flat=True)
        return TemporaryFileShare.objects.filter(id__in=share_ids, owner_id=user_id).only(
            "id", "title", "status", "expires_at", "view_count", "file_count", "created_at"
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Overridden to automatically inject file_id if not present in payload.
        """

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            data = serializer.validated_data
            file_ids = data.get("file_ids", [])
            file_id = self.kwargs.get("file_id")

            if file_id not in file_ids:
                file_ids.append(file_id)

            data["file_ids"] = file_ids

            share_request = CreateTemporaryShareRequest.from_validated_data(request.user.id, data)
            share = DocusafeShareOwnerService.create_share(share_request)

            return self.build_response(
                success=True,
                message="Temporary share created successfully for this file.",
                data=TemporaryFileShareDetailSerializer(share).data,
                status=status.HTTP_201_CREATED,
                errorCode=0,
                description="Temporary share created successfully for this file.",
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

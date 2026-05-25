from django.db.models import QuerySet
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import BaseSerializer

from apps.docusafe.models.folder import DocusafeFolder
from apps.docusafe.serializers.folder import (
    DocusafeFolderDetailSerializer,
    DocusafeFolderSerializer,
)
from apps.docusafe.services.folder_service import DocusafeFolderService
from shared.mixins.drf_views import CustomListCreateAPIView, CustomRetrieveUpdateDestroyAPIView
from shared.mixins.pagination import CustomPageNumberPagination


class FolderListCreateView(CustomListCreateAPIView):
    """
    API view for listing and creating folders.
    GET: List user's folders (My Safe).
    POST: Create a new folder.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method == "POST":
            return DocusafeFolderDetailSerializer
        return DocusafeFolderSerializer

    def get_queryset(self) -> QuerySet[DocusafeFolder]:
        """
        List user's folders.
        """
        user_id = self.request.user.id
        return DocusafeFolderService.list_folders(user_id)

    def perform_create(self, serializer: BaseSerializer) -> None:
        """
        Create a new folder using the service layer.
        """
        user_id = self.request.user.id
        name = serializer.validated_data.get("name")
        description = serializer.validated_data.get("description")

        # Delegate creation to the service layer
        folder = DocusafeFolderService.create_folder(
            user_id=user_id,
            name=name,
            description=description,
        )

        # Update serializer instance manually to skip the
        # default DRF perform_create logic
        serializer.instance = folder


class FolderDetailUpdateDeleteView(CustomRetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, and deleting a specific folder.
    GET: Retrieve details of a folder.
    PATCH: Update folder details.
    DELETE: Hard-delete a folder and its contents.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DocusafeFolderDetailSerializer
    lookup_url_kwarg = "folder_id"

    def get_object(self) -> DocusafeFolder:
        """
        Retrieve folder using the service layer with ownership check.
        """
        user_id = self.request.user.id
        folder_id = self.kwargs.get(self.lookup_url_kwarg)
        return DocusafeFolderService.get_folder(user_id, folder_id)

    def perform_update(self, serializer: BaseSerializer) -> None:
        """
        Update folder using the service layer.
        """
        user_id = self.request.user.id
        folder_id = serializer.instance.id
        data = serializer.validated_data

        # Delegate update to the service layer
        folder = DocusafeFolderService.update_folder(user_id=user_id, folder_id=folder_id, **data)

        # Update serializer instance manually
        serializer.instance = folder

    def perform_destroy(self, instance: DocusafeFolder) -> None:
        """
        Delete folder using the service layer.
        """
        user_id = self.request.user.id
        DocusafeFolderService.delete_folder(user_id, instance.id)

from django.urls import path

from apps.docusafe.views.file import (
    BulkFileUploadView,
    FileDetailUpdateDeleteView,
    FileListUploadView,
    FileSharesListView,
)
from apps.docusafe.views.file_access import (
    FileAccessListView,
    GrantAccessView,
    RevokeAccessView,
    SharedFilesInFolderView,
    SharedWithMeView,
)
from apps.docusafe.views.folder import FolderDetailUpdateDeleteView, FolderListCreateView
from apps.docusafe.views.search import DocusafeSearchView
from apps.docusafe.views.temporary_share import (
    TemporaryShareAccessView,
    TemporaryShareDetailUpdateDeleteView,
    TemporaryShareFileDownloadView,
    TemporarySharesListCreateView,
)

urlpatterns = [
    # Folder APIs
    path("v1/docusafe/folders", FolderListCreateView.as_view(), name="folder-list-create"),
    path(
        "v1/docusafe/folders/<uuid:folder_id>",
        FolderDetailUpdateDeleteView.as_view(),
        name="folder-detail-update-delete",
    ),
    # File APIs (Nested)
    path(
        "v1/docusafe/folders/<uuid:folder_id>/files",
        FileListUploadView.as_view(),
        name="file-list-upload",
    ),
    path(
        "v1/docusafe/folders/<uuid:folder_id>/files/bulk",
        BulkFileUploadView.as_view(),
        name="file-bulk-upload",
    ),
    path(
        "v1/docusafe/folders/<uuid:folder_id>/files/<uuid:file_id>",
        FileDetailUpdateDeleteView.as_view(),
        name="file-detail-update-delete",
    ),
    path(
        "v1/docusafe/folders/<uuid:folder_id>/files/<uuid:file_id>/shares",
        FileSharesListView.as_view(),
        name="file-shares-list",
    ),
    # File Sharing APIs
    path("v1/docusafe/access/grant", GrantAccessView.as_view(), name="access-grant"),
    path("v1/docusafe/access/revoke", RevokeAccessView.as_view(), name="access-revoke"),
    path(
        "v1/docusafe/access/file/<uuid:file_id>",
        FileAccessListView.as_view(),
        name="file-access-list",
    ),
    # Shared With Me APIs
    path("v1/docusafe/shared-with-me", SharedWithMeView.as_view(), name="shared-with-me"),
    path(
        "v1/docusafe/shared-with-me/folders/<uuid:folder_id>/files",
        SharedFilesInFolderView.as_view(),
        name="shared-files-in-folder",
    ),
    # Temporary Share APIs
    path(
        "v1/docusafe/shares",
        TemporarySharesListCreateView.as_view(),
        name="temporary-share-list-create",
    ),
    path(
        "v1/docusafe/shares/<uuid:id>",
        TemporaryShareDetailUpdateDeleteView.as_view(),
        name="temporary-share-detail",
    ),
    # Public Access (No Auth)
    path(
        "v1/docusafe/shares/access/<uuid:share_id>",
        TemporaryShareAccessView.as_view(),
        name="temporary-share-access",
    ),
    path(
        "v1/docusafe/shares/access/<uuid:share_id>/files/<uuid:file_id>/download",
        TemporaryShareFileDownloadView.as_view(),
        name="temporary-share-file-download",
    ),
    # Search API
    path("v1/docusafe/search", DocusafeSearchView.as_view(), name="docusafe-search"),
]

from typing import Any

import structlog
from django.db import transaction
from django.utils import timezone

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.folder import DocusafeFolder
from apps.docusafe.models.temporary_share import TemporaryFileShare, TemporaryShareFile
from shared.enums import TemporaryShareStatus

logger = structlog.getLogger("default")


class DocusafeShareProjectionService:
    """
    Maintain temporary-share derived state and cleanup after share-file changes.
    """

    @staticmethod
    def sync_shared_state(file_ids: list[Any]) -> None:
        if not file_ids:
            return

        normalized_file_ids = [str(file_id) for file_id in file_ids]

        now = timezone.now()
        active_share_ids = TemporaryFileShare.objects.filter(
            status=TemporaryShareStatus.ACTIVE,
            expires_at__gt=now,
        ).values_list("id", flat=True)

        shared_file_ids = set(
            TemporaryShareFile.objects.filter(
                file_id__in=normalized_file_ids,
                share_id__in=active_share_ids,
            ).values_list("file_id", flat=True)
        )
        normalized_shared_file_ids = {str(file_id) for file_id in shared_file_ids}

        DocusafeFile.objects.filter(id__in=normalized_shared_file_ids).update(is_shared=True)

        unshared_file_ids = set(normalized_file_ids) - normalized_shared_file_ids
        if unshared_file_ids:
            DocusafeFile.objects.filter(id__in=unshared_file_ids).update(is_shared=False)

        folder_ids = list(
            DocusafeFile.objects.filter(id__in=normalized_file_ids).values_list("folder_id", flat=True).distinct()
        )
        if not folder_ids:
            return

        shared_folder_ids = set(
            DocusafeFile.objects.filter(folder_id__in=folder_ids, is_shared=True)
            .values_list("folder_id", flat=True)
            .distinct()
        )
        unshared_folder_ids = set(folder_ids) - shared_folder_ids

        if shared_folder_ids:
            DocusafeFolder.objects.filter(id__in=shared_folder_ids).update(is_shared=True)
        if unshared_folder_ids:
            DocusafeFolder.objects.filter(id__in=unshared_folder_ids).update(is_shared=False)

    @staticmethod
    @transaction.atomic
    def remove_files(file_ids: list[Any]) -> None:
        if not file_ids:
            return

        share_ids = list(
            TemporaryShareFile.objects.filter(file_id__in=file_ids).values_list("share_id", flat=True).distinct()
        )
        if not share_ids:
            DocusafeShareProjectionService.sync_shared_state(file_ids)
            return

        TemporaryShareFile.objects.filter(file_id__in=file_ids).delete()
        DocusafeShareProjectionService._sync_share_counts(share_ids)
        DocusafeShareProjectionService.sync_shared_state(file_ids)

    @staticmethod
    def _sync_share_counts(share_ids: list[Any]) -> None:
        for share in TemporaryFileShare.objects.filter(id__in=share_ids):
            remaining_count = TemporaryShareFile.objects.filter(share_id=share.id).count()
            if remaining_count == 0:
                share.delete()
                logger.info("Deleted empty temporary share after file removal", share_id=share.id)
                continue

            share.file_count = remaining_count
            share.save(update_fields=["file_count"])
            logger.info("Synchronized temporary share after file removal", share_id=share.id)

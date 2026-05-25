from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.temporary_share import (
    ShareViewLog,
    TemporaryFileShare,
    TemporaryShareFile,
)
from apps.docusafe.services.folder_scope_service import DocusafeFolderScopeService
from apps.docusafe.services.share_projection_service import (
    DocusafeShareProjectionService,
)
from shared.enums import TemporaryShareStatus

logger = structlog.getLogger("default")


@dataclass(frozen=True)
class CreateTemporaryShareRequest:
    user_id: str
    file_ids: tuple[str, ...]
    password: str
    expires_at: datetime
    title: str | None = None
    max_views: int | None = None
    max_failed_attempts: int = 5
    recipient_emails: tuple[str, ...] = ()

    @classmethod
    def from_validated_data(cls, user_id: Any, validated_data: dict) -> CreateTemporaryShareRequest:
        return cls(
            user_id=str(user_id),
            file_ids=tuple(str(file_id) for file_id in validated_data["file_ids"]),
            password=validated_data["password"],
            expires_at=validated_data["expires_at"],
            title=validated_data.get("title"),
            max_views=validated_data.get("max_views"),
            max_failed_attempts=validated_data.get("max_failed_attempts", 5),
            recipient_emails=tuple(validated_data.get("recipient_emails") or []),
        )


class DocusafeShareOwnerService:
    """
    Owner-side lifecycle for temporary shares.
    """

    @staticmethod
    def list_shares(user_id: Any) -> QuerySet[TemporaryFileShare]:
        return TemporaryFileShare.objects.filter(owner_id=user_id).only(
            "id",
            "title",
            "status",
            "expires_at",
            "view_count",
            "file_count",
            "created_at",
        )

    @staticmethod
    @transaction.atomic
    def create_share(request: CreateTemporaryShareRequest) -> TemporaryFileShare:
        DocusafeShareOwnerService._get_owned_files(request.user_id, list(request.file_ids))

        share = TemporaryFileShare.objects.create(
            title=request.title,
            password_hash=make_password(request.password),
            expires_at=request.expires_at,
            max_views=request.max_views,
            max_failed_attempts=request.max_failed_attempts,
            owner_id=request.user_id,
            recipient_emails=list(request.recipient_emails),
            file_count=len(request.file_ids),
        )

        TemporaryShareFile.objects.bulk_create(
            [TemporaryShareFile(share_id=share.id, file_id=file_id) for file_id in request.file_ids]
        )

        DocusafeShareProjectionService.sync_shared_state(list(request.file_ids))

        if request.recipient_emails:
            DocusafeShareOwnerService._send_share_emails(share)

        return share

    @staticmethod
    @transaction.atomic
    def update_share(user_id: Any, share_id: Any, **data: Any) -> TemporaryFileShare:
        share = TemporaryFileShare.objects.filter(id=share_id, owner_id=user_id).first()
        if not share:
            raise ValidationError("Share not found or you do not have permission.")

        file_ids = data.pop("file_ids", None)
        password = data.pop("password", None)
        projection_fields = {"status", "expires_at"}
        should_sync_projection = file_ids is not None or bool(projection_fields & data.keys())

        if password:
            share.password_hash = make_password(password)

        for attr, value in data.items():
            setattr(share, attr, value)

        affected_file_ids = []
        if file_ids is not None:
            DocusafeShareOwnerService._get_owned_files(user_id, file_ids)

            old_file_ids = list(
                TemporaryShareFile.objects.filter(share_id=share.id).values_list(
                    "file_id",
                    flat=True,
                )
            )
            affected_file_ids = list({*old_file_ids, *file_ids})

            TemporaryShareFile.objects.filter(share_id=share.id).delete()
            if file_ids:
                TemporaryShareFile.objects.bulk_create(
                    [TemporaryShareFile(share_id=share.id, file_id=file_id) for file_id in file_ids]
                )

            share.file_count = len(file_ids)
            if share.file_count == 0:
                share.delete()
                DocusafeShareProjectionService.sync_shared_state(affected_file_ids)
                logger.info(
                    "Deleted empty temporary share during update",
                    share_id=share_id,
                )
                share._empty_deleted = True
                return share

        if not affected_file_ids and should_sync_projection:
            affected_file_ids = list(
                TemporaryShareFile.objects.filter(share_id=share.id).values_list(
                    "file_id",
                    flat=True,
                )
            )

        share.save()

        if affected_file_ids and should_sync_projection:
            DocusafeShareProjectionService.sync_shared_state(affected_file_ids)

        logger.info("Updated temporary share", share_id=share_id)
        return share

    @staticmethod
    @transaction.atomic
    def delete_share(user_id: Any, share_id: Any) -> None:
        share = TemporaryFileShare.objects.filter(id=share_id, owner_id=user_id).first()
        if not share:
            raise ValidationError("Share not found or you do not have permission.")

        file_ids = list(
            TemporaryShareFile.objects.filter(share_id=share_id).values_list(
                "file_id",
                flat=True,
            )
        )

        TemporaryShareFile.objects.filter(share_id=share_id).delete()
        ShareViewLog.objects.filter(share_id=share_id).delete()
        share.delete()

        DocusafeShareProjectionService.sync_shared_state(file_ids)

    @staticmethod
    @transaction.atomic
    def process_expired_shares() -> int:
        now = timezone.now()
        expired_shares = TemporaryFileShare.objects.filter(
            status=TemporaryShareStatus.ACTIVE,
            expires_at__lt=now,
        )

        count = expired_shares.count()
        if count == 0:
            return 0

        affected_file_ids = list(
            TemporaryShareFile.objects.filter(share_id__in=expired_shares.values_list("id", flat=True))
            .values_list("file_id", flat=True)
            .distinct()
        )

        expired_shares.update(status=TemporaryShareStatus.EXPIRED)
        DocusafeShareProjectionService.sync_shared_state(affected_file_ids)

        logger.info("Automatically expired temporary shares", count=count)
        return count

    @staticmethod
    def _get_owned_files(user_id: Any, file_ids: list[Any]) -> QuerySet[DocusafeFile]:
        return DocusafeFolderScopeService.get_owned_files(user_id, file_ids, folder_status=None)

    @staticmethod
    def _send_share_emails(share: TemporaryFileShare) -> None:
        for email in share.recipient_emails:
            logger.info(
                "Email notification triggered for temporary share",
                share_id=share.id,
                recipient_email=email,
            )

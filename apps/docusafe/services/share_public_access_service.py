from dataclasses import dataclass
from typing import Any

from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.models.user import UserMaster
from apps.docusafe.constants import PRESIGNED_URL_EXPIRY_SECONDS
from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.temporary_share import (
    ShareViewLog,
    TemporaryFileShare,
    TemporaryShareFile,
)
from apps.docusafe.services.file_storage_service import DocusafeFileStorageService
from apps.docusafe.services.share_projection_service import (
    DocusafeShareProjectionService,
)
from shared.enums import DocusafeStatus, TemporaryShareStatus


@dataclass(frozen=True)
class PublicShareAccessRequest:
    share_id: str
    password: str
    request_ip: str | None
    user_agent: str
    client_metadata: dict[str, object]

    @classmethod
    def from_validated_data(
        cls,
        share_id,
        request_ip: str | None,
        user_agent: str,
        validated_data: dict,
    ) -> PublicShareAccessRequest:
        return cls(
            share_id=str(share_id),
            password=validated_data["password"],
            request_ip=request_ip,
            user_agent=user_agent,
            client_metadata=dict(validated_data.get("client_metadata") or {}),
        )


@dataclass(frozen=True)
class PublicShareDownloadRequest:
    share_id: str
    file_id: str
    password: str
    request_ip: str | None
    user_agent: str
    client_metadata: dict[str, object]

    @classmethod
    def from_validated_data(
        cls,
        share_id,
        file_id,
        request_ip: str | None,
        user_agent: str,
        validated_data: dict,
    ) -> PublicShareDownloadRequest:
        return cls(
            share_id=str(share_id),
            file_id=str(file_id),
            password=validated_data["password"],
            request_ip=request_ip,
            user_agent=user_agent,
            client_metadata=dict(validated_data.get("client_metadata") or {}),
        )


@dataclass(frozen=True)
class SharedFileAccessResult:
    file_id: str
    file_name: str
    file_size: int
    mime_type: str | None

    def to_response_data(self) -> dict[str, object]:
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
        }


@dataclass(frozen=True)
class ShareAccessResult:
    files: tuple[SharedFileAccessResult, ...]
    title: str | None
    expires_at: str | None
    shared_by: str

    def to_response_data(self) -> dict[str, object]:
        return {
            "files": [file.to_response_data() for file in self.files],
            "total_files": len(self.files),
            "title": self.title,
            "expires_at": self.expires_at,
            "shared_by": self.shared_by,
        }


@dataclass(frozen=True)
class ShareDownloadResult:
    download_url: str
    expires_in_seconds: int

    def to_response_data(self) -> dict[str, object]:
        return {
            "download_url": self.download_url,
            "expires_in_seconds": self.expires_in_seconds,
        }


@dataclass(frozen=True)
class ShareValidationState:
    share: TemporaryFileShare
    failure_reason: str | None
    error_message: str | None


class DocusafeSharePublicAccessService:
    """
    Public access verification, download access, and view logging.
    """

    @staticmethod
    def verify_and_access(request: PublicShareAccessRequest) -> ShareAccessResult:
        client_metadata = DocusafeSharePublicAccessService._normalize_client_metadata(request.client_metadata)
        validation = DocusafeSharePublicAccessService._validate_share_access(
            share_id=request.share_id,
            password=request.password,
            increment_view_count=True,
        )

        if validation.error_message:
            DocusafeSharePublicAccessService._log_view(
                request.share_id,
                False,
                validation.failure_reason,
                request.request_ip,
                request.user_agent,
                client_metadata,
            )
            raise ValidationError(validation.error_message)

        DocusafeSharePublicAccessService._log_view(
            request.share_id,
            True,
            None,
            request.request_ip,
            request.user_agent,
            client_metadata,
        )

        file_ids = TemporaryShareFile.objects.filter(share_id=request.share_id).values_list(
            "file_id",
            flat=True,
        )
        files = DocusafeFile.objects.filter(id__in=file_ids, status=DocusafeStatus.ACTIVE)

        owner = UserMaster.objects.filter(id=validation.share.owner_id).first()
        shared_by = f"{owner.first_name or ''} {owner.last_name or ''}".strip() if owner else "Unknown User"

        return ShareAccessResult(
            files=tuple(
                SharedFileAccessResult(
                    file_id=str(file.id),
                    file_name=file.file_name,
                    file_size=file.file_size,
                    mime_type=file.mime_type,
                )
                for file in files
            ),
            title=validation.share.title,
            expires_at=validation.share.expires_at.isoformat() if validation.share.expires_at else None,
            shared_by=shared_by,
        )

    @staticmethod
    def verify_and_download(
        request: PublicShareDownloadRequest,
    ) -> ShareDownloadResult:
        client_metadata = DocusafeSharePublicAccessService._normalize_client_metadata(request.client_metadata)
        validation = DocusafeSharePublicAccessService._validate_share_access(
            share_id=request.share_id,
            password=request.password,
            increment_view_count=False,
        )

        if validation.error_message:
            DocusafeSharePublicAccessService._log_view(
                request.share_id,
                False,
                validation.failure_reason,
                request.request_ip,
                request.user_agent,
                client_metadata,
            )
            raise ValidationError(validation.error_message)

        if not TemporaryShareFile.objects.filter(share_id=request.share_id, file_id=request.file_id).exists():
            raise ValidationError("File not found in this share.")

        file = DocusafeFile.objects.filter(id=request.file_id, status=DocusafeStatus.ACTIVE).first()
        if not file:
            raise ValidationError("File not found.")

        download_metadata = dict(client_metadata)
        download_metadata["action"] = "download"
        download_metadata["file_id"] = str(request.file_id)

        DocusafeSharePublicAccessService._log_view(
            request.share_id,
            True,
            None,
            request.request_ip,
            request.user_agent,
            download_metadata,
        )

        return ShareDownloadResult(
            download_url=DocusafeFileStorageService.get_presigned_url(file.file_path),
            expires_in_seconds=PRESIGNED_URL_EXPIRY_SECONDS,
        )

    @staticmethod
    def _log_view(
        share_id: Any,
        success: bool,
        reason: str | None,
        request_ip: str | None,
        user_agent: str,
        client_metadata: dict[str, object],
    ) -> None:
        ShareViewLog.objects.create(
            share_id=share_id,
            success=success,
            failure_reason=reason,
            ip_address=request_ip or "unknown",
            user_agent=user_agent or "",
            client_metadata=DocusafeSharePublicAccessService._normalize_client_metadata(client_metadata),
        )

    @staticmethod
    def _normalize_client_metadata(client_metadata: object) -> dict[str, object]:
        if not isinstance(client_metadata, dict):
            return {}
        return dict(client_metadata)

    @staticmethod
    def _validate_share_access(share_id: Any, password: str, increment_view_count: bool) -> ShareValidationState:
        with transaction.atomic():
            share = TemporaryFileShare.objects.select_for_update().filter(id=share_id).first()
            if not share:
                raise ValidationError("Share not found.")

            if share.status != TemporaryShareStatus.ACTIVE:
                return ShareValidationState(
                    share=share,
                    failure_reason=share.status,
                    error_message=f"This share is {share.status.lower()}.",
                )

            if share.expires_at < timezone.now():
                share.status = TemporaryShareStatus.EXPIRED
                share.save(update_fields=["status"])
                DocusafeSharePublicAccessService._sync_projection_for_share(share.id)
                return ShareValidationState(
                    share=share,
                    failure_reason=TemporaryShareStatus.EXPIRED,
                    error_message="This share has expired.",
                )

            if share.max_views and share.view_count >= share.max_views:
                return ShareValidationState(
                    share=share,
                    failure_reason="MAX_VIEWS_REACHED",
                    error_message="Max view limit reached for this share.",
                )

            if not check_password(password, share.password_hash):
                share.failed_attempts += 1
                update_fields = ["failed_attempts"]
                if share.failed_attempts >= share.max_failed_attempts:
                    share.status = TemporaryShareStatus.BLOCKED
                    update_fields.append("status")
                share.save(update_fields=update_fields)

                if share.status == TemporaryShareStatus.BLOCKED:
                    DocusafeSharePublicAccessService._sync_projection_for_share(share.id)
                    return ShareValidationState(
                        share=share,
                        failure_reason="INVALID_PASSWORD",
                        error_message="This share has been blocked due to too many failed attempts.",
                    )

                remaining = share.max_failed_attempts - share.failed_attempts
                return ShareValidationState(
                    share=share,
                    failure_reason="INVALID_PASSWORD",
                    error_message=f"Invalid password. {remaining} attempts remaining.",
                )

            update_fields = []
            if increment_view_count:
                share.view_count += 1
                update_fields.append("view_count")

            if share.failed_attempts > 0:
                share.failed_attempts = 0
                update_fields.append("failed_attempts")

            if update_fields:
                share.save(update_fields=update_fields)

            return ShareValidationState(share=share, failure_reason=None, error_message=None)

    @staticmethod
    def _sync_projection_for_share(share_id: Any) -> None:
        file_ids = list(
            TemporaryShareFile.objects.filter(share_id=share_id).values_list(
                "file_id",
                flat=True,
            )
        )
        DocusafeShareProjectionService.sync_shared_state(file_ids)

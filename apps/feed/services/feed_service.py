import posixpath
import uuid
from typing import Any

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F, QuerySet
from django.db.models.functions import Greatest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.models import UserMaster
from apps.core.services.social_graph_service import SocialGraphService
from apps.feed.enums import ReactionType
from apps.feed.models.feed import Feed, FeedComment, FeedReaction, FeedSave, FeedShare
from apps.feed.serializers.presentation import normalize_storage_path
from apps.feed.services.access_policy import (
    FeedAccessPolicy,
    validate_access_configuration,
    validate_access_ids_ownership,
    validate_access_user_ids,
)
from apps.feed.validators import validate_feed_content
from shared.utils.files import delete_file, move_file


def _validation_error_from_dict(errors: dict) -> ValidationError:
    return ValidationError(errors)


class FeedService:
    @staticmethod
    def get_feed_queryset(user: UserMaster, creator_id: Any | None = None) -> QuerySet[Feed]:
        scope = SocialGraphService.build_visibility_scope(user)
        access_filter = FeedAccessPolicy.build_filter(user.id, scope)

        queryset = (
            Feed.objects.filter(is_deleted=False)
            .filter(access_filter)
            .select_related("creator")
        )
        if creator_id is not None:
            queryset = queryset.filter(creator_id=creator_id)

        return queryset.order_by("-created_at")

    @staticmethod
    def get_visible_feed(feed_id: Any, user: UserMaster) -> Feed:
        """Retrieve a feed post ensuring the user has visibility access."""
        scope = SocialGraphService.build_visibility_scope(user)
        access_filter = FeedAccessPolicy.build_filter(user.id, scope)

        feed = (
            Feed.objects.filter(id=feed_id, is_deleted=False)
            .filter(access_filter)
            .distinct()
            .first()
        )
        if not feed:
            raise PermissionDenied("Feed not accessible")
        return feed

    @staticmethod
    def _validate_media_path(
        user_id_str: str,
        feed_id_str: str,
        path: str,
        old_media_urls: list[str],
    ) -> str:
        if not isinstance(path, str):
            raise ValidationError("Media URL must be a string path.")

        normalized = posixpath.normpath(normalize_storage_path(path))
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValidationError("Invalid file path.")

        old_media_keys = {posixpath.normpath(normalize_storage_path(item)) for item in old_media_urls}

        if normalized.startswith(f"feeds/{feed_id_str}/"):
            if normalized not in old_media_keys:
                raise ValidationError(f"Unauthorized path: {path}")
        elif normalized.startswith(f"temp/{user_id_str}/"):
            if not default_storage.exists(normalized):
                raise ValidationError(f"File does not exist: {path}")
        else:
            raise ValidationError(f"Invalid path location: {path}")

        return normalized

    @staticmethod
    def _process_feed_media(
        user: UserMaster,
        feed_id: Any,
        new_media_urls: list[str],
        old_media_urls: list[str] | None = None,
    ) -> list[str]:
        old_media_urls = old_media_urls or []
        user_id_str = str(user.id)
        feed_id_str = str(feed_id)

        unique_new_urls: list[str] = []
        for url in new_media_urls:
            if url not in unique_new_urls:
                unique_new_urls.append(url)

        for path in unique_new_urls:
            FeedService._validate_media_path(
                user_id_str=user_id_str,
                feed_id_str=feed_id_str,
                path=path,
                old_media_urls=old_media_urls,
            )

        final_media_urls: list[str] = []
        for path in unique_new_urls:
            normalized = posixpath.normpath(normalize_storage_path(path))
            if normalized.startswith(f"temp/{user_id_str}/"):
                dest_folder = f"feeds/{feed_id_str}"
                moved_path = move_file(normalized, dest_folder)
                if not moved_path:
                    raise ValidationError(f"Failed to move file: {path}")
                final_media_urls.append(moved_path)
            else:
                final_media_urls.append(normalized)

        final_media_keys = {posixpath.normpath(normalize_storage_path(item)) for item in final_media_urls}
        for path in old_media_urls:
            if posixpath.normpath(normalize_storage_path(path)) not in final_media_keys:
                delete_file(posixpath.normpath(normalize_storage_path(path)))

        return final_media_urls

    @staticmethod
    def _validate_access_control(
        user: UserMaster,
        access_type: str,
        access_family_ids: list[str],
        access_close_group_ids: list[str],
        access_user_ids: list[str],
    ) -> None:
        config_error = validate_access_configuration(
            access_type=access_type,
            access_family_ids=access_family_ids,
            access_close_group_ids=access_close_group_ids,
            access_user_ids=access_user_ids,
        )
        if config_error:
            raise _validation_error_from_dict(config_error)

        creator_family_ids = SocialGraphService.get_user_family_ids(user)
        creator_close_group_ids = set(SocialGraphService.get_close_group_membership_ids(user)) | set(
            SocialGraphService.get_owned_close_group_ids(user)
        )

        ownership_error = validate_access_ids_ownership(
            access_family_ids=access_family_ids,
            access_close_group_ids=access_close_group_ids,
            creator_family_ids=creator_family_ids,
            creator_close_group_ids=creator_close_group_ids,
        )
        if ownership_error:
            raise _validation_error_from_dict(ownership_error)

        user_ids_error = validate_access_user_ids(
            access_user_ids=access_user_ids,
            allowed_user_ids=set(SocialGraphService.get_access_user_id_candidates(user)),
        )
        if user_ids_error:
            raise _validation_error_from_dict(user_ids_error)

    @staticmethod
    def _validate_content(
        text: str | None,
        media_urls: list[str] | None,
        youtube_url: str | None,
        external_urls: list[str] | None = None,
    ) -> None:
        error = validate_feed_content(
            body_text=text,
            media_urls=media_urls,
            youtube_url=youtube_url,
            external_urls=external_urls,
        )
        if error:
            raise ValidationError(error)

    @staticmethod
    @transaction.atomic
    def create_feed(  # noqa: PLR0913
        user: UserMaster,
        text: str | None = None,
        media_urls: list[str] | None = None,
        youtube_url: str | None = None,
        external_urls: list[str] | None = None,
        access_type: str = "only_me",
        access_family_ids: list[str] | None = None,
        access_close_group_ids: list[str] | None = None,
        access_user_ids: list[str] | None = None,
    ) -> Feed:
        media_urls = media_urls or []
        FeedService._validate_content(text, media_urls, youtube_url, external_urls)

        access_family_ids = access_family_ids or []
        access_close_group_ids = access_close_group_ids or []
        access_user_ids = access_user_ids or []

        FeedService._validate_access_control(
            user=user,
            access_type=access_type,
            access_family_ids=access_family_ids,
            access_close_group_ids=access_close_group_ids,
            access_user_ids=access_user_ids,
        )

        feed_id = uuid.uuid4()
        final_media_urls = FeedService._process_feed_media(user, feed_id, media_urls)

        return Feed.objects.create(
            id=feed_id,
            creator=user,
            text=text,
            media_urls=final_media_urls,
            youtube_url=youtube_url,
            external_urls=external_urls,
            access_type=access_type,
            access_family_ids=access_family_ids,
            access_close_group_ids=access_close_group_ids,
            access_user_ids=access_user_ids,
        )

    @staticmethod
    @transaction.atomic
    def update_feed(  # noqa: PLR0913
        user: UserMaster,
        feed_id: Any,
        text: str | None = None,
        media_urls: list[str] | None = None,
        youtube_url: str | None = None,
        external_urls: list[str] | None = None,
        access_type: str | None = None,
        access_family_ids: list[str] | None = None,
        access_close_group_ids: list[str] | None = None,
        access_user_ids: list[str] | None = None,
        text_provided: bool = False,
        media_urls_provided: bool = False,
        youtube_url_provided: bool = False,
        external_urls_provided: bool = False,
    ) -> Feed:
        feed = Feed.objects.filter(id=feed_id, is_deleted=False).first()
        if not feed:
            raise ValidationError({"detail": "Feed not found"})
        if feed.creator_id != user.id:
            raise PermissionDenied("Only the creator can edit this post")

        updated_text = text if text_provided else feed.text
        updated_media_urls = media_urls if media_urls_provided else feed.media_urls
        updated_youtube_url = youtube_url if youtube_url_provided else feed.youtube_url
        updated_external_urls = external_urls if external_urls_provided else feed.external_urls

        FeedService._validate_content(
            updated_text,
            updated_media_urls,
            updated_youtube_url,
            updated_external_urls,
        )

        target_access_type = access_type if access_type is not None else feed.access_type
        target_family_ids = access_family_ids if access_family_ids is not None else feed.access_family_ids
        target_close_group_ids = (
            access_close_group_ids if access_close_group_ids is not None else feed.access_close_group_ids
        )
        target_user_ids = access_user_ids if access_user_ids is not None else feed.access_user_ids

        FeedService._validate_access_control(
            user=user,
            access_type=target_access_type,
            access_family_ids=target_family_ids or [],
            access_close_group_ids=target_close_group_ids or [],
            access_user_ids=target_user_ids or [],
        )

        feed.access_type = target_access_type
        feed.access_family_ids = target_family_ids
        feed.access_close_group_ids = target_close_group_ids
        feed.access_user_ids = target_user_ids

        if media_urls_provided:
            feed.media_urls = FeedService._process_feed_media(
                user=user,
                feed_id=feed.id,
                new_media_urls=updated_media_urls if updated_media_urls is not None else [],
                old_media_urls=feed.media_urls if feed.media_urls is not None else [],
            )

        if text_provided:
            feed.text = updated_text
        if youtube_url_provided:
            feed.youtube_url = updated_youtube_url
        if external_urls_provided:
            feed.external_urls = updated_external_urls

        feed.save()
        return feed

    @staticmethod
    @transaction.atomic
    def delete_feed(user: UserMaster, feed_id: Any) -> bool:
        feed = Feed.objects.filter(id=feed_id, is_deleted=False).first()
        if not feed:
            raise ValidationError({"detail": "Feed not found"})
        if feed.creator_id != user.id:
            raise PermissionDenied("Only the creator can delete this post")

        feed.is_deleted = True
        feed.deleted_at = timezone.now()
        feed.save(update_fields=["is_deleted", "deleted_at"])

        FeedComment.objects.filter(feed=feed, is_deleted=False).update(
            is_deleted=True,
            deleted_at=timezone.now(),
        )
        return True

    @staticmethod
    @transaction.atomic
    def comment_on_feed(user: UserMaster, feed_id: Any, comment_text: str) -> FeedComment:
        if not comment_text:
            raise ValidationError({"comment_text": "comment_text cannot be empty"})
        feed = FeedService.get_visible_feed(feed_id, user)

        if FeedComment.objects.filter(feed=feed, user=user, is_deleted=False).exists():
            raise ValidationError({"comment_text": "You can only comment once per post."})

        comment = FeedComment.objects.create(
            feed=feed,
            user=user,
            comment_text=comment_text,
        )

        Feed.objects.filter(id=feed.id).update(comment_count=F("comment_count") + 1)
        return comment

    @staticmethod
    @transaction.atomic
    def update_feed_comment(user: UserMaster, feed_id: Any, comment_id: Any, comment_text: str) -> FeedComment:
        if not comment_text:
            raise ValidationError({"comment_text": "comment_text cannot be empty"})

        FeedService.get_visible_feed(feed_id, user)

        comment = FeedComment.objects.filter(
            id=comment_id,
            feed_id=feed_id,
            is_deleted=False,
        ).select_related("feed").first()
        if not comment:
            raise ValidationError({"detail": "Comment not found"})

        if comment.user_id != user.id:
            raise PermissionDenied("You can only update your own comment")

        comment.comment_text = comment_text
        comment.save(update_fields=["comment_text"])
        return comment

    @staticmethod
    def get_feed_comments(
        user: UserMaster, feed_id: Any, page: int = 1, page_size: int = 20
    ) -> tuple[QuerySet[FeedComment], int]:
        feed = FeedService.get_visible_feed(feed_id, user)

        offset = (page - 1) * page_size
        queryset = FeedComment.objects.filter(feed=feed, is_deleted=False).select_related("user").order_by("created_at")
        total = queryset.count()
        comments = queryset[offset : offset + page_size]

        return comments, total

    @staticmethod
    @transaction.atomic
    def delete_feed_comment(user: UserMaster, feed_id: Any, comment_id: Any) -> bool:
        FeedService.get_visible_feed(feed_id, user)

        comment = FeedComment.objects.filter(
            id=comment_id,
            feed_id=feed_id,
            is_deleted=False,
        ).select_related("feed").first()
        if not comment:
            raise ValidationError({"detail": "Comment not found"})

        feed = comment.feed

        if user.id not in (comment.user_id, feed.creator_id):
            raise PermissionDenied("You cannot delete this comment")

        comment.is_deleted = True
        comment.deleted_at = timezone.now()
        comment.save(update_fields=["is_deleted", "deleted_at"])

        Feed.objects.filter(id=feed.id).update(
            comment_count=Greatest(F("comment_count") - 1, 0),
        )
        return True

    @staticmethod
    @transaction.atomic
    def react_to_feed(user: UserMaster, feed_id: Any, reaction_string: str | None) -> Feed:
        feed = FeedService.get_visible_feed(feed_id, user)

        existing = FeedReaction.objects.filter(feed=feed, user=user).first()

        if not reaction_string:
            if existing:
                existing.delete()
                Feed.objects.filter(id=feed.id).update(
                    reaction_count=Greatest(F("reaction_count") - 1, 0),
                )
            return feed

        if reaction_string not in ReactionType.values:
            raise ValidationError({"reaction": f"Invalid reaction type: {reaction_string}"})

        if existing:
            if existing.reaction != reaction_string:
                existing.reaction = reaction_string
                existing.save(update_fields=["reaction"])
        else:
            FeedReaction.objects.create(feed=feed, user=user, reaction=reaction_string)
            Feed.objects.filter(id=feed.id).update(reaction_count=F("reaction_count") + 1)

        return feed

    @staticmethod
    @transaction.atomic
    def share_feed(user: UserMaster, feed_id: Any, platform: str) -> bool:
        if not platform:
            raise ValidationError({"platform": "platform is required"})
        feed = FeedService.get_visible_feed(feed_id, user)

        FeedShare.objects.create(feed=feed, user=user, platform=platform)
        Feed.objects.filter(id=feed.id).update(share_count=F("share_count") + 1)
        return True

    @staticmethod
    @transaction.atomic
    def save_feed(user: UserMaster, feed_id: Any) -> Feed:
        feed = FeedService.get_visible_feed(feed_id, user)
        FeedSave.objects.get_or_create(feed=feed, user=user)
        return feed

    @staticmethod
    @transaction.atomic
    def unsave_feed(user: UserMaster, feed_id: Any) -> Feed:
        feed = FeedService.get_visible_feed(feed_id, user)
        FeedSave.objects.filter(feed=feed, user=user).delete()
        return feed

    @staticmethod
    def get_saved_feeds(
        user: UserMaster,
        page: int,
        page_size: int,
    ) -> tuple[list[Feed], int]:
        visible_feed_ids = FeedService.get_feed_queryset(user).values_list("id", flat=True)
        saves_qs = (
            FeedSave.objects.filter(user=user, feed_id__in=visible_feed_ids)
            .select_related("feed", "feed__creator")
            .order_by("-created_at")
        )
        total = saves_qs.count()
        offset = (page - 1) * page_size
        saves = list(saves_qs[offset : offset + page_size])
        return [save.feed for save in saves], total

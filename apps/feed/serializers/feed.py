from typing import Any, cast

from rest_framework import serializers

from apps.core.models import UserMaster
from apps.feed.enums import AccessType, ReactionType, SharePlatform
from apps.feed.models.feed import Feed, FeedComment
from apps.feed.serializers.presentation import (
    build_feed_user_snapshot,
    resolve_public_storage_urls,
)
from apps.feed.validators import validate_feed_content


class FeedListQuerySerializer(serializers.Serializer):
    creator_id = serializers.UUIDField(required=False, allow_null=True)


class FeedCreateSerializer(serializers.Serializer):
    body_text = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    media_urls = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    youtube_url = serializers.CharField(required=False, allow_null=True, max_length=500)
    external_urls = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
    )
    access_type = serializers.ChoiceField(choices=AccessType.choices, required=False, default=AccessType.ONLY_ME)
    access_family_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    access_close_group_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    access_user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        error = validate_feed_content(
            body_text=attrs.get("body_text"),
            media_urls=attrs.get("media_urls"),
            youtube_url=attrs.get("youtube_url"),
            external_urls=attrs.get("external_urls"),
        )
        if error:
            raise serializers.ValidationError(error)
        return attrs

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        result = super().to_internal_value(data)
        if result.get("access_family_ids"):
            result["access_family_ids"] = [str(v) for v in result["access_family_ids"]]
        if result.get("access_close_group_ids"):
            result["access_close_group_ids"] = [str(v) for v in result["access_close_group_ids"]]
        if result.get("access_user_ids"):
            result["access_user_ids"] = [str(v) for v in result["access_user_ids"]]
        return result


class FeedUpdateSerializer(FeedCreateSerializer):
    body_text = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    media_urls = serializers.ListField(child=serializers.CharField(), required=False)
    youtube_url = serializers.CharField(required=False, allow_null=True, max_length=500)
    external_urls = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)
    access_type = serializers.ChoiceField(choices=AccessType.choices, required=False)
    access_family_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    access_close_group_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    access_user_ids = serializers.ListField(child=serializers.UUIDField(), required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if self.partial:
            return attrs
        return super().validate(attrs)


class FeedCommentWriteSerializer(serializers.Serializer):
    comment_text = serializers.CharField(required=True, allow_blank=False)


class FeedReactionWriteSerializer(serializers.Serializer):
    reaction = serializers.ChoiceField(
        choices=ReactionType.choices,
        required=False,
        allow_null=True,
    )


class FeedShareWriteSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=SharePlatform.choices, required=True)


class FeedListSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    body_text = serializers.CharField(source="text", required=False, allow_null=True, allow_blank=True)
    media_urls = serializers.SerializerMethodField()
    created_by = serializers.UUIDField(source="creator_id", read_only=True)
    creator_info = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()

    class Meta:
        model = Feed
        fields = [
            "id",
            "body_text",
            "media_urls",
            "youtube_url",
            "external_urls",
            "created_by",
            "creator_info",
            "access_type",
            "access_family_ids",
            "access_close_group_ids",
            "access_user_ids",
            "reaction_count",
            "comment_count",
            "share_count",
            "my_reaction",
            "is_saved",
            "reactions",
            "created_at",
        ]

    def get_media_urls(self, obj: Feed) -> list[str]:
        return resolve_public_storage_urls(cast(list[str] | None, obj.media_urls))

    def get_creator_info(self, obj: Feed):
        user = getattr(obj, "creator", None)
        if not user:
            return None
        return build_feed_user_snapshot(cast(UserMaster, user))

    def get_my_reaction(self, obj: Feed):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return None

        user_reactions = getattr(obj, "user_reactions", None)
        if user_reactions is not None:
            return user_reactions[0].reaction if user_reactions else None

        all_reactions = getattr(obj, "all_reactions", None)
        if all_reactions is None:
            all_reactions = obj.reactions.all()

        for reaction in all_reactions:
            if str(reaction.user_id) == str(request.user.id):
                return reaction.reaction
        return None

    def get_is_saved(self, obj: Feed) -> bool:
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False

        user_saves = getattr(obj, "user_saves", None)
        if user_saves is not None:
            return bool(user_saves)

        return obj.saves.filter(user_id=request.user.id).exists()

    def get_reactions(self, obj: Feed) -> dict[str, int]:
        all_reactions = getattr(obj, "all_reactions", None)
        if all_reactions is None:
            all_reactions = obj.reactions.all()

        breakdown: dict[str, int] = {}
        for reaction in all_reactions:
            breakdown[reaction.reaction] = breakdown.get(reaction.reaction, 0) + 1
        return breakdown


class FeedCommentSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = FeedComment
        fields = [
            "id",
            "comment_text",
            "user",
            "created_at",
        ]

    def get_user(self, obj: FeedComment):
        user = getattr(obj, "user", None)
        if not user:
            return None
        return build_feed_user_snapshot(cast(UserMaster, user))

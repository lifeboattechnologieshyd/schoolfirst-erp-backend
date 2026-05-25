from django.utils import timezone
from rest_framework import serializers

from apps.calendar.enums import AccessType, CommentParentType, ReminderType
from apps.calendar.models import Comment, Event
from apps.calendar.models.general_event import GeneralEvent
from apps.calendar.serializers.calendar import LocationSerializer, validate_access_fields, validate_access_membership
from apps.calendar.serializers.comment import CommentReadSerializer
from apps.calendar.serializers.rrule import RRuleSerializer
from apps.calendar.validators import TimezoneDateTimeField


class EventWriteSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=255)
    start_at = TimezoneDateTimeField()
    end_at = TimezoneDateTimeField(required=False, allow_null=True)
    all_day = serializers.BooleanField(required=False, default=False)
    description = serializers.CharField(required=False, allow_null=True)
    event_type = serializers.CharField(max_length=100, required=False, allow_null=True)
    access_type = serializers.ChoiceField(choices=AccessType.choices, required=False)
    access_family_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_null=True, default=list
    )
    access_close_group_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_null=True, default=list
    )
    access_user_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_null=True, default=list
    )
    reminder_datetime = TimezoneDateTimeField(required=False, allow_null=True)
    reminder_types = serializers.ListField(
        child=serializers.ChoiceField(choices=ReminderType.choices),
        required=False,
        allow_null=True,
    )
    location = LocationSerializer(required=False, allow_null=True)
    attachments = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)
    rrule = RRuleSerializer(required=False, allow_null=True)
    occurrence_date = serializers.DateField(source="recurrence_date", required=False, allow_null=True)

    class Meta:
        model = Event
        fields = [
            "title",
            "start_at",
            "end_at",
            "all_day",
            "description",
            "event_type",
            "access_type",
            "access_family_ids",
            "access_close_group_ids",
            "access_user_ids",
            "reminder_datetime",
            "reminder_types",
            "location",
            "attachments",
            "rrule",
            "occurrence_date",
        ]

    def validate(self, attrs):
        validate_access_fields(attrs)
        start_at = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(self.instance, "end_at", None))

        if not self.partial and start_at is not None and start_at.date() < timezone.now().date():
            raise serializers.ValidationError({"start_at": "start_at cannot be in the past."})

        if start_at is not None and end_at is not None and end_at < start_at:
            raise serializers.ValidationError({"end_at": "end_at must be greater than or equal to start_at."})

        request = self.context.get("request")
        if request is not None:
            validate_access_membership(request.user, attrs)

        return attrs

    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        if result.get("access_family_ids"):
            result["access_family_ids"] = [str(v) for v in result["access_family_ids"]]
        if result.get("access_close_group_ids"):
            result["access_close_group_ids"] = [str(v) for v in result["access_close_group_ids"]]
        if result.get("access_user_ids"):
            result["access_user_ids"] = [str(v) for v in result["access_user_ids"]]
        return result


class EventReadSerializer(serializers.ModelSerializer):
    comments = serializers.SerializerMethodField()
    occurrence_date = serializers.DateField(source="recurrence_date", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "creator_id",
            "title",
            "description",
            "event_type",
            "access_type",
            "access_family_ids",
            "access_close_group_ids",
            "access_user_ids",
            "start_at",
            "end_at",
            "all_day",
            "reminder_datetime",
            "reminder_types",
            "location",
            "attachments",
            "rrule",
            "parent_event_id",
            "occurrence_date",
            "recurrence_end_date",
            "is_deleted_instance",
            "comment_count",
            "created_at",
            "updated_at",
            "comments",
        ]

    def get_comments(self, obj):
        if self.context.get("include_comments", False):
            qs = Comment.objects.filter(
                parent_type=CommentParentType.EVENT,
                parent_id=obj.id,
                deleted_at__isnull=True,
            ).order_by("created_at")
            return CommentReadSerializer(qs, many=True).data
        return []


class EventListSerializer(serializers.ModelSerializer):
    occurrence_date = serializers.DateField(source="recurrence_date", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "creator_id",
            "title",
            "description",
            "event_type",
            "access_type",
            "access_family_ids",
            "access_close_group_ids",
            "access_user_ids",
            "start_at",
            "end_at",
            "all_day",
            "reminder_datetime",
            "reminder_types",
            "location",
            "attachments",
            "rrule",
            "parent_event_id",
            "occurrence_date",
            "recurrence_end_date",
            "is_deleted_instance",
            "comment_count",
            "created_at",
            "updated_at",
        ]


class EventCalendarSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "event_type",
            "start_at",
            "end_at",
            "all_day",
            "rrule",
            "recurrence_end_date",
            "comment_count",
        ]


class GeneralEventCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralEvent
        fields = [
            "id",
            "title",
            "description",
            "event_at",
        ]

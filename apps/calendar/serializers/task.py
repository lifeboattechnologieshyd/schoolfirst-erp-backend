from django.utils import timezone
from rest_framework import serializers

from apps.calendar.enums import AccessType, CommentParentType, ReminderType, TaskPriority, TaskStatus
from apps.calendar.models import Comment, Task
from apps.calendar.serializers.calendar import LocationSerializer, validate_access_fields, validate_access_membership
from apps.calendar.serializers.comment import CommentReadSerializer
from apps.calendar.serializers.rrule import RRuleSerializer
from apps.calendar.validators import TimezoneDateTimeField


class TaskWriteSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_null=True)
    task_type = serializers.CharField(max_length=100, required=False, allow_null=True)
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
    priority = serializers.ChoiceField(choices=TaskPriority.choices, required=False, default=TaskPriority.ROUTINE)
    agent_assist = serializers.BooleanField(required=False, default=False)
    deadline_datetime = TimezoneDateTimeField(required=False, allow_null=True)
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
        model = Task
        fields = [
            "title",
            "description",
            "task_type",
            "access_type",
            "access_family_ids",
            "access_close_group_ids",
            "access_user_ids",
            "priority",
            "agent_assist",
            "deadline_datetime",
            "reminder_datetime",
            "reminder_types",
            "location",
            "attachments",
            "rrule",
            "occurrence_date",
        ]

    def validate(self, attrs):
        validate_access_fields(attrs)
        deadline_datetime = attrs.get("deadline_datetime")
        reminder_datetime = attrs.get("reminder_datetime")
        if not self.partial and deadline_datetime is not None and deadline_datetime.date() < timezone.now().date():
            raise serializers.ValidationError({"deadline_datetime": "deadline_datetime cannot be in the past."})
        if deadline_datetime is not None and reminder_datetime is not None and reminder_datetime >= deadline_datetime:
            raise serializers.ValidationError(
                {"reminder_datetime": "reminder_datetime must be before deadline_datetime."}
            )

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


class TaskReadSerializer(serializers.ModelSerializer):
    comments = serializers.SerializerMethodField()
    occurrence_date = serializers.DateField(source="recurrence_date", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "creator_id",
            "title",
            "description",
            "task_type",
            "access_type",
            "access_family_ids",
            "access_close_group_ids",
            "access_user_ids",
            "status",
            "done_by",
            "completed_at",
            "acknowledged_at",
            "is_visible",
            "priority",
            "agent_assist",
            "deadline_datetime",
            "reminder_datetime",
            "reminder_types",
            "location",
            "attachments",
            "rrule",
            "parent_task_id",
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
                parent_type=CommentParentType.TASK,
                parent_id=obj.id,
                deleted_at__isnull=True,
            ).order_by("created_at")
            return CommentReadSerializer(qs, many=True).data
        return []


class TaskListSerializer(serializers.ModelSerializer):
    occurrence_date = serializers.DateField(source="recurrence_date", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "creator_id",
            "title",
            "description",
            "task_type",
            "access_type",
            "access_family_ids",
            "access_close_group_ids",
            "access_user_ids",
            "status",
            "done_by",
            "completed_at",
            "acknowledged_at",
            "priority",
            "is_visible",
            "agent_assist",
            "deadline_datetime",
            "reminder_datetime",
            "reminder_types",
            "location",
            "attachments",
            "rrule",
            "parent_task_id",
            "occurrence_date",
            "recurrence_end_date",
            "is_deleted_instance",
            "comment_count",
            "created_at",
            "updated_at",
        ]


class TaskCalendarSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "status",
            "priority",
            "deadline_datetime",
            "rrule",
            "recurrence_end_date",
            "comment_count",
        ]


class TaskStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TaskStatus.choices)

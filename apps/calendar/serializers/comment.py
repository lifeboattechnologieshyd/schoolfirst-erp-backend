from rest_framework import serializers

from apps.calendar.models import Comment


class CommentBodySerializer(serializers.Serializer):
    """Nested comment endpoint serializer (parent comes from URL)."""

    comment = serializers.CharField()
    occurrence_date = serializers.DateField(required=False, allow_null=True)


class CommentReadSerializer(serializers.ModelSerializer):
    comment = serializers.CharField(source="body")

    class Meta:
        model = Comment
        fields = [
            "id",
            "parent_type",
            "parent_id",
            "user_id",
            "comment",
            "created_at",
            "deleted_at",
        ]

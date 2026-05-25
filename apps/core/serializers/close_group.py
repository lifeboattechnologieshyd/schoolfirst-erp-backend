from rest_framework import serializers

from apps.core.models.close_group import CloseGroup, CloseGroupMember


class CloseGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloseGroup
        fields = ["id", "name", "member_count"]


class CloseGroupMemberAddSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class CloseGroupMemberSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = CloseGroupMember
        fields = ["id", "user", "email", "first_name", "last_name", "profile_image", "status", "created_at"]

    def get_first_name(self, obj):
        return obj.user.first_name if obj.user else None

    def get_last_name(self, obj):
        return obj.user.last_name if obj.user else None

    def get_profile_image(self, obj):
        return obj.user.profile_image if obj.user else None


class CloseGroupAddedMeSerializer(serializers.Serializer):
    """Serialize a UserMaster who added me to their close group."""

    id = serializers.UUIDField()
    email = serializers.EmailField()
    first_name = serializers.CharField(allow_null=True)
    last_name = serializers.CharField(allow_null=True)
    profile_image = serializers.CharField(allow_null=True)

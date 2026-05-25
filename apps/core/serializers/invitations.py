from rest_framework import serializers

from apps.core.models.user import InvitationCode


class InvitationCodeSerializer(serializers.ModelSerializer):
    remaining_uses = serializers.SerializerMethodField()

    class Meta:
        model = InvitationCode
        fields = [
            "id",
            "code",
            "code_type",
            "target_email",
            "max_uses",
            "current_uses",
            "remaining_uses",
            "expires_at",
            "is_active",
            "created_at",
        ]

    def get_remaining_uses(self, obj):
        return obj.max_uses - obj.current_uses

from rest_framework import serializers

from apps.core.models import MembershipApplication


class MembershipApplicationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    mobile = serializers.CharField(max_length=20, required=False, allow_null=True)
    source = serializers.CharField(max_length=100, required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_null=True)

    def validate_email(self, value: str) -> str:
        if MembershipApplication.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An application with this email already exists.")
        return value

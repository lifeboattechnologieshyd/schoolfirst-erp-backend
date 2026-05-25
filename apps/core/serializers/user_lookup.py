from rest_framework import serializers


class UserLookupRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class UserLookupResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    first_name = serializers.CharField(allow_null=True)
    last_name = serializers.CharField(allow_null=True)
    gender = serializers.CharField(allow_null=True)
    profile_image = serializers.CharField(allow_null=True)

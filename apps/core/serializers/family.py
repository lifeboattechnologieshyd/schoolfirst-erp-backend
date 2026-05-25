from rest_framework import serializers

from apps.core.constants import ALLOWED_IMAGE_EXTENSIONS
from apps.core.models.family import Family, FamilyMember
from shared.utils.files import get_file_url, validate_image_temp_path


class FamilyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, max_length=150)
    family_picture = serializers.CharField(required=False, allow_null=True, max_length=500)

    def validate_family_picture(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        error = validate_image_temp_path(value, request.user.id, ALLOWED_IMAGE_EXTENSIONS)
        if error:
            raise serializers.ValidationError(error)
        return value


class FamilySerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    family_picture = serializers.SerializerMethodField()
    user_status = serializers.SerializerMethodField()

    class Meta:
        model = Family
        fields = ["id", "name", "family_picture", "owner_name", "member_count", "is_owner", "user_status", "created_at"]

    def get_family_picture(self, obj):
        return get_file_url(obj.family_picture) if obj.family_picture else None

    def get_owner_name(self, obj):
        if hasattr(obj, "owner") and obj.owner:
            return obj.owner.first_name or obj.owner.email
        return None

    def get_member_count(self, obj):
        return getattr(obj, "joined_member_count", 0) or 0

    def get_is_owner(self, obj):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            return str(obj.owner_id) == str(request.user.id)
        return False

    def get_user_status(self, obj):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            member = FamilyMember.objects.filter(family=obj, user_id=request.user.id).first()
            return member.status if member else None
        return None


class FamilyMemberSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = FamilyMember
        fields = [
            "id",
            "user",
            "email",
            "first_name",
            "last_name",
            "gender",
            "profile_image",
            "role",
            "status",
            "relation",
            "created_at",
        ]

    def get_first_name(self, obj):
        if obj.user:
            return obj.user.first_name
        return obj.first_name

    def get_last_name(self, obj):
        if obj.user:
            return obj.user.last_name
        return obj.last_name

    def get_gender(self, obj):
        if obj.user:
            return obj.user.gender
        return obj.gender

    def get_profile_image(self, obj):
        return obj.user.profile_image if obj.user else None


class FamilyDetailSerializer(FamilySerializer):
    members = serializers.SerializerMethodField()

    class Meta(FamilySerializer.Meta):
        fields = [*FamilySerializer.Meta.fields, "members"]

    def get_members(self, obj):
        request = self.context.get("request")
        is_owner = (
            request and request.user and request.user.is_authenticated and str(obj.owner_id) == str(request.user.id)
        )

        if is_owner:
            members = obj.members.exclude(status=FamilyMember.Status.REMOVED).select_related("user")
        else:
            members = obj.members.filter(
                status__in=[FamilyMember.Status.JOINED, FamilyMember.Status.INVITED]
            ).select_related("user")

        return FamilyMemberSerializer(members, many=True).data


class FamilyMemberAddSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    relation = serializers.ChoiceField(choices=FamilyMember.Relation.choices, required=False, allow_null=True)
    first_name = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    last_name = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    gender = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=255)


class FamilyInvitationSerializer(serializers.ModelSerializer):
    family_name = serializers.CharField(source="family.name", read_only=True)
    family_picture = serializers.SerializerMethodField()
    invited_by_name = serializers.SerializerMethodField()

    def get_family_picture(self, obj):
        return get_file_url(obj.family.family_picture) if obj.family.family_picture else None

    class Meta:
        model = FamilyMember
        fields = [
            "id",
            "family",
            "family_name",
            "family_picture",
            "role",
            "status",
            "relation",
            "invited_by_name",
            "created_at",
        ]

    def get_invited_by_name(self, obj):
        if obj.invited_by:
            return obj.invited_by.first_name or obj.invited_by.email
        return None

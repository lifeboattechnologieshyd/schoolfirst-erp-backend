from rest_framework import serializers

from apps.docusafe.models.folder import DocusafeFolder


class DocusafeFolderSerializer(serializers.ModelSerializer):
    """
    Base serializer for DocusafeFolder model (Minimal for listing).
    """

    class Meta:
        model = DocusafeFolder
        fields = [
            "id",
            "name",
            "file_count",
            "total_size",
            "is_shared",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class DocusafeFolderDetailSerializer(DocusafeFolderSerializer):
    """
    Detailed serializer for DocusafeFolder model.
    """

    class Meta(DocusafeFolderSerializer.Meta):
        fields = [
            *DocusafeFolderSerializer.Meta.fields,
            "description",
            "owner_id",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner_id",
            "file_count",
            "total_size",
            "is_shared",
            "created_at",
            "updated_at",
        ]

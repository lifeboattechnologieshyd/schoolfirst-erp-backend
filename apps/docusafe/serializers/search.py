from rest_framework import serializers


class SearchQuerySerializer(serializers.Serializer):
    """Validates search request body."""

    query = serializers.CharField(max_length=1000, help_text="Natural language search query.")
    folder_id = serializers.UUIDField(required=False, help_text="Optional folder filter.")
    limit = serializers.IntegerField(
        required=False,
        default=10,
        min_value=1,
        max_value=50,
        help_text="Maximum results to return (default: 10, max: 50).",
    )


class SearchResultSerializer(serializers.Serializer):
    """Serializes a single search result."""

    file_id = serializers.UUIDField()
    file_name = serializers.CharField()
    folder_id = serializers.UUIDField()
    file_extension = serializers.CharField()
    mime_type = serializers.CharField()
    file_size = serializers.IntegerField()
    score = serializers.FloatField()
    match_type = serializers.CharField(help_text="Type of match: CHUNK, TITLE, or SUMMARY.")

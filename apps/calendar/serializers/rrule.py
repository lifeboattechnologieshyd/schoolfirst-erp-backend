from rest_framework import serializers

from apps.calendar.enums import RecurringFrequency

VALID_WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


class RRuleSerializer(serializers.Serializer):
    frequency = serializers.ChoiceField(choices=RecurringFrequency.choices)
    interval = serializers.IntegerField(min_value=1, required=False, default=1)
    by_day = serializers.ListField(
        child=serializers.ChoiceField(choices=VALID_WEEKDAYS),
        required=False,
        allow_null=True,
    )
    by_month_day = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=31),
        required=False,
        allow_null=True,
    )
    count = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    until = serializers.DateField(required=False, allow_null=True)

    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        if result.get("until") is not None:
            result["until"] = result["until"].isoformat()
        return result

    def validate(self, attrs):
        if attrs.get("count") and attrs.get("until"):
            raise serializers.ValidationError("Only one of 'count' or 'until' may be specified.")
        if not attrs.get("until"):
            raise serializers.ValidationError({"until": "An end date (until) is required."})
        return attrs

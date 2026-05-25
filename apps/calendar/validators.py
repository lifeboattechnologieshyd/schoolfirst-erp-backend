import re

from rest_framework import serializers

# Matches strings that end with 'Z', '+HH:MM', '-HH:MM', '+HHMM', '-HHMM'
_TZ_RE = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


class TimezoneDateTimeField(serializers.DateTimeField):
    """
    DateTimeField that rejects naive datetime strings before DRF's enforce_timezone
    converts them.  DRF (with USE_TZ=True) silently makes naive datetimes
    timezone-aware, so validators on the parsed value never see them as naive.
    This subclass intercepts at the raw-string level.
    """

    def to_internal_value(self, value):
        if isinstance(value, str) and not _TZ_RE.search(value.rstrip()):
            raise serializers.ValidationError("Datetime must include timezone information (e.g. 2025-06-15T18:00:00Z).")
        return super().to_internal_value(value)

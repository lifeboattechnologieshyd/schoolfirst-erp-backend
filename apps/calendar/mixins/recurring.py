from django.db import models


class RecurringMixin(models.Model):
    """
    iCalendar-inspired recurrence mixin.

    rrule               — structured recurrence rule dict; None means non-recurring.
                          Keys: frequency (required), interval, by_day,
                          by_month_day, count, until (ISO date string).
    recurrence_date     — the original occurrence date this override row replaces.
    recurrence_end_date — denormalized from rrule.until for efficient date-range
                          filtering. None when rrule uses count or has no fixed end.
    is_deleted_instance — tombstone flag: True means this override
                            deletes the occurrence.
    """

    rrule = models.JSONField(null=True)
    recurrence_date = models.DateField(null=True)
    recurrence_end_date = models.DateField(null=True)
    is_deleted_instance = models.BooleanField(default=False)

    class Meta:
        abstract = True

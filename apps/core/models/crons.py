from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class CronJobLocks(models.Model):
    job_name = models.CharField(max_length=100, primary_key=True, editable=False)
    acquired = models.BooleanField(default=False)
    enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cronjob_locks"

    def __str__(self) -> str:
        return str(self.job_name)

    # Type declarations for static analysis
    objects: models.Manager[CronJobLocks] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

import os

import structlog
from django.db import transaction

from apps.core.models import CronJobLocks

logger = structlog.getLogger("default")


def acquire_db_lock(job_name) -> bool:
    try:
        with transaction.atomic():
            try:
                lock_obj, created = CronJobLocks.objects.select_for_update().get_or_create(job_name=job_name)
                if created or not lock_obj.acquired:
                    lock_obj.created_at = lock_obj.updated_at
                    lock_obj.acquired = True
                    lock_obj.save()
                    return True
            except Exception:
                logger.debug("Acquiring DB lock failed")
                return False
        logger.debug(f"The DB Lock for Cron Job '{job_name}' is already acquired.")

        return False
    except Exception:
        logger.debug("Acquiring DB lock failed")
        return False


def release_db_lock(job_name) -> bool:
    try:
        lock_obj = CronJobLocks.objects.filter(job_name=job_name).get()
        lock_obj.acquired = False
        lock_obj.save()
        return True
    except CronJobLocks.DoesNotExist:
        logger.debug(f"The DB Lock for Cron Job '{job_name}' is not found.")
        return False
    except Exception:
        logger.debug("Releasing DB lock failed")
        return False


#################################################
# TO ACQUIRE LOCK ON A SPECIFIC FILE #
#################################################
def acquire_lock(file: str) -> bool | None:
    try:
        os.open(file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        return True
    except FileExistsError:
        logger.debug(f"File : {file} is already locked by another instance of the cron job!")
        return False
    except Exception:
        logger.debug(f"Error while acquiring lock on file: {file}")
        return False


#################################################
# TO RELEASE LOCK ON A SPECIFIC FILE #
#################################################
def release_lock(file: str) -> bool | None:
    try:
        os.unlink(file)
        return True
    except FileNotFoundError:
        logger.exception(f"File : {file} is not found to release the lock!")
        return False

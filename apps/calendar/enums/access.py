from django.db import models


class AccessType(models.TextChoices):
    ONLY_ME = "only_me", "Only Me"
    ALL = "all", "All"
    MIXED = "mixed", "Mixed"


class ReminderType(models.TextChoices):
    PUSH = "push", "Push"
    FULL_SCREEN = "full_screen", "Full Screen"
    EMAIL = "email", "Email"

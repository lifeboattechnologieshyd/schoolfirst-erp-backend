from django.db import models


class AccessType(models.TextChoices):
    ONLY_ME = "only_me", "Only Me"
    ALL = "all", "All Family"
    MIXED = "mixed", "Selected Entities"

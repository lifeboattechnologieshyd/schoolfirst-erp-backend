from django.db import models


class SharePlatform(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    FACEBOOK = "facebook", "Facebook"
    TWITTER = "twitter", "Twitter"
    NATIVE = "native", "Native Share"
    COPY_LINK = "copy_link", "Copy Link"
    OTHER = "other", "Other"

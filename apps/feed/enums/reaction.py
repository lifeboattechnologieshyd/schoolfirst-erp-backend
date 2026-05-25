from django.db import models


class ReactionType(models.TextChoices):
    LIKE = "like", "👍"
    LOVE = "love", "❤️"
    LAUGH = "laugh", "😂"
    WOW = "wow", "😮"
    SAD = "sad", "😢"
    ANGRY = "angry", "😡"
    CELEBRATE = "celebrate", "🎉"

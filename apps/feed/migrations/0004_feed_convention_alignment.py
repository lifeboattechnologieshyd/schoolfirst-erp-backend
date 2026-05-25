# Feed convention alignment: rename author FK, restore audit field, indexes, constraints.

from django.conf import settings
from django.db import migrations, models


def backfill_feed_audit_created_by(apps, schema_editor):
    """Populate audit created_by from creator_id after the FK rename."""
    feed_model = apps.get_model("feed", "Feed")
    for feed in feed_model.objects.exclude(creator_id__isnull=True).iterator():
        feed_model.objects.filter(pk=feed.pk).update(created_by=str(feed.creator_id))


def normalize_feed_share_platforms(apps, schema_editor):
    """Map legacy free-text platforms to a valid choice before applying constraints."""
    feed_share = apps.get_model("feed", "FeedShare")
    valid_platforms = {"whatsapp", "facebook", "twitter", "native", "copy_link", "other"}
    for share in feed_share.objects.exclude(platform__in=valid_platforms).iterator():
        feed_share.objects.filter(pk=share.pk).update(platform="other")


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0003_remove_feed_feed_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Rename FK column created_by_id -> creator_id (no default prompt; data preserved).
        migrations.RenameField(
            model_name="feed",
            old_name="created_by",
            new_name="creator",
        ),
        # Restore AuditModel.created_by CharField (distinct from creator FK).
        migrations.AddField(
            model_name="feed",
            name="created_by",
            field=models.CharField(editable=False, max_length=255, null=True),
        ),
        migrations.RunPython(backfill_feed_audit_created_by, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="feed",
            name="text",
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name="feed",
            name="media_urls",
            field=models.JSONField(default=list),
        ),
        migrations.AlterField(
            model_name="feed",
            name="youtube_url",
            field=models.CharField(max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name="feed",
            name="access_family_ids",
            field=models.JSONField(default=list, null=True),
        ),
        migrations.AlterField(
            model_name="feed",
            name="access_close_group_ids",
            field=models.JSONField(default=list, null=True),
        ),
        migrations.AlterField(
            model_name="feed",
            name="access_user_ids",
            field=models.JSONField(default=list, null=True),
        ),
        migrations.AlterField(
            model_name="feed",
            name="deleted_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name="feedcomment",
            name="deleted_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(normalize_feed_share_platforms, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="feedshare",
            name="platform",
            field=models.CharField(
                choices=[
                    ("whatsapp", "WhatsApp"),
                    ("facebook", "Facebook"),
                    ("twitter", "Twitter"),
                    ("native", "Native Share"),
                    ("copy_link", "Copy Link"),
                    ("other", "Other"),
                ],
                max_length=50,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="feedreaction",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="feedreaction",
            constraint=models.UniqueConstraint(
                fields=("feed", "user"),
                name="feed_reactions_feed_user_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="feed",
            index=models.Index(fields=["creator", "-created_at"], name="feeds_creator_a63108_idx"),
        ),
        migrations.AddIndex(
            model_name="feed",
            index=models.Index(fields=["is_deleted"], name="feeds_is_dele_fd454d_idx"),
        ),
        migrations.AddIndex(
            model_name="feed",
            index=models.Index(fields=["access_type"], name="feeds_access__6ff40b_idx"),
        ),
        migrations.AddIndex(
            model_name="feedcomment",
            index=models.Index(fields=["feed", "created_at"], name="feed_commen_feed_id_afc08c_idx"),
        ),
        migrations.AddIndex(
            model_name="feedcomment",
            index=models.Index(fields=["is_deleted"], name="feed_commen_is_dele_bcb026_idx"),
        ),
        migrations.AddIndex(
            model_name="feedshare",
            index=models.Index(fields=["feed"], name="feed_shares_feed_id_c029ef_idx"),
        ),
    ]

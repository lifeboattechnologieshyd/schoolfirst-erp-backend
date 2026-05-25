from django.db import migrations


class Migration(migrations.Migration):
    """
    State-only migration: removes feed models from the 'core' app state.
    No database operations are performed — tables are retained as-is.
    Models are now owned by the 'feed' app (apps/feed/migrations/0001_initial.py).
    """

    dependencies = [
        ("core", "0008_invitation_code_numeric_6digits"),
        ("feed", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel("FamilyFeedVisibility"),
                migrations.DeleteModel("FamilyFeedSave"),
                migrations.DeleteModel("FamilyFeedReaction"),
                migrations.DeleteModel("FamilyFeedMedia"),
                migrations.DeleteModel("FamilyFeedComment"),
                migrations.DeleteModel("FamilyFeed"),
            ],
            database_operations=[],
        ),
    ]

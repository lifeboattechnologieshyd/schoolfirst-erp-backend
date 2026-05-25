import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


def cleanup_local_orphans(apps, schema_editor):
    DocusafeFile = apps.get_model("docusafe", "DocusafeFile")
    DocusafeFolder = apps.get_model("docusafe", "DocusafeFolder")
    DocusafeFileAccess = apps.get_model("docusafe", "DocusafeFileAccess")
    ShareViewLog = apps.get_model("docusafe", "ShareViewLog")
    TemporaryFileShare = apps.get_model("docusafe", "TemporaryFileShare")
    TemporaryShareFile = apps.get_model("docusafe", "TemporaryShareFile")

    orphan_file_ids = list(
        DocusafeFile.objects.exclude(folder_id__in=DocusafeFolder.objects.values("id")).values_list("id", flat=True)
    )
    if orphan_file_ids:
        TemporaryShareFile.objects.filter(file_id__in=orphan_file_ids).delete()
        DocusafeFileAccess.objects.filter(file_id__in=orphan_file_ids).delete()
        DocusafeFile.objects.filter(id__in=orphan_file_ids).delete()

    TemporaryShareFile.objects.filter(
        ~Q(share_id__in=TemporaryFileShare.objects.values("id"))
        | ~Q(file_id__in=DocusafeFile.objects.values("id"))
    ).delete()

    ShareViewLog.objects.exclude(share_id__in=TemporaryFileShare.objects.values("id")).delete()
    DocusafeFileAccess.objects.exclude(file_id__in=DocusafeFile.objects.values("id")).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("docusafe", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(cleanup_local_orphans, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE docusafe_file "
                        "ADD CONSTRAINT docusafe_file_folder_fk "
                        "FOREIGN KEY (folder_id) REFERENCES docusafe_folder (id) "
                        "DEFERRABLE INITIALLY DEFERRED"
                    ),
                    reverse_sql="ALTER TABLE docusafe_file DROP CONSTRAINT docusafe_file_folder_fk",
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE docusafe_temporary_share_file "
                        "ADD CONSTRAINT docusafe_sharefile_share_fk "
                        "FOREIGN KEY (share_id) REFERENCES docusafe_temporary_share (id) "
                        "ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED"
                    ),
                    reverse_sql=(
                        "ALTER TABLE docusafe_temporary_share_file "
                        "DROP CONSTRAINT docusafe_sharefile_share_fk"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE docusafe_temporary_share_file "
                        "ADD CONSTRAINT docusafe_sharefile_file_fk "
                        "FOREIGN KEY (file_id) REFERENCES docusafe_file (id) "
                        "ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED"
                    ),
                    reverse_sql=(
                        "ALTER TABLE docusafe_temporary_share_file "
                        "DROP CONSTRAINT docusafe_sharefile_file_fk"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE docusafe_share_view_log "
                        "ADD CONSTRAINT docusafe_viewlog_share_fk "
                        "FOREIGN KEY (share_id) REFERENCES docusafe_temporary_share (id) "
                        "ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED"
                    ),
                    reverse_sql="ALTER TABLE docusafe_share_view_log DROP CONSTRAINT docusafe_viewlog_share_fk",
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE docusafe_file_access "
                        "ADD CONSTRAINT docusafe_access_file_fk "
                        "FOREIGN KEY (file_id) REFERENCES docusafe_file (id) "
                        "ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED"
                    ),
                    reverse_sql="ALTER TABLE docusafe_file_access DROP CONSTRAINT docusafe_access_file_fk",
                ),
            ],
            state_operations=[
                migrations.RenameField(
                    model_name="docusafefile",
                    old_name="folder_id",
                    new_name="folder",
                ),
                migrations.AlterField(
                    model_name="docusafefile",
                    name="folder",
                    field=models.ForeignKey(
                        db_column="folder_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="files",
                        to="docusafe.docusafefolder",
                    ),
                ),
                migrations.RenameField(
                    model_name="docusafefileaccess",
                    old_name="file_id",
                    new_name="file",
                ),
                migrations.AlterField(
                    model_name="docusafefileaccess",
                    name="file",
                    field=models.ForeignKey(
                        db_column="file_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_grants",
                        to="docusafe.docusafefile",
                    ),
                ),
                migrations.RenameField(
                    model_name="temporarysharefile",
                    old_name="share_id",
                    new_name="share",
                ),
                migrations.RenameField(
                    model_name="temporarysharefile",
                    old_name="file_id",
                    new_name="file",
                ),
                migrations.AlterField(
                    model_name="temporarysharefile",
                    name="share",
                    field=models.ForeignKey(
                        db_column="share_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="share_files",
                        to="docusafe.temporaryfileshare",
                    ),
                ),
                migrations.AlterField(
                    model_name="temporarysharefile",
                    name="file",
                    field=models.ForeignKey(
                        db_column="file_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="temporary_share_files",
                        to="docusafe.docusafefile",
                    ),
                ),
                migrations.RenameField(
                    model_name="shareviewlog",
                    old_name="share_id",
                    new_name="share",
                ),
                migrations.AlterField(
                    model_name="shareviewlog",
                    name="share",
                    field=models.ForeignKey(
                        db_column="share_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="view_logs",
                        to="docusafe.temporaryfileshare",
                    ),
                ),
                migrations.RemoveIndex(
                    model_name="docusafefile",
                    name="docusafe_fi_folder__ed32d1_idx",
                ),
                migrations.RemoveIndex(
                    model_name="docusafefileaccess",
                    name="docusafe_fi_file_id_c5bb17_idx",
                ),
                migrations.RemoveIndex(
                    model_name="shareviewlog",
                    name="docusafe_sh_share_i_56d9cd_idx",
                ),
                migrations.RemoveIndex(
                    model_name="temporarysharefile",
                    name="docusafe_te_share_i_e6bec1_idx",
                ),
                migrations.RemoveIndex(
                    model_name="temporarysharefile",
                    name="docusafe_te_file_id_793cee_idx",
                ),
                migrations.AddIndex(
                    model_name="docusafefile",
                    index=models.Index(fields=["folder"], name="docusafe_fi_folder__ed32d1_idx"),
                ),
                migrations.AddIndex(
                    model_name="docusafefileaccess",
                    index=models.Index(fields=["file"], name="docusafe_fi_file_id_c5bb17_idx"),
                ),
                migrations.AddIndex(
                    model_name="shareviewlog",
                    index=models.Index(fields=["share"], name="docusafe_sh_share_i_56d9cd_idx"),
                ),
                migrations.AddIndex(
                    model_name="temporarysharefile",
                    index=models.Index(fields=["share"], name="docusafe_te_share_i_e6bec1_idx"),
                ),
                migrations.AddIndex(
                    model_name="temporarysharefile",
                    index=models.Index(fields=["file"], name="docusafe_te_file_id_793cee_idx"),
                ),
            ],
        ),
    ]

from pathlib import Path

##############################################
#         CRON Jobs & Task Scheduling        #
##############################################
BASE_DIR = Path(__file__).resolve().parent.parent


CRONJOBS = [
    # Every 24 hours cleanup expired OTPs and invitation codes (runs at 2 AM daily)
    ("0 2 * * *", "django.core.management.call_command", ["cleanup_expired_auth_data"]),
    # Every 24 hours cleanup temporary files (runs at 3 AM daily)
    ("0 3 * * *", "django.core.management.call_command", ["cleanup_temp_files"]),
    # Every minute process docusafe embeddings
    ("* * * * *", "django.core.management.call_command", ["process_embeddings"]),
    # Every minute cleanup expired temporary shares
    ("* * * * *", "django.core.management.call_command", ["cleanup_expired_shares"]),
    # Every 5 minutes cleanup deleted docusafe files and folders
    ("*/5 * * * *", "django.core.management.call_command", ["cleanup_docusafe"]),
]

import os
from pathlib import Path

from shared.utils import get_from_env, str_to_bool

BASE_DIR = Path(__file__).resolve().parent.parent

# --- AWS S3 Settings ---
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME")
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", None)  # Optional: set for MinIO
AWS_S3_USE_SSL = get_from_env("AWS_S3_USE_SSL", True, type_cast=str_to_bool)


STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "region_name": AWS_S3_REGION_NAME,
            "bucket_name": AWS_S3_BUCKET,
            "endpoint_url": AWS_S3_ENDPOINT_URL or None,
            "use_ssl": AWS_S3_USE_SSL,
        },
    },
    "staticfiles": {  # Static files
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "region_name": AWS_S3_REGION_NAME,
            "bucket_name": AWS_S3_BUCKET,
            "endpoint_url": AWS_S3_ENDPOINT_URL or None,
            "use_ssl": AWS_S3_USE_SSL,
            "location": "public",
        },
    },
}


DATA_UPLOAD_MAX_MEMORY_SIZE = 4294967296  # 4GB
FILE_UPLOAD_MAX_MEMORY_SIZE = 4294967296  # 4GB


STATICFILES_DIRS = [os.path.join(BASE_DIR, "templates")]

if AWS_S3_USE_SSL:
    STATIC_URL = f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/static/"
    if AWS_S3_ENDPOINT_URL:
        STATIC_URL = f"{AWS_S3_ENDPOINT_URL}/static/"
    else:
        STATIC_URL = f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/static/"
elif AWS_S3_ENDPOINT_URL:
    STATIC_URL = f"{AWS_S3_ENDPOINT_URL}/static/"
else:
    STATIC_URL = f"http://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/static/"

if AWS_S3_ENDPOINT_URL:
    MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/media/"
elif AWS_S3_USE_SSL:
    MEDIA_URL = f"https://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/"
else:
    MEDIA_URL = f"http://{AWS_S3_BUCKET}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/"

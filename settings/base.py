import logging
import os
from pathlib import Path

from config.logs import LOGGING  # noqa: F401, F403
from shared.utils import get_from_env, str_to_bool

# --- Django Core ---
DEBUG = get_from_env("DEBUG", False, type_cast=str_to_bool)
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
ROOT_URLCONF = "settings.urls"
WSGI_APPLICATION = "settings.wsgi.application"
APPEND_SLASH = False


# --- Project Metadata ---
NAMESPACE = os.environ.get("NAMESPACE", "local")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "SCHOOLFIRST-ERP-BACKEND")
SERVICE_VERSION = os.environ.get("SERVICE_VERSION", "1.0.0")


# --- Feature Flags ---
ENABLE_DOCS = get_from_env("ENABLE_DOCS", False, type_cast=str_to_bool)
ENABLE_EMAIL = get_from_env("ENABLE_EMAIL", False, type_cast=str_to_bool)
ENABLE_HEALTHCHECKS = get_from_env("ENABLE_HEALTHCHECKS", True, type_cast=str_to_bool)
ENABLE_METRICS = get_from_env("ENABLE_METRICS", False, type_cast=str_to_bool)
ENABLE_SILK = get_from_env("ENABLE_SILK", False, type_cast=str_to_bool)
ENABLE_TRACING = get_from_env("ENABLE_TRACING", False, type_cast=str_to_bool)


# --- Installed Apps ---
INSTALLED_APPS = [
    # Default
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Internal Apps
    "apps.core",
    "apps.school",
    "apps.backoffice",
    # Third Party
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_crontab",
    "drf_spectacular",
    "django_filters",
    "storages",
    "django_structlog",
    "channels",
    # Health Checks
    "health_check",
]


# --- Middleware ---
MIDDLEWARE = [
    # Default
    "corsheaders.middleware.CorsMiddleware",
    "shared.middleware.StripTrailingSlashMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # "shared.middleware.RBACMiddleware",
    # Custom
    "crum.CurrentRequestUserMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
    "config.metrics.OpenTelemetryCustomMiddleware",
]


# --- Templates ---
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# --- Static & Media Files ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# --- Logging & Structlog ---
DJANGO_STRUCTLOG_STATUS_4XX_LOG_LEVEL = logging.INFO
DJANGO_STRUCTLOG_USER_ID_FIELD = "id"
# OTEL
OTEL_GRPC_ENDPOINT = os.environ.get("OTEL_GRPC_ENDPOINT", "localhost:4317")


# Importing other settings modules at the bottom to avoid circular imports
try:
    from settings.databases import *  # noqa
    from settings.object_storage import *  # noqa
    from settings.auth import *  # noqa
    from settings.integrations import *  # noqa
    from settings.crons import *  # noqa
except ImportError:
    raise ImportError(  # noqa: B904
        "Failed to import settings modules. Please ensure all dependencies are installed."
    )  # noqa: B904

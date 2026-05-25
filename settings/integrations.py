from shared.utils import get_from_env, str_to_bool

EMAIL_BACKEND = get_from_env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = get_from_env("EMAIL_HOST", "127.0.0.1")
EMAIL_PORT = get_from_env("EMAIL_PORT", 25, type_cast=int)
EMAIL_HOST_USER = get_from_env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = get_from_env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = get_from_env("EMAIL_USE_TLS", False, type_cast=str_to_bool)
EMAIL_USE_SSL = get_from_env("EMAIL_USE_SSL", False, type_cast=str_to_bool)
EMAIL_TIMEOUT = get_from_env("EMAIL_TIMEOUT", 10, type_cast=int)
DEFAULT_FROM_EMAIL = get_from_env(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "noreply@schoolfirst.local",
)
SERVER_EMAIL = get_from_env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

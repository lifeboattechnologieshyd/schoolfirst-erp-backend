from shared.utils import get_from_env

DATABASE_ROUTERS = ["config.db_router.AppRouter"]

APP_TO_DB_MAPPING = {}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": get_from_env("POSTGRES_DB_NAME", "schoolfirst"),
        "USER": get_from_env("POSTGRES_DB_USER", "postgres"),
        "PASSWORD": get_from_env("POSTGRES_DB_PASSWORD", "postgres"),
        "HOST": get_from_env("POSTGRES_DB_HOST", "localhost"),
        "PORT": get_from_env("POSTGRES_DB_PORT", "5432", type_cast=int),
        "OPTIONS": (
            {}
            if get_from_env("POSTGRES_DB_SSL_ENABLED", False)
            else {"sslmode": "verify-full", "sslrootcert": "./postgresql_ssl_cert.pem"}
        ),
        "CONN_MAX_AGE": 4 * 60 * 60,
    },
}

from shared.utils import get_from_env

DATABASE_ROUTERS = ["config.db_router.AppRouter"]

APP_TO_DB_MAPPING = {}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": get_from_env("POSTGRES_DB_NAME"),
        "USER": get_from_env("POSTGRES_DB_USER"),
        "PASSWORD": get_from_env("POSTGRES_DB_PASSWORD"),
        "HOST": get_from_env("POSTGRES_DB_HOST"),
        "PORT": get_from_env("POSTGRES_DB_PORT", type_cast=int),
        "OPTIONS": (
            {}
            if get_from_env("POSTGRES_DB_SSL_ENABLED", False)
            else {"sslmode": "verify-full", "sslrootcert": "./postgresql_ssl_cert.pem"}
        ),
        "CONN_MAX_AGE": 4 * 60 * 60,
    },
}

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": "schoolfirst",
#         "USER": "postgres",
#         "PASSWORD": "postgres",
#         "HOST": "postgres",
#         "PORT": "5432",
#     }
# }

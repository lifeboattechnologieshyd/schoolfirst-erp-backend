from datetime import timedelta

from corsheaders.defaults import default_headers

from shared.utils import get_from_env

########################################
#        REST Framework & JWT          #
########################################
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.FileUploadParser",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "EXCEPTION_HANDLER": "shared.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    # Define the rate for throttle scopes
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/minute",  # Default for anonymous users
        "user": "10000/hour",  # Default for authenticated users
        "chat_message": "120/hour",  # Assistant chat endpoint per user
        "login": "100/15min",  # Login attempts per IP
        "invite_validate": "200/hour",  # Invite code validation per IP
        "membership_application": "30/day",  # Membership applications per email
    },
}


#################################
#       JWT AUTH SETTINGS       #
#################################
SIMPLE_JWT = {
    "BLACKLIST_DB_ALIAS": "default",
    "BLACKLIST_AFTER_ROTATION": True,
    "ROTATE_REFRESH_TOKENS": True,
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=float(get_from_env("ACCESS_TOKEN_LIFETIME_IN_DAYS", 15))),
    "REFRESH_TOKEN_LIFETIME": timedelta(minutes=float(get_from_env("REFRESH_TOKEN_LIFETIME_IN_DAYS", 30))),
}


#############################################
#          CORS & Allowed Hosts             #
#############################################
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    *default_headers,
    "x-request-id",
    "x-correlation-id",
    "traceparent",
    "baggage",
    "Access-Control-Allow-Credentials",
]
CORS_EXPOSE_HEADERS = [
    "x-request-id",
    "x-correlation-id",
    "traceparent",
    "baggage",
    "Access-Control-Allow-Credentials",
]


AUTH_USER_MODEL = "core.UserMaster"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

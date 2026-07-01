import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import pytz
import structlog
from django.dispatch import receiver
from django.utils import timezone
from django_structlog import signals
from opentelemetry.trace import format_span_id, format_trace_id, get_current_span

#####################################
#         LOGGING SETTINGS          #
#####################################
BASE_DIR = Path(__file__).resolve().parent.parent
LOGGING_DIR = os.path.join(BASE_DIR, "logs")

if not os.path.exists(LOGGING_DIR):
    os.makedirs(LOGGING_DIR)

# Setup logging
DEFAULT_LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "DEBUG")


def add_extra_context_to_logs(
    logger: logging.Logger, method_name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    # Add ist time
    event_dict["ist_time"] = timezone.now().astimezone(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
    # Add PID
    event_dict["pid"] = os.getpid()

    # Add Trace Context from OpenTelemetry
    span = get_current_span()
    context = span.get_span_context()
    if context.trace_id != 0:
        event_dict["trace_id"] = format_trace_id(context.trace_id)
        event_dict["span_id"] = format_span_id(context.span_id)
        event_dict["service_name"] = os.environ.get("SERVICE_NAME", "SCHOOLFIRST-ERP-BACKEND")
        event_dict["service_version"] = os.environ.get("SERVICE_VERSION", "1.0.0")
    else:
        event_dict["trace_id"] = None
        event_dict["span_id"] = None
        event_dict["service_name"] = None
        event_dict["service_version"] = None

    # Add request path normalization
    if "request_path" in event_dict:
        event_dict["request_path"] = normalize_request_path(event_dict["request_path"])

    return event_dict


# To enable standard library logs to be formatted via structlog, we add this
# `foreign_pre_chain` to both formatters.
foreign_pre_chain = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    add_extra_context_to_logs,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
]

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        *foreign_pre_chain,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    context_class=structlog.threadlocal.wrap_dict(dict),
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


# Configure all logs to be handled by structlog `ProcessorFormatter` and
# rendered either as pretty colored console lines or as single JSON lines.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "default": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(colors=True),
            "foreign_pre_chain": foreign_pre_chain,
        },
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
            "foreign_pre_chain": foreign_pre_chain,
        },
    },
    "handlers": {

        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },

        "null": {
            "class": "logging.NullHandler",
        },

        "application_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(LOGGING_DIR,"application.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "json",
        },

        "auth_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(LOGGING_DIR,"auth.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "json",
        },

        "payment_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(LOGGING_DIR,"payment.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "json",
        },

        "audit_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(LOGGING_DIR,"audit.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "json",
        },

        "scheduler_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(LOGGING_DIR,"scheduler.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "json",
        },

        "request_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(LOGGING_DIR,"request.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "json",
        },

        "django_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": os.path.join(LOGGING_DIR,"django.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "json",
        },

    },
        "loggers": {

            "default": {
                "handlers": ["application_file","console"],
                "level": DEFAULT_LOG_LEVEL,
                "propagate": False,
            },

            "application": {
                "handlers": ["application_file","console"],
                "level": DEFAULT_LOG_LEVEL,
                "propagate": False,
            },

            "auth": {
                "handlers": ["auth_file","console"],
                "level": DEFAULT_LOG_LEVEL,
                "propagate": False,
            },

            "payment": {
                "handlers": ["payment_file","console"],
                "level": DEFAULT_LOG_LEVEL,
                "propagate": False,
            },

            "audit": {
                "handlers": ["audit_file","console"],
                "level": DEFAULT_LOG_LEVEL,
                "propagate": False,
            },

            "scheduler": {
                "handlers": ["scheduler_file","console"],
                "level": DEFAULT_LOG_LEVEL,
                "propagate": False,
            },

            "request": {
                "handlers": ["request_file","console"],
                "level": DEFAULT_LOG_LEVEL,
                "propagate": False,
            },

            "django": {
                "handlers": ["django_file","console"],
                "level": "INFO",
                "propagate": False,
            },

            "django.request": {
                "handlers": ["django_file","console"],
                "level": "WARNING",
                "propagate": False,
            },

            "django_structlog.middlewares.request": {
                "handlers": ["null"],
                "level": "ERROR",
                "propagate": False,
            },

},
}


######################################
#       LOGGING CONTEXT MANAGER      #
######################################
@contextmanager
def log_context_manager(**kwargs):
    """
    Context manager to apply logging context using structlog.
    """
    structlog.contextvars.bind_contextvars(**kwargs)
    try:
        yield
    finally:
        structlog.contextvars.clear_contextvars()


######################################
#        LOGGING MIDDLEWARE          #
######################################


@receiver(signals.bind_extra_request_metadata)
def bind_extra_request_metadata(request, logger, log_kwargs, **kwargs):
    try:
        from rest_framework_simplejwt.tokens import UntypedToken  # noqa: PLC0415

        header = request.META.get("HTTP_AUTHORIZATION")
        user_id = None
        if header:
            raw_token = header.split()[1]
            token = UntypedToken(raw_token)
            user_id = token["user_id"]
        # Bind context variables
        structlog.contextvars.bind_contextvars(
            request_path=normalize_request_path(request.path),
            request_method=request.method,
            user_id=user_id,
        )
    except Exception:  # noqa: S110
        pass


@receiver(signals.bind_extra_request_finished_metadata)
def bind_extra_request_finished_metadata(request, response, logger, log_kwargs, **kwargs):
    # Bind context variables
    structlog.contextvars.bind_contextvars(
        request_path=normalize_request_path(request.path),
        request_method=request.method,
        response_status_code=response.status_code,
        duration_ms=getattr(request, "duration_ms", None),
    )




@receiver(signals.bind_extra_request_failed_metadata)
def bind_extra_request_failed_metadata(request, logger, exception, log_kwargs, **kwargs):
    # Bind context variables
    structlog.contextvars.bind_contextvars(
        request_path=normalize_request_path(request.path),
        request_method=request.method,
    )


@receiver(signals.update_failure_response)
def update_failure_response(request, response, logger, exception, **kwargs):
    # Bind context variables
    structlog.contextvars.bind_contextvars(
        request_path=normalize_request_path(request.path),
        request_method=request.method,
        response_status_code=response.status_code,
    )


#######################################
#         PATH NORMALIZATION          #
#######################################


# Regex patterns
UUID_REGEX = re.compile(
    r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-"
    r"[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-"
    r"[a-fA-F0-9]{12}$"
)
INTEGER_REGEX = re.compile(r"^\d+$")


def normalize_request_path(request_path: str) -> str:
    """
    Normalize a request path by:
        - Removing query parameters
        - Replacing integers with :int
        - Replacing UUIDs with :uuid

    Args:
        request_path (str): The full request URL or path.

    Returns:
        str: The normalized path.
    """
    try:
        parsed = urlparse(request_path)
        path = parsed.path

        # Normalize each segment
        segments = []
        for segment in path.strip("/").split("/"):
            if UUID_REGEX.match(segment):
                segments.append(":uuid")
            elif INTEGER_REGEX.match(segment):
                segments.append(":int")
            else:
                segments.append(segment)

        normalized = "/" + "/".join(segments)
        return normalized
    except Exception:
        return request_path

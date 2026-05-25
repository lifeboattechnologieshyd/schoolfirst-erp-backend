import os

from django.core.wsgi import get_wsgi_application
from dotenv import load_dotenv

from config.metrics import init_metrics
from config.tracing import init_tracer

load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.development")

try:
    ENABLE_TRACING = os.environ.get("ENABLE_TRACING", "False")
    if ENABLE_TRACING == "True":
        init_tracer()
    ENABLE_METRICS = os.environ.get("ENABLE_METRICS", "False")
    if ENABLE_METRICS == "True":
        init_metrics()
except:  # noqa: E722
    import logging

    logging.exception("Failed to initialize tracing/metrics")


application = get_wsgi_application()

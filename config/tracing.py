# Python imports
import atexit

from django.conf import settings

# Third party imports
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,  # , ConsoleSpanExporter, SimpleSpanProcessor
)

from .logs import normalize_request_path

# Global variable to track initialization
_TRACER_PROVIDER = None
_INSTRUMENTED = None


def init_tracer():
    """Initialize OpenTelemetry with proper shutdown handling"""
    global _TRACER_PROVIDER  # noqa: PLW0603
    global _INSTRUMENTED  # noqa: PLW0603

    # If already initialized, return existing provider
    if _TRACER_PROVIDER is not None:
        return _TRACER_PROVIDER

    # Configure the tracer provider
    service_name = settings.SERVICE_NAME
    service_version = settings.SERVICE_VERSION
    resource = Resource.create({"service.name": service_name, "service.version": service_version})
    tracer_provider = TracerProvider(resource=resource)

    # Set as global tracer provider
    trace.set_tracer_provider(tracer_provider)

    # Configure the OTLP exporter
    otel_endpoint = settings.OTEL_GRPC_ENDPOINT
    otlp_exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True, timeout=5)
    span_processor = BatchSpanProcessor(otlp_exporter, export_timeout_millis=5000)
    tracer_provider.add_span_processor(span_processor)

    # ✅ Console Exporter (for debugging)
    # console_exporter = ConsoleSpanExporter()
    # console_processor = SimpleSpanProcessor(console_exporter)
    # tracer_provider.add_span_processor(console_processor)

    # Initialize instrumentations
    if not _INSTRUMENTED:
        # Initialize Django instrumentation
        DjangoInstrumentor().instrument(
            request_hook=_otel_django_request_hook,
            response_hook=_otel_django_response_hook,
        )
        # Initialize Requests instrumentation
        RequestsInstrumentor().instrument()
        # Initialize Psycopg instrumentation
        PsycopgInstrumentor().instrument()
        # Initialize Logging instrumentation
        LoggingInstrumentor().instrument()
        # Mark as instrumented
        _INSTRUMENTED = True

    # Store provider globally
    _TRACER_PROVIDER = tracer_provider

    # Register shutdown handler
    atexit.register(shutdown_tracer)

    return tracer_provider


def shutdown_tracer():
    """Shutdown OpenTelemetry tracers and processors"""
    global _TRACER_PROVIDER  # noqa: PLW0603

    if _TRACER_PROVIDER is not None:
        if hasattr(_TRACER_PROVIDER, "shutdown"):
            _TRACER_PROVIDER.shutdown()
        _TRACER_PROVIDER = None


def _otel_django_request_hook(span, request):
    if span and span.is_recording():
        pass


def _otel_django_response_hook(span, request, response):
    if span and span.is_recording():
        request_path = normalize_request_path(request.path)
        span.set_attribute("http.status_code", response.status_code)
        span.set_attribute("http.route", request_path)
        span.set_attribute("http.path", request_path)

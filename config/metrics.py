import atexit
from dataclasses import dataclass
from timeit import default_timer
from typing import TypedDict

import structlog
from django.conf import settings
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource

from .logs import normalize_request_path

logger = structlog.getLogger("default")


class MetricsInstruments(TypedDict):
    http_requests_total_count: metrics.Counter
    http_request_duration_seconds_histogram: metrics.Histogram
    job_runs_total_count: metrics.Counter
    job_duration_seconds_histogram: metrics.Histogram


@dataclass(slots=True)
class MetricsState:
    meter_provider: MeterProvider | None = None
    meter: metrics.Meter | None = None
    instruments: MetricsInstruments | None = None
    initialized: bool = False


_STATE = MetricsState()


def init_metrics() -> tuple[metrics.Meter, MetricsInstruments]:
    """Initialize OpenTelemetry metrics with proper shutdown handling."""
    if _STATE.initialized and _STATE.meter is not None and _STATE.instruments is not None:
        return _STATE.meter, _STATE.instruments

    otel_endpoint = settings.OTEL_GRPC_ENDPOINT
    otlp_exporter = OTLPMetricExporter(endpoint=otel_endpoint, insecure=True)

    metric_reader = PeriodicExportingMetricReader(otlp_exporter, export_interval_millis=5000)

    # Histogram views
    http_request_duration_seconds_histogram_view = View(
        instrument_name="http_request_duration_seconds",
        aggregation=ExplicitBucketHistogramAggregation(
            boundaries=[
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.2,
                0.5,
                1,
                2,
                5,
                10,
                30,
                60,
                120,
                240,
                float("inf"),
            ]
        ),
    )

    job_duration_seconds_histogram_view = View(
        instrument_name="job_duration_seconds",
        aggregation=ExplicitBucketHistogramAggregation(
            boundaries=[
                10,
                30,
                60,
                120,
                300,
                600,
                900,
                1200,
                1800,
                2700,
                3600,
                5400,
                7200,
                float("inf"),
            ]
        ),
    )

    resource = Resource.create(
        {
            "service.name": settings.SERVICE_NAME,
            "service.version": settings.SERVICE_VERSION,
            "namespace": settings.NAMESPACE,
        }
    )

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
        views=[
            http_request_duration_seconds_histogram_view,
            job_duration_seconds_histogram_view,
        ],
    )
    metrics.set_meter_provider(meter_provider)

    meter = metrics.get_meter(__name__)

    # Define instruments
    instruments: MetricsInstruments = {
        "http_requests_total_count": meter.create_counter("http_requests_total", description="Total HTTP requests"),
        "http_request_duration_seconds_histogram": meter.create_histogram(
            "http_request_duration_seconds",
            description="HTTP request latency in seconds",
        ),
        "job_runs_total_count": meter.create_counter("job_runs_total", description="Total number of job runs"),
        "job_duration_seconds_histogram": meter.create_histogram(
            "job_duration_seconds", description="Duration of job runs"
        ),
    }

    _STATE.meter_provider = meter_provider
    _STATE.meter = meter
    _STATE.instruments = instruments
    _STATE.initialized = True

    # Register shutdown handler
    atexit.register(shutdown_metrics)

    return meter, instruments


def shutdown_metrics():
    """Shutdown OpenTelemetry metrics provider."""
    meter_provider = _STATE.meter_provider
    if meter_provider is not None and hasattr(meter_provider, "shutdown"):
        meter_provider.shutdown()

    _STATE.meter_provider = None
    _STATE.meter = None
    _STATE.instruments = None
    _STATE.initialized = False


class OpenTelemetryCustomMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Lazy init to avoid startup cost when metrics are disabled
        _, self._instruments = init_metrics()

    def __call__(self, request):
        start = default_timer()
        response = self.get_response(request)
        duration = default_timer() - start

        path = normalize_request_path(request.path)
        status = response.status_code
        if "metrics" in path or "api/v1/reports_hub/" in path or "health" in path or status in (401, 404):
            return response

        if settings.ENABLE_METRICS and self._instruments:
            attrs = {
                "request_path": path,
                "method": request.method,
                "status_code": str(status),
            }
            try:
                self._instruments["http_requests_total_count"].add(1, attributes=attrs)
                self._instruments["http_request_duration_seconds_histogram"].record(duration, attributes=attrs)
            except Exception:
                logger.exception("Error while recording OTel HTTP request metrics")

        return response


def current_time() -> float:
    return default_timer()


def time_since(start: float) -> float:
    return default_timer() - start

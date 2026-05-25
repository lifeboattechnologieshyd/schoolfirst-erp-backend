import typing

from health_check.base import HealthCheck
from health_check.views import HealthCheckView


class CustomHealthCheckView(HealthCheckView):
    """
    Custom health check view that excludes DNS and Mail checks.
    """

    checks: typing.Iterable[type[HealthCheck] | str | tuple[type[HealthCheck] | str, dict[str, typing.Any]]] = (
        "health_check.checks.Cache",
        "health_check.checks.Database",
        "health_check.checks.Storage",
    )

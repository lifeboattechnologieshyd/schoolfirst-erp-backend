import typing

from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
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


def simple_health_check(request):
    return HttpResponse(b"OK", content_type="text/plain")


urlpatterns = []


####################################
#          HEALTH CHECKS           #
####################################
if settings.ENABLE_HEALTHCHECKS:
    urlpatterns += [
        path("health", CustomHealthCheckView.as_view()),
        path("health/simple", simple_health_check),

    ]

####################################
#       API DOCUMENTATION          #
####################################
if settings.ENABLE_DOCS:
    urlpatterns += [
        path("api/v1/schema", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/v1/schema/swagger-ui",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "api/v1/schema/redoc",
            SpectacularRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]


####################################
#          SILK PROFILING          #
####################################
if settings.ENABLE_SILK:
    urlpatterns.append(path("silk/", include("silk.urls", namespace="silk")))


####################################
#     Conditional App URLs Load    #
####################################

if "apps.core" in settings.INSTALLED_APPS:
    urlpatterns.append(path("user/", include("apps.core.urls")))
if "apps.school" in settings.INSTALLED_APPS:
    urlpatterns.append(path("school/", include("apps.school.urls")))
if "apps.backoffice" in settings.INSTALLED_APPS:
    urlpatterns.append(path("backoffice/", include("apps.backoffice.urls")))
if "apps.fee" in settings.INSTALLED_APPS:
    urlpatterns.append(path("fee/", include("apps.fee.urls")))
if "apps.payment" in settings.INSTALLED_APPS:
    urlpatterns.append(path("payment/", include("apps.payment.urls")))
if "apps.ptm" in settings.INSTALLED_APPS:
    urlpatterns.append(path("ptm/", include("apps.ptm.urls")))
if "apps.calendar" in settings.INSTALLED_APPS:
    urlpatterns.append(path("calendar/", include("apps.calendar.urls")))
if "apps.homework" in settings.INSTALLED_APPS:
    urlpatterns.append(path("homework/", include("apps.homework.urls")))
if "apps.transport" in settings.INSTALLED_APPS:
    urlpatterns.append(path("transport/", include("apps.transport.urls")))


####################################
#       MEDIA FILES (DEV)          #
####################################
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

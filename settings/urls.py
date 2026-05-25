from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.views.health import CustomHealthCheckView


def simple_health_check(request):
    return HttpResponse("OK")


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
    urlpatterns.append(path("api/", include("apps.core.urls")))

if "apps.assistant" in settings.INSTALLED_APPS:
    urlpatterns.append(path("api/", include("apps.assistant.urls")))

if "apps.docusafe" in settings.INSTALLED_APPS:
    urlpatterns.append(path("api/", include("apps.docusafe.urls")))

if "apps.feed" in settings.INSTALLED_APPS:
    urlpatterns.append(path("api/", include("apps.feed.urls")))

if "apps.calendar" in settings.INSTALLED_APPS:
    urlpatterns.append(path("api/", include("apps.calendar.urls")))


####################################
#       MEDIA FILES (DEV)          #
####################################
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

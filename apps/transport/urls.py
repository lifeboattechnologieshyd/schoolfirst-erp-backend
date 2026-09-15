from django.urls import path

from apps.transport.views.transport import StudentBusAPIView, StudentRouteAPIView

urlpatterns = [

    path("bus",StudentBusAPIView.as_view()),

    path("route",StudentRouteAPIView.as_view()),
]
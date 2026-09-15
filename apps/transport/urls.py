from django.urls import path

from apps.transport.views.transport import StudentBusAPIView, StudentRouteAPIView, StudentLiveLocationAPIView

urlpatterns = [

    path("bus",StudentBusAPIView.as_view()),

    path("route",StudentRouteAPIView.as_view()),

    path("live-location",StudentLiveLocationAPIView.as_view()),
]
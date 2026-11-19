from django.urls import path

from apps.feels.views.views import FeelShareAPIView, FeelLikeAPIView, FeelsLISTAPIView, FeelUnlikeAPIView

urlpatterns = [
    path("feels",FeelsLISTAPIView.as_view(),),

    path("feels/<uuid:feel_id>/share",FeelShareAPIView.as_view(),),

    path("feels/<uuid:feel_id>/like",FeelLikeAPIView.as_view(),),

    path("feels/<uuid:feel_id>/unlike",FeelUnlikeAPIView.as_view(),),
]
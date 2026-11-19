from django.urls import path

from apps.feels.views.views import FeelShareAPIView, FeelLikeAPIView, FeelsLISTAPIView, FeelUnlikeAPIView, \
    FeelViewAPIView

urlpatterns = [
    path("feels",FeelsLISTAPIView.as_view(),),

    path("feels/<uuid:feel_id>/share",FeelShareAPIView.as_view(),),

    path("feels/<uuid:feel_id>/like",FeelLikeAPIView.as_view(),),

    path("feels/<uuid:feel_id>/unlike",FeelUnlikeAPIView.as_view(),),

    path("feels/<uuid:feel_id>/view",FeelViewAPIView.as_view(),),
]
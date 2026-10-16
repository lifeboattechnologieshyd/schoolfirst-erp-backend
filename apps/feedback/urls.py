from django.urls import path

from apps.feedback.views.feedback import CreateFeedbackAPIView, MyFeedbackAPIView, FeedbackCategoryLISTAPIView

urlpatterns = [

    path("create/feedback",CreateFeedbackAPIView.as_view(),),

    path("feedbacks",MyFeedbackAPIView.as_view(),),

    path("categories",FeedbackCategoryLISTAPIView.as_view(),),
]
from django.urls import path

from apps.remarks.views.remarks import StudentRemarkLISTAPIView, RemarkCategoryLISTAPIView

urlpatterns = [
    path("categories",RemarkCategoryLISTAPIView.as_view()),
    path("remarks",StudentRemarkLISTAPIView.as_view()),
]
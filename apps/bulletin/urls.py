from django.urls import path

from apps.backoffice.views.bulletin import BulletinListAPIView
from apps.bulletin.views.bulletin import BulletinLISTAPIView, BulletinReadAPIView, BulletinCategoryLISTAPIView

urlpatterns = [
    path('categories', BulletinCategoryLISTAPIView.as_view()),
    path('bulletins', BulletinLISTAPIView.as_view()),
    path("read", BulletinReadAPIView.as_view()),
]
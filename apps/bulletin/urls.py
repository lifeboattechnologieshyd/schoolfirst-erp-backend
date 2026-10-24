from django.urls import path

from apps.bulletin.views.bulletin import BulletinLISTAPIView, BulletinReadAPIView

urlpatterns = [
    path('bulletins', BulletinLISTAPIView.as_view()),
    path("read", BulletinReadAPIView.as_view()),
]
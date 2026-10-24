from django.urls import path

from apps.bulletin.views.bulletin import BulletinLISTAPIView

urlpatterns = [
    path('bulletins', BulletinLISTAPIView.as_view()),
]
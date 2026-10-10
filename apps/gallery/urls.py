from django.urls import path

from apps.gallery.views.gallery import GalleryCategoryListAPIView, GalleryLISTAPIView

urlpatterns = [
    path("categories", GalleryCategoryListAPIView.as_view()),
    path("gallery/list",GalleryLISTAPIView.as_view()),
]
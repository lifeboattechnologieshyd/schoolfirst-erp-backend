from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.gallery.models import GalleryCategory, Gallery
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


class GalleryCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )

            categories = GalleryCategory.objects.filter(
                school=school,
                is_active=True,
            ).order_by("name")

            data = [
                {
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                }
                for category in categories
            ]

            application_logger.info(
                "gallery_categories_fetched",
                school_id=str(school.id),
                count=len(data),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Gallery categories fetched successfully.",
                data=data,
            )

        except Exception:
            application_logger.exception(
                "gallery_categories_fetch_failed",
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch gallery categories."
            )

class GalleryLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )

            category_id = request.query_params.get("category_id")
            search = request.query_params.get("search")

            queryset = (
                Gallery.objects.filter(
                    school=school,
                    is_published=True,
                    category__is_active=True,
                )
                .select_related("category")
                .prefetch_related("images", "videos")
                .annotate(
                    image_count=Count(
                        "images",
                        filter=Q(images__is_deleted=False),
                        distinct=True,
                    ),
                    video_count=Count(
                        "videos",
                        filter=Q(videos__is_deleted=False),
                        distinct=True,
                    ),
                )
            )

            if category_id:
                queryset = queryset.filter(category_id=category_id)

            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                )

            queryset = queryset.order_by(
                "-event_date",
                "-created_at",
            )

            data = []

            for gallery in queryset:
                images = [
                    {
                        "id": str(image.id),
                        "image": image.image.url if image.image else None,
                        "caption": image.caption,
                        "display_order": image.display_order,
                    }
                    for image in gallery.images.all()
                    if not image.is_deleted
                ]

                videos = [
                    {
                        "id": str(video.id),
                        "video": video.video.url if video.video else None,
                        "caption": video.caption,
                        "display_order": video.display_order,
                    }
                    for video in gallery.videos.all()
                    if not video.is_deleted
                ]

                data.append({
                    "id": str(gallery.id),
                    "title": gallery.title,
                    "description": gallery.description,
                    "category": {
                        "id": str(gallery.category_id),
                        "name": gallery.category.name,
                    },
                    "event_date": gallery.event_date,
                    "allow_downloads": gallery.allow_downloads,
                    "image_count": gallery.image_count,
                    "video_count": gallery.video_count,
                    "images": images,
                    "videos": videos,
                })

            application_logger.info(
                "galleries_fetched",
                school_id=str(school.id),
                category_id=category_id,
                count=len(data),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Galleries fetched successfully.",
                data=data,
            )

        except Exception:
            application_logger.exception(
                "galleries_fetch_failed",
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch galleries."
            )
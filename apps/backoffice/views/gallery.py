from django.db import transaction
from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.gallery.models import GalleryCategory, Gallery, GalleryImage
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class GalleryCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "gallery.category.create"


    def get(self, request):
        school = request.school
        search = request.query_params.get("search")

        application_logger.info(
            "gallery_categories_requested",
            school_id=str(school.id) if school else None,
            user_id=str(request.user.id),
            search=search,
        )

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )


            queryset = GalleryCategory.objects.filter(school=school)

            if search:
                queryset = queryset.filter(name__icontains=search)

            data = [
                {
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                }
                for category in queryset.order_by("name")
            ]

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

    def post(self, request):
        school = request.school

        name = request.data.get("name")
        description = request.data.get("description")

        application_logger.info(
            "gallery_category_create_requested",
            school_id=str(school.id) if school else None,
            user_id=str(request.user.id),
        )

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )


            if not name or not name.strip():
                return CustomResponse.errorResponse(
                    description="Category name is required."
                )

            name = name.strip()

            if GalleryCategory.objects.filter(
                school=school,
                name__iexact=name,
            ).exists():
                return CustomResponse.errorResponse(
                    description="Category already exists."
                )

            category = GalleryCategory.objects.create(
                school=school,
                name=name,
                description=description or None,
            )

            application_logger.info(
                "gallery_category_created",
                school_id=str(school.id),
                category_id=str(category.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Gallery category created successfully.",
                data={
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                },
            )

        except Exception:
            application_logger.exception(
                "gallery_category_create_failed",
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to create gallery category."
            )

    def put(self, request, category_id):
        school = request.school

        application_logger.info(
            "gallery_category_update_requested",
            school_id=str(school.id) if school else None,
            category_id=str(category_id),
            user_id=str(request.user.id),
        )

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )

            category = GalleryCategory.objects.filter(
                id=category_id,
                school=school,
            ).first()

            if category is None:
                return CustomResponse.errorResponse(
                    description="Gallery category not found."
                )

            # Update category name
            if "name" in request.data:
                name = request.data.get("name")

                if not name or not name.strip():
                    return CustomResponse.errorResponse(
                        description="Category name cannot be empty."
                    )

                name = name.strip()

                if GalleryCategory.objects.filter(
                        school=school,
                        name__iexact=name,
                ).exclude(id=category.id).exists():
                    return CustomResponse.errorResponse(
                        description="Category already exists."
                    )

                category.name = name

            # Update description
            if "description" in request.data:
                category.description = (
                        request.data.get("description") or None
                )

            # Update active status
            if "is_active" in request.data:
                is_active = request.data.get("is_active")

                if isinstance(is_active, bool):
                    category.is_active = is_active
                elif str(is_active).lower() in ("true", "false"):
                    category.is_active = str(is_active).lower() == "true"
                else:
                    return CustomResponse.errorResponse(
                        description="is_active must be true or false."
                    )

            category.save()

            application_logger.info(
                "gallery_category_updated",
                school_id=str(school.id),
                category_id=str(category.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Gallery category updated successfully.",
                data={
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                },
            )

        except Exception:
            application_logger.exception(
                "gallery_category_update_failed",
                school_id=str(school.id) if school else None,
                category_id=str(category_id),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update gallery category."
            )



class GalleryCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "gallery.create"

    def post(self, request):
        school = request.school

        application_logger.info(
            "gallery_create_requested",
            school_id=str(school.id) if school else None,
            user_id=str(request.user.id),
        )

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )

            title = request.data.get("title")
            category_id = request.data.get("category_id")
            description = request.data.get("description")
            event_date = request.data.get("event_date") or None
            allow_downloads = request.data.get("allow_downloads", True)
            is_published = request.data.get("is_published", False)
            images = request.FILES.getlist("images")

            if not title or not title.strip():
                return CustomResponse.errorResponse(
                    description="Gallery title is required."
                )

            if not category_id:
                return CustomResponse.errorResponse(
                    description="Category ID is required."
                )

            category = GalleryCategory.objects.filter(
                id=category_id,
                school=school,
                is_active=True,
            ).first()

            if category is None:
                return CustomResponse.errorResponse(
                    description="Invalid gallery category."
                )

            with transaction.atomic():
                gallery = Gallery.objects.create(
                    school=school,
                    category=category,
                    title=title.strip(),
                    description=description or None,
                    event_date=event_date,
                    allow_downloads=allow_downloads,
                    is_published=is_published,
                )

                for image in images:
                    GalleryImage.objects.create(
                        gallery=gallery,
                        image=image,
                    )

            application_logger.info(
                "gallery_created",
                gallery_id=str(gallery.id),
                school_id=str(school.id),
                image_count=len(images),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Gallery created successfully.",
                data={
                    "id": str(gallery.id),
                    "title": gallery.title,
                    "description": gallery.description,
                    "category_id": str(gallery.category_id),
                    "category_name": category.name,
                    "event_date": gallery.event_date,
                    "allow_downloads": gallery.allow_downloads,
                    "is_published": gallery.is_published,
                    "image_count": len(images),
                },
            )

        except Exception:
            application_logger.exception(
                "gallery_create_failed",
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )
            return CustomResponse.errorResponse(
                description="Failed to create gallery."
            )

class GalleryListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "gallery.view"

    def get(self, request):
        school = request.school

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )

            category_id = request.query_params.get("category_id")
            search = request.query_params.get("search")
            is_published = request.query_params.get("is_published")

            queryset = (
                Gallery.objects.filter(school=school)
                .select_related("category")
                .annotate(image_count=Count("images", distinct=True))
            )

            if category_id:
                queryset = queryset.filter(category_id=category_id)

            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                )

            if is_published is not None:
                if is_published.lower() not in ("true", "false"):
                    return CustomResponse.errorResponse(
                        description="is_published must be true or false."
                    )

                queryset = queryset.filter(
                    is_published=is_published.lower() == "true"
                )

            queryset = queryset.order_by("-event_date", "-created_at")

            data = [
                {
                    "id": str(gallery.id),
                    "title": gallery.title,
                    "description": gallery.description,
                    "category": {
                        "id": str(gallery.category_id),
                        "name": gallery.category.name,
                    },
                    "event_date": gallery.event_date,
                    "allow_downloads": gallery.allow_downloads,
                    "is_published": gallery.is_published,
                    "image_count": gallery.image_count,
                }
                for gallery in queryset
            ]

            application_logger.info(
                "gallery_list_fetched",
                school_id=str(school.id),
                returned_count=len(data),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Galleries fetched successfully.",
                data=data,
            )

        except Exception:
            application_logger.exception(
                "gallery_list_failed",
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )
            return CustomResponse.errorResponse(
                description="Failed to fetch galleries."
            )

class GalleryDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "gallery.view"

    def get(self, request, gallery_id):
        school = request.school

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )

            gallery = (
                Gallery.objects.filter(
                    id=gallery_id,
                    school=school,
                )
                .select_related("category")
                .prefetch_related("images")
                .first()
            )

            if gallery is None:
                return CustomResponse.errorResponse(
                    description="Gallery not found."
                )

            images = [
                {
                    "id": str(image.id),
                    "image": image.image.url if image.image else None,
                    "caption": image.caption,
                    "display_order": image.display_order,
                }
                for image in gallery.images.all()
            ]

            return CustomResponse.successResponse(
                description="Gallery fetched successfully.",
                data={
                    "id": str(gallery.id),
                    "title": gallery.title,
                    "description": gallery.description,
                    "category": {
                        "id": str(gallery.category_id),
                        "name": gallery.category.name,
                    },
                    "event_date": gallery.event_date,
                    "allow_downloads": gallery.allow_downloads,
                    "is_published": gallery.is_published,
                    "images": images,
                },
            )

        except Exception:
            application_logger.exception(
                "gallery_detail_failed",
                gallery_id=str(gallery_id),
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )
            return CustomResponse.errorResponse(
                description="Failed to fetch gallery."
            )

class GalleryUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "gallery.update"

    def patch(self, request, gallery_id):
        school = request.school

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )

            gallery = Gallery.objects.filter(
                id=gallery_id,
                school=school,
            ).first()

            if gallery is None:
                return CustomResponse.errorResponse(
                    description="Gallery not found."
                )

            if "title" in request.data:
                title = request.data.get("title")

                if not title or not title.strip():
                    return CustomResponse.errorResponse(
                        description="Gallery title cannot be empty."
                    )

                gallery.title = title.strip()

            if "description" in request.data:
                gallery.description = request.data.get("description") or None

            if "event_date" in request.data:
                gallery.event_date = request.data.get("event_date") or None

            if "category_id" in request.data:
                category = GalleryCategory.objects.filter(
                    id=request.data.get("category_id"),
                    school=school,
                    is_active=True,
                ).first()

                if category is None:
                    return CustomResponse.errorResponse(
                        description="Invalid gallery category."
                    )

                gallery.category = category

            if "allow_downloads" in request.data:
                gallery.allow_downloads = request.data.get("allow_downloads")

            if "is_published" in request.data:
                gallery.is_published = request.data.get("is_published")

            with transaction.atomic():
                gallery.save()

                images = request.FILES.getlist("images")

                for image in images:
                    GalleryImage.objects.create(
                        gallery=gallery,
                        image=image,
                    )

            application_logger.info(
                "gallery_updated",
                gallery_id=str(gallery.id),
                school_id=str(school.id),
                added_image_count=len(images),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Gallery updated successfully.",
                data={"id": str(gallery.id)},
            )

        except Exception:
            application_logger.exception(
                "gallery_update_failed",
                gallery_id=str(gallery_id),
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )
            return CustomResponse.errorResponse(
                description="Failed to update gallery."
            )


class GalleryDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "gallery.delete"

    def delete(self, request, gallery_id):
        school = request.school

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )

            gallery = Gallery.objects.filter(
                id=gallery_id,
                school=school,
                is_deleted=False,
            ).first()

            if gallery is None:
                return CustomResponse.errorResponse(
                    description="Gallery not found."
                )

            gallery.soft_delete(request.user)

            application_logger.info(
                "gallery_soft_deleted",
                gallery_id=str(gallery.id),
                school_id=str(school.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Gallery deleted successfully."
            )

        except Exception:
            application_logger.exception(
                "gallery_soft_delete_failed",
                gallery_id=str(gallery_id),
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to delete gallery."
            )


class GalleryImageDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "gallery.update"

    def delete(self, request, gallery_id, image_id):
        school = request.school

        try:
            if school is None:
                return CustomResponse.errorResponse(
                    description="School not found."
                )

            image = GalleryImage.objects.filter(
                id=image_id,
                gallery_id=gallery_id,
                gallery__school=school,
                gallery__is_deleted=False,
                is_deleted=False,
            ).first()

            if image is None:
                return CustomResponse.errorResponse(
                    description="Gallery image not found."
                )

            image.soft_delete(request.user)

            application_logger.info(
                "gallery_image_soft_deleted",
                gallery_id=str(gallery_id),
                image_id=str(image.id),
                school_id=str(school.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Gallery image deleted successfully."
            )

        except Exception:
            application_logger.exception(
                "gallery_image_soft_delete_failed",
                gallery_id=str(gallery_id),
                image_id=str(image_id),
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to delete gallery image."
            )
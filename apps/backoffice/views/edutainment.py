
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from apps.edutainment.models import Feed, FeedCategories, DIYMaterials, DIYSteps
from shared.mixins import CustomPageNumberPagination, CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class FeedListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    pagination_class = CustomPageNumberPagination
    required_permission = "feed.view"

    def get(self, request):

        try:
            category = request.query_params.get("category")
            feed_status = request.query_params.get("status")
            feed_type = request.query_params.get("feed_type")
            language = request.query_params.get("language")
            trending = request.query_params.get("trending")
            search = request.query_params.get("search")

            feeds = Feed.objects.all()

            if category:
                feeds = feeds.filter(f_category=category)

            if feed_status:
                feeds = feeds.filter(status=feed_status)

            if feed_type:
                feeds = feeds.filter(feed_type=feed_type)

            if language:
                feeds = feeds.filter(language=language)

            if trending is not None:
                feeds = feeds.filter(
                    trending=trending.lower() == "true"
                )

            if search:
                feeds = feeds.filter(
                    Q(heading__icontains=search) |
                    Q(description__icontains=search) |
                    Q(subject__icontains=search)
                )

            feeds = feeds.order_by("-created_at")

            total = feeds.count()

            paginator = self.pagination_class()
            page = paginator.paginate_queryset(feeds, request)

            data = [
                {
                    "id": str(feed.id),
                    "serial_number": feed.serial_number,
                    "heading": feed.heading,
                    "feed_type": feed.feed_type,
                    "f_category": feed.f_category,
                    "image": feed.image,
                    "video": feed.video,
                    "youtube_video": feed.youtube_video,
                    "audio_url": feed.audio_url,
                    "categories": feed.categories,
                    "grade_id": str(feed.grade_id) if feed.grade_id else None,
                    "subject": feed.subject,
                    "lesson": feed.lesson,
                    "skill_tested": feed.skill_tested,
                    "description": feed.description,
                    "description_2": feed.description_2,
                    "trending": feed.trending,
                    "language": feed.language,
                    "duration": feed.duration,
                    "posting_date": feed.posting_date,
                    "status": feed.status,
                    "likes_count": feed.likes_count,
                    "comments_count": feed.comments_count,
                    "whatsapp_share_count": feed.whatsapp_share_count,
                }
                for feed in page
            ]

            application_logger.info(
                "feed_list_fetched user_id=%s total=%s returned_count=%s",
                request.user.id,
                total,
                len(data),
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Feeds fetched successfully."
            )

        except Exception as e:

            application_logger.exception(
                "feed_list_failed user_id=%s error=%s",
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch feeds."
            )

class FeedCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feed.create"

    @transaction.atomic
    def post(self, request):

        request_data = request.data

        heading = request_data.get("heading")
        posting_date = request_data.get("posting_date")

        if not heading:
            return CustomResponse.errorResponse(
                description="Feed heading is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not posting_date:
            return CustomResponse.errorResponse(
                description="Posting date is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        feed_type = request_data.get(
            "feed_type",
            Feed.FeedType.TEXT,
        )

        category = request_data.get(
            "f_category",
            Feed.FeedCategory.DIY,
        )

        language = request_data.get(
            "language",
            Feed.Language.TELUGU,
        )

        feed_status = request_data.get(
            "status",
            Feed.FeedStatus.DRAFT,
        )

        if feed_type not in Feed.FeedType.values:
            return CustomResponse.errorResponse(
                description="Invalid feed type.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if category not in Feed.FeedCategory.values:
            return CustomResponse.errorResponse(
                description="Invalid feed category.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if language not in Feed.Language.values:
            return CustomResponse.errorResponse(
                description="Invalid language.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if feed_status not in Feed.FeedStatus.values:
            return CustomResponse.errorResponse(
                description="Invalid feed status.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            feed = Feed.objects.create(
                heading=heading,
                feed_type=feed_type,
                f_category=category,
                language=language,
                status=feed_status,
                image=request_data.get("image"),
                video=request_data.get("video"),
                youtube_video=request_data.get("youtube_video"),
                audio_url=request_data.get("audio_url"),
                trending=request_data.get("trending", True),
                categories=request_data.get("categories"),
                grade_id=request_data.get("grade_id") or None,
                subject=request_data.get("subject"),
                lesson=request_data.get("lesson"),
                skill_tested=request_data.get("skill_tested"),
                description=request_data.get("description"),
                description_2=request_data.get("description_2"),
                duration=request_data.get("duration", 0),
                remarks=request_data.get("remarks"),
                posting_date=posting_date,
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            application_logger.info(
                "feed_created feed_id=%s user_id=%s",
                feed.id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(feed.id),
                    "heading": feed.heading,
                    "serial_number": feed.serial_number,
                    "status": feed.status,
                },
                description="Feed created successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "feed_create_failed user_id=%s error=%s",
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to create feed."
            )

class FeedUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feed.update"

    @transaction.atomic
    def put(self, request, feed_id):

        try:

            feed = Feed.objects.filter(id=feed_id).first()

            if not feed:
                return CustomResponse.errorResponse(
                    description="Feed not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            request_data = request.data

            allowed_fields = [
                "heading",
                "image",
                "video",
                "youtube_video",
                "audio_url",
                "trending",
                "categories",
                "grade_id",
                "subject",
                "lesson",
                "skill_tested",
                "description",
                "description_2",
                "duration",
                "remarks",
                "posting_date",
            ]

            enum_fields = {
                "feed_type": Feed.FeedType.values,
                "f_category": Feed.FeedCategory.values,
                "language": Feed.Language.values,
            }

            for field, valid_values in enum_fields.items():

                if field in request_data:
                    if request_data[field] not in valid_values:
                        return CustomResponse.errorResponse(
                            description=f"Invalid {field.replace('_', ' ')}.",
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    setattr(feed, field, request_data[field])

            if "status" in request_data:
                if request_data["status"] not in Feed.FeedStatus.values:
                    return CustomResponse.errorResponse(
                        description="Invalid feed status.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                feed.status = request_data["status"]

            for field in allowed_fields:

                if field in request_data:

                    value = request_data.get(field)

                    if field == "grade_id":
                        value = value or None

                    setattr(feed, field, value)

            if not feed.heading:
                return CustomResponse.errorResponse(
                    description="Feed heading is required.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            feed.save()

            application_logger.info(
                "feed_updated feed_id=%s user_id=%s",
                feed.id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(feed.id),
                    "heading": feed.heading,
                    "status": feed.status,
                },
                description="Feed updated successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "feed_update_failed feed_id=%s user_id=%s error=%s",
                feed_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to update feed."
            )

class FeedDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feed.delete"

    @transaction.atomic
    def delete(self, request, feed_id):

        try:

            feed = Feed.objects.filter(id=feed_id).first()

            if not feed:
                return CustomResponse.errorResponse(
                    description="Feed not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            deleted_feed_id = str(feed.id)

            feed.delete()

            application_logger.info(
                "feed_deleted feed_id=%s user_id=%s",
                deleted_feed_id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "id": deleted_feed_id,
                },
                description="Feed deleted successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "feed_delete_failed feed_id=%s user_id=%s error=%s",
                feed_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to delete feed."
            )


class FeedCategoryListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    pagination_class = CustomPageNumberPagination


    required_permission = "feed_category.view"



    def get(self, request):

        search = request.query_params.get("search", "").strip()
        category_status = request.query_params.get("status", "").strip()

        application_logger.info(
            "feed_category_list_requested",
            requested_by=str(request.user.id),
            search=search,
            status=category_status,
        )

        try:

            categories = FeedCategories.objects.all()

            if search:
                categories = categories.filter(
                    display_name__icontains=search,
                )

            if category_status:
                if category_status not in FeedCategories.CategoryStatus.values:
                    return CustomResponse.errorResponse(
                        description="Invalid category status.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                categories = categories.filter(
                    status=category_status,
                )

            categories = categories.order_by("display_name")

            total = categories.count()

            paginator = self.pagination_class()
            page = paginator.paginate_queryset(categories, request)

            data = [
                {
                    "id": str(category.id),
                    "display_name": category.display_name,
                    "status": category.status,
                }
                for category in page
            ]

        except Exception as e:

            application_logger.exception(
                "feed_category_list_failed",
                requested_by=str(request.user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch feed categories.",
            )

        application_logger.info(
            "feed_category_list_fetched",
            requested_by=str(request.user.id),
            total=total,
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            data=data,
            total=total,
            description="Feed categories fetched successfully.",
        )

class FeedCategoryCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feed_category.create"

    @transaction.atomic
    def post(self, request):
        try:

            display_name = request.data.get("display_name", "").strip()

            category_status = request.data.get(
                "status",
                FeedCategories.CategoryStatus.ACTIVE,
            )

            if not display_name:
                return CustomResponse.errorResponse(
                    description="Category name is required.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if category_status not in FeedCategories.CategoryStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid category status.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if FeedCategories.objects.filter(
                display_name__iexact=display_name,
            ).exists():

                return CustomResponse.errorResponse(
                    description="Category already exists.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:

                category = FeedCategories.objects.create(
                    display_name=display_name,
                    status=category_status,
                )

            except Exception as e:

                application_logger.exception(
                    "feed_category_create_failed",
                    requested_by=str(request.user.id),
                    error=str(e),
                )

                return CustomResponse.errorResponse(
                    description="Unable to create feed category.",
                )

            application_logger.info(
                "feed_category_created",
                category_id=str(category.id),
                display_name=category.display_name,
                requested_by=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(category.id),
                    "display_name": category.display_name,
                    "status": category.status,
                },
                description="Feed category created successfully.",
            )
        except Exception as e:

            application_logger.exception(
                "Error creating feed category. "
                "error=%s",
                str(e),
            )


class FeedCategoryDetailAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    def get_permissions(self):

        if self.request.method == "PUT":
            self.required_permission = "feed_category.update"

        elif self.request.method == "DELETE":
            self.required_permission = "feed_category.delete"

        return super().get_permissions()

    def get_category(self, category_id):

        return FeedCategories.objects.filter(
            id=category_id,
        ).first()

    @transaction.atomic
    def put(self, request, category_id):

        category = self.get_category(category_id)

        if not category:
            return CustomResponse.errorResponse(
                description="Feed category not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        display_name = request.data.get("display_name")
        category_status = request.data.get("status")

        if display_name is not None:

            display_name = display_name.strip()

            if not display_name:
                return CustomResponse.errorResponse(
                    description="Category name cannot be empty.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            duplicate = FeedCategories.objects.filter(
                display_name__iexact=display_name,
            ).exclude(
                id=category.id,
            ).exists()

            if duplicate:
                return CustomResponse.errorResponse(
                    description="Category already exists.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            category.display_name = display_name

        if category_status is not None:

            if category_status not in FeedCategories.CategoryStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid category status.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            category.status = category_status

        category.save()

        application_logger.info(
            "feed_category_updated",
            category_id=str(category.id),
            requested_by=str(request.user.id),
        )

        return CustomResponse.successResponse(
            data={
                "id": str(category.id),
                "display_name": category.display_name,
                "status": category.status,
            },
            description="Feed category updated successfully.",
        )

    @transaction.atomic
    def delete(self, request, category_id):

        category = self.get_category(category_id)

        if not category:
            return CustomResponse.errorResponse(
                description="Feed category not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        category_id = str(category.id)

        category.delete()

        application_logger.info(
            "feed_category_deleted",
            category_id=category_id,
            requested_by=str(request.user.id),
        )

        return CustomResponse.successResponse(
            data={
                "id": category_id,
            },
            description="Feed category deleted successfully.",
        )



class DIYMaterialsAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    pagination_class = CustomPageNumberPagination

    def get_permissions(self):

        if self.request.method == "GET":
            self.required_permission = "feed.view"

        elif self.request.method == "POST":
            self.required_permission = "feed.update"

        return super().get_permissions()

    def get_feed(self, feed_id):

        return Feed.objects.filter(
            id=feed_id,
        ).first()

    def get(self, request, feed_id):

        application_logger.info(
            "diy_materials_list_requested",
            requested_by=str(request.user.id),
            feed_id=str(feed_id),
        )

        feed = self.get_feed(feed_id)

        if not feed:
            return CustomResponse.errorResponse(
                description="Feed not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        materials = DIYMaterials.objects.filter(
            feed=feed,
        ).order_by("display_order", "created_at")

        total = materials.count()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(materials, request)

        data = [
            {
                "id": str(material.id),
                "material_name": material.material_name,
                "quantity": material.quantity,
                "display_order": material.display_order,
            }
            for material in page
        ]

        application_logger.info(
            "diy_materials_list_fetched",
            requested_by=str(request.user.id),
            feed_id=str(feed.id),
            total=total,
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            data=data,
            total=total,
            description="DIY materials fetched successfully.",
        )

    @transaction.atomic
    def post(self, request, feed_id):

        feed = self.get_feed(feed_id)

        if not feed:
            return CustomResponse.errorResponse(
                description="Feed not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        material_name = request.data.get("material_name", "").strip()
        quantity = request.data.get("quantity")
        display_order = request.data.get("display_order", 0)

        if not material_name:
            return CustomResponse.errorResponse(
                description="Material name is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            display_order = int(display_order)

            if display_order < 0:
                raise ValueError

        except (ValueError, TypeError):
            return CustomResponse.errorResponse(
                description="Display order must be a non-negative integer.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        material = DIYMaterials.objects.create(
            feed=feed,
            material_name=material_name,
            quantity=quantity,
            display_order=display_order,
        )

        application_logger.info(
            "diy_material_created",
            material_id=str(material.id),
            feed_id=str(feed.id),
            requested_by=str(request.user.id),
        )

        return CustomResponse.successResponse(
            data={
                "id": str(material.id),
                "feed_id": str(feed.id),
                "material_name": material.material_name,
                "quantity": material.quantity,
                "display_order": material.display_order,
            },
            description="DIY material added successfully.",
        )



class DIYStepsAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    pagination_class = CustomPageNumberPagination

    def get_permissions(self):

        if self.request.method == "GET":
            self.required_permission = "feed.view"

        elif self.request.method == "POST":
            self.required_permission = "feed.update"

        return super().get_permissions()

    def get_feed(self, feed_id):

        return Feed.objects.filter(
            id=feed_id,
        ).first()

    def get(self, request, feed_id):

        application_logger.info(
            "diy_steps_list_requested",
            requested_by=str(request.user.id),
            feed_id=str(feed_id),
        )

        feed = self.get_feed(feed_id)

        if not feed:
            return CustomResponse.errorResponse(
                description="Feed not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        steps = DIYSteps.objects.filter(
            feed=feed,
        ).order_by("step_number")

        total = steps.count()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(steps, request)

        data = [
            {
                "id": str(step.id),
                "step_number": step.step_number,
                "heading": step.heading,
                "description": step.description,
                "image": step.image,
            }
            for step in page
        ]

        application_logger.info(
            "diy_steps_list_fetched",
            requested_by=str(request.user.id),
            feed_id=str(feed.id),
            total=total,
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            data=data,
            total=total,
            description="DIY steps fetched successfully.",
        )

    @transaction.atomic
    def post(self, request, feed_id):

        feed = self.get_feed(feed_id)

        if not feed:
            return CustomResponse.errorResponse(
                description="Feed not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        step_number = request.data.get("step_number")
        description = request.data.get("description", "").strip()

        if step_number is None:
            return CustomResponse.errorResponse(
                description="Step number is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            step_number = int(step_number)

            if step_number < 1:
                raise ValueError

        except (ValueError, TypeError):
            return CustomResponse.errorResponse(
                description="Step number must be a positive integer.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not description:
            return CustomResponse.errorResponse(
                description="Step description is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if DIYSteps.objects.filter(
            feed=feed,
            step_number=step_number,
        ).exists():

            return CustomResponse.errorResponse(
                description="Step number already exists for this feed.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        step = DIYSteps.objects.create(
            feed=feed,
            step_number=step_number,
            heading=request.data.get("heading"),
            description=description,
            image=request.data.get("image"),
        )

        application_logger.info(
            "diy_step_created",
            step_id=str(step.id),
            feed_id=str(feed.id),
            step_number=step.step_number,
            requested_by=str(request.user.id),
        )

        return CustomResponse.successResponse(
            data={
                "id": str(step.id),
                "feed_id": str(feed.id),
                "step_number": step.step_number,
                "heading": step.heading,
                "description": step.description,
                "image": step.image,
            },
            description="DIY step added successfully.",
        )


class DIYContentUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    def get_permissions(self):

        self.required_permission = "feed.update"

        return super().get_permissions()

    @transaction.atomic
    def put(self, request, feed_id):

        application_logger.info(
            "diy_content_update_started",
            requested_by=str(request.user.id),
            feed_id=str(feed_id),
        )

        feed = Feed.objects.filter(
            id=feed_id,
        ).first()

        if not feed:
            return CustomResponse.errorResponse(
                description="Feed not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        materials = request.data.get("materials")
        steps = request.data.get("steps")

        if materials is None and steps is None:
            return CustomResponse.errorResponse(
                description="Provide materials or steps to update.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate materials
        if materials is not None:

            if not isinstance(materials, list):
                return CustomResponse.errorResponse(
                    description="Materials must be a list.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for index, material in enumerate(materials):

                if not isinstance(material, dict):
                    return CustomResponse.errorResponse(
                        description=f"Invalid material at position {index + 1}.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if not str(material.get("material_name", "")).strip():
                    return CustomResponse.errorResponse(
                        description=f"Material name is required at position {index + 1}.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                try:
                    display_order = int(material.get("display_order", index))

                    if display_order < 0:
                        raise ValueError

                    material["display_order"] = display_order

                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        description=f"Invalid display order at position {index + 1}.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # Validate steps
        if steps is not None:

            if not isinstance(steps, list):
                return CustomResponse.errorResponse(
                    description="Steps must be a list.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            step_numbers = []

            for index, step in enumerate(steps):

                if not isinstance(step, dict):
                    return CustomResponse.errorResponse(
                        description=f"Invalid step at position {index + 1}.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                try:
                    step_number = int(step.get("step_number"))

                    if step_number < 1:
                        raise ValueError

                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        description=f"Valid step number is required at position {index + 1}.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if step_number in step_numbers:
                    return CustomResponse.errorResponse(
                        description=f"Duplicate step number: {step_number}.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                step_numbers.append(step_number)

                if not str(step.get("description", "")).strip():
                    return CustomResponse.errorResponse(
                        description=f"Step description is required at position {index + 1}.",
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                step["step_number"] = step_number

        # Update materials only when supplied
        if materials is not None:

            DIYMaterials.objects.filter(
                feed=feed,
            ).delete()

            DIYMaterials.objects.bulk_create([
                DIYMaterials(
                    feed=feed,
                    material_name=material["material_name"].strip(),
                    quantity=material.get("quantity"),
                    display_order=material["display_order"],
                )
                for material in materials
            ])

        # Update steps only when supplied
        if steps is not None:

            DIYSteps.objects.filter(
                feed=feed,
            ).delete()

            DIYSteps.objects.bulk_create([
                DIYSteps(
                    feed=feed,
                    step_number=step["step_number"],
                    heading=step.get("heading"),
                    description=step["description"].strip(),
                    image=step.get("image"),
                )
                for step in steps
            ])

        # Fetch updated content
        updated_materials = DIYMaterials.objects.filter(
            feed=feed,
        ).order_by("display_order", "created_at")

        updated_steps = DIYSteps.objects.filter(
            feed=feed,
        ).order_by("step_number")

        data = {
            "feed_id": str(feed.id),
            "materials": [
                {
                    "id": str(material.id),
                    "material_name": material.material_name,
                    "quantity": material.quantity,
                    "display_order": material.display_order,
                }
                for material in updated_materials
            ],
            "steps": [
                {
                    "id": str(step.id),
                    "step_number": step.step_number,
                    "heading": step.heading,
                    "description": step.description,
                    "image": step.image,
                }
                for step in updated_steps
            ],
        }

        application_logger.info(
            "diy_content_updated",
            requested_by=str(request.user.id),
            feed_id=str(feed.id),
            materials_count=updated_materials.count(),
            steps_count=updated_steps.count(),
        )

        return CustomResponse.successResponse(
            data=data,
            description="DIY content updated successfully.",
        )





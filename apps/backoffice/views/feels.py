from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.feels.models import Feels
from shared.mixins import CustomPageNumberPagination, CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class FeelsListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    pagination_class = CustomPageNumberPagination
    required_permission = "feels.view"

    def get(self, request):

        try:
            queryset = Feels.objects.all().order_by("-created_at")

            search = request.query_params.get("search")
            category = request.query_params.get("category")

            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(category__icontains=search)
                )

            if category:
                queryset = queryset.filter(
                    category__iexact=category
                )

            total = queryset.count()

            paginator = self.pagination_class()
            paginated_queryset = paginator.paginate_queryset(
                queryset,
                request,
                view=self,
            )

            if paginated_queryset is None:
                paginated_queryset = queryset

            data = [
                {
                    "id": str(feel.id),
                    "serial_number": feel.serial_number,
                    "youtube_video": feel.youtube_video,
                    "title": feel.title,
                    "description": feel.description,
                    "thumbnail_image": feel.thumbnail_image,
                    "likes_count": feel.likes_count,
                    "share_count": feel.share_count,
                    "views_count": feel.views_count,
                    "score": feel.score,
                    "category": feel.category,
                }
                for feel in paginated_queryset
            ]

            application_logger.info(
                "feels_list_fetched user_id=%s total=%s",
                request.user.id,
                total,
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Feels fetched successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "feels_list_failed user_id=%s error=%s",
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch feels.",
            )

class FeelsCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feels.create"

    @transaction.atomic
    def post(self, request):

        try:
            request_data = request.data

            title = request_data.get("title", "").strip()

            if not title:
                return CustomResponse.errorResponse(
                    description="Feel title is required.",
                )

            if len(title) > 100:
                return CustomResponse.errorResponse(
                    description="Feel title cannot exceed 100 characters.",
                )

            serial_number = request_data.get("serial_number")

            if serial_number not in [None, ""]:
                try:
                    serial_number = int(serial_number)

                    if serial_number <= 0:
                        raise ValueError

                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        description="Serial number must be a positive integer.",
                    )

                if Feels.objects.filter(
                    serial_number=serial_number
                ).exists():
                    return CustomResponse.errorResponse(
                        description="Serial number already exists.",
                    )

            score = request_data.get("score", 0)

            try:
                score = int(score)

                if score < 0:
                    raise ValueError

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Score must be a non-negative integer.",
                )

            feel = Feels.objects.create(
                title=title,
                youtube_video=request_data.get("youtube_video"),
                description=request_data.get("description"),
                thumbnail_image=request_data.get("thumbnail_image"),
                category=request_data.get("category") or "NA",
                score=score,
                serial_number=serial_number,
            )

            application_logger.info(
                "feel_created feel_id=%s serial_number=%s created_by=%s",
                feel.id,
                feel.serial_number,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(feel.id),
                    "serial_number": feel.serial_number,
                    "title": feel.title,
                    "youtube_video": feel.youtube_video,
                    "description": feel.description,
                    "thumbnail_image": feel.thumbnail_image,
                    "category": feel.category,
                    "score": feel.score,
                },
                description="Feel created successfully.",
            )

        except IntegrityError as e:

            application_logger.exception(
                "feel_create_integrity_failed user_id=%s error=%s",
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Serial number already exists. Please try again.",
            )

        except Exception as e:

            application_logger.exception(
                "feel_create_failed user_id=%s error=%s",
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to create feel.",
            )

class FeelsUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feels.update"

    @transaction.atomic
    def put(self, request, feel_id):

        try:
            feel = Feels.objects.filter(id=feel_id).first()

            if not feel:
                return CustomResponse.errorResponse(
                    description="Feel not found.",
                )

            request_data = request.data

            if "title" in request_data:

                title = request_data.get("title", "").strip()

                if not title:
                    return CustomResponse.errorResponse(
                        description="Feel title is required.",
                    )

                if len(title) > 100:
                    return CustomResponse.errorResponse(
                        description="Feel title cannot exceed 100 characters.",
                    )

                feel.title = title

            if "youtube_video" in request_data:
                feel.youtube_video = request_data.get("youtube_video")

            if "description" in request_data:
                feel.description = request_data.get("description")

            if "thumbnail_image" in request_data:
                feel.thumbnail_image = request_data.get("thumbnail_image")

            if "category" in request_data:
                feel.category = request_data.get("category") or "NA"

            if "score" in request_data:

                try:
                    score = int(request_data.get("score"))

                    if score < 0:
                        raise ValueError

                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        description="Score must be a non-negative integer.",
                    )

                feel.score = score

            if "serial_number" in request_data:

                try:
                    serial_number = int(request_data.get("serial_number"))

                    if serial_number <= 0:
                        raise ValueError

                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        description="Serial number must be a positive integer.",
                    )

                if Feels.objects.filter(
                    serial_number=serial_number
                ).exclude(id=feel.id).exists():
                    return CustomResponse.errorResponse(
                        description="Serial number already exists.",
                    )

                feel.serial_number = serial_number

            feel.save()

            application_logger.info(
                "feel_updated feel_id=%s updated_by=%s",
                feel.id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(feel.id),
                    "serial_number": feel.serial_number,
                    "title": feel.title,
                    "youtube_video": feel.youtube_video,
                    "description": feel.description,
                    "thumbnail_image": feel.thumbnail_image,
                    "category": feel.category,
                    "score": feel.score,
                },
                description="Feel updated successfully.",
            )

        except IntegrityError as e:

            application_logger.exception(
                "feel_update_integrity_failed feel_id=%s error=%s",
                feel_id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Serial number already exists.",
            )

        except Exception as e:

            application_logger.exception(
                "feel_update_failed feel_id=%s user_id=%s error=%s",
                feel_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to update feel.",
            )


class FeelsDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feels.delete"

    @transaction.atomic
    def delete(self, request, feel_id):

        try:
            feel = Feels.objects.filter(id=feel_id).first()

            if not feel:
                return CustomResponse.errorResponse(
                    description="Feel not found.",
                )

            deleted_feel_id = str(feel.id)

            feel.delete()

            application_logger.info(
                "feel_deleted feel_id=%s deleted_by=%s",
                deleted_feel_id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "id": deleted_feel_id,
                },
                description="Feel deleted successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "feel_delete_failed feel_id=%s user_id=%s error=%s",
                feel_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to delete feel.",
            )
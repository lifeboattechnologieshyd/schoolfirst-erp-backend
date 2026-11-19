from django.db import transaction
from django.db.models import Q, F
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.feels.models import Feels, FeelLikes
from shared.mixins import CustomPageNumberPagination, CustomResponse
from shared.utils.logger import application_logger


class FeelsLISTAPIView(APIView):

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get(self, request):

        try:
            search = request.query_params.get("search")
            category = request.query_params.get("category")

            feels = Feels.objects.all().order_by(
                "-score",
                "serial_number",
            )

            if search:
                feels = feels.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(category__icontains=search)
                )

            if category:
                feels = feels.filter(
                    category__iexact=category
                )

            total = feels.count()

            paginator = self.pagination_class()
            paginated_feels = paginator.paginate_queryset(
                feels,
                request,
                view=self,
            )

            if paginated_feels is None:
                paginated_feels = feels

            feel_ids = [feel.id for feel in paginated_feels]

            liked_feel_ids = set(
                FeelLikes.objects.filter(
                    user_id=request.user.id,
                    feel_id__in=feel_ids,
                ).values_list("feel_id", flat=True)
            )

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
                    "is_liked": feel.id in liked_feel_ids,
                }
                for feel in paginated_feels
            ]

            application_logger.info(
                "frontend_feels_fetched user_id=%s total=%s",
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
                "frontend_feels_fetch_failed user_id=%s error=%s",
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch feels.",
            )

class FeelShareAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, feel_id):

        try:
            feel = Feels.objects.filter(
                id=feel_id
            ).first()

            if not feel:
                return CustomResponse.errorResponse(
                    description="Feel not found.",
                )

            Feels.objects.filter(id=feel.id).update(
                share_count=F("share_count") + 1
            )

            feel.refresh_from_db()

            application_logger.info(
                "feel_shared feel_id=%s user_id=%s",
                feel.id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "feel_id": str(feel.id),
                    "share_count": feel.share_count,
                },
                description="Feel shared successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "feel_share_failed feel_id=%s user_id=%s error=%s",
                feel_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to share feel.",
            )

class FeelLikeAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, feel_id):

        try:
            feel = Feels.objects.filter(
                id=feel_id
            ).first()

            if not feel:
                return CustomResponse.errorResponse(
                    description="Feel not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            like, created = FeelLikes.objects.get_or_create(
                feel_id=feel.id,
                user_id=request.user.id,
            )

            if created:
                Feels.objects.filter(id=feel.id).update(
                    likes_count=F("likes_count") + 1
                )

            feel.refresh_from_db()

            application_logger.info(
                "feel_liked feel_id=%s user_id=%s created=%s",
                feel.id,
                request.user.id,
                created,
            )

            return CustomResponse.successResponse(
                data={
                    "feel_id": str(feel.id),
                    "is_liked": True,
                    "likes_count": feel.likes_count,
                },
                description=(
                    "Feel liked successfully."
                    if created else "Feel is already liked."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "feel_like_failed feel_id=%s user_id=%s error=%s",
                feel_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to like feel.",
            )

class FeelUnlikeAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def delete(self, request, feel_id):

        try:
            feel = Feels.objects.filter(
                id=feel_id
            ).first()

            if not feel:
                return CustomResponse.errorResponse(
                    description="Feel not found.",
                )

            deleted_count, _ = FeelLikes.objects.filter(
                feel_id=feel.id,
                user_id=request.user.id,
            ).delete()

            if deleted_count:
                Feels.objects.filter(
                    id=feel.id,
                    likes_count__gt=0,
                ).update(
                    likes_count=F("likes_count") - 1
                )

            feel.refresh_from_db()

            application_logger.info(
                "feel_unliked feel_id=%s user_id=%s",
                feel.id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "feel_id": str(feel.id),
                    "is_liked": False,
                    "likes_count": feel.likes_count,
                },
                description="Feel unliked successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "feel_unlike_failed feel_id=%s user_id=%s error=%s",
                feel_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to unlike feel.",
            )
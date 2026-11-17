
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from apps.edutainment.models import Feed
from shared.mixins import CustomPageNumberPagination, CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class FeedListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    pagination_class = CustomPageNumberPagination

    def get_permissions(self):
        return super().get_permissions()

    def get(self, request):

        self.required_permission = "feed.view"

        school = request.school

        category = request.query_params.get("category")
        feed_status = request.query_params.get("status")
        feed_type = request.query_params.get("feed_type")
        language = request.query_params.get("language")
        trending = request.query_params.get("trending")
        search = request.query_params.get("search")

        application_logger.info(
            "feed_list_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
        )

        try:

            feeds = Feed.objects.filter(
                school_id=school.id if school else None,
            )

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
                    trending=trending.lower() == "true",
                )

            if search:
                feeds = feeds.filter(
                    Q(heading__icontains=search)
                    | Q(description__icontains=search)
                    | Q(subject__icontains=search)
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

        except Exception as e:

            application_logger.exception(
                "feed_list_failed",
                requested_by=str(request.user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch feeds.",
            )

        application_logger.info(
            "feed_list_fetched",
            requested_by=str(request.user.id),
            total=total,
            returned_count=len(data),
        )

        return CustomResponse.successResponse(
            data=data,
            total=total,
            description="Feeds fetched successfully.",
        )

    @transaction.atomic
    def post(self, request):

        self.required_permission = "feed.create"

        school = request.school
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
                school_id=school.id if school else None,
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

        except Exception as e:

            application_logger.exception(
                "feed_create_failed",
                requested_by=str(request.user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to create feed.",
            )

        application_logger.info(
            "feed_created",
            feed_id=str(feed.id),
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
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



class FeedDetailAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    def get_feed(self, request, feed_id):

        school = request.school

        return Feed.objects.filter(
            id=feed_id,
            school_id=school.id if school else None,
        ).first()

    def get(self, request, feed_id):

        self.required_permission = "feed.view"

        feed = self.get_feed(request, feed_id)

        if not feed:
            return CustomResponse.errorResponse(
                description="Feed not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        data = {
            "id": str(feed.id),
            "serial_number": feed.serial_number,
            "heading": feed.heading,
            "feed_type": feed.feed_type,
            "f_category": feed.f_category,
            "image": feed.image,
            "video": feed.video,
            "youtube_video": feed.youtube_video,
            "audio_url": feed.audio_url,
            "trending": feed.trending,
            "categories": feed.categories,
            "grade_id": str(feed.grade_id) if feed.grade_id else None,
            "subject": feed.subject,
            "lesson": feed.lesson,
            "skill_tested": feed.skill_tested,
            "description": feed.description,
            "description_2": feed.description_2,
            "language": feed.language,
            "duration": feed.duration,
            "remarks": feed.remarks,
            "posting_date": feed.posting_date,
            "status": feed.status,
            "approved_by": feed.approved_by,
            "approved_time": feed.approved_time,
            "likes_count": feed.likes_count,
            "comments_count": feed.comments_count,
            "whatsapp_share_count": feed.whatsapp_share_count,
        }

        return CustomResponse.successResponse(
            data=data,
            description="Feed fetched successfully.",
        )

    @transaction.atomic
    def put(self, request, feed_id):

        self.required_permission = "feed.update"

        feed = self.get_feed(request, feed_id)

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

        if "feed_type" in request_data:
            if request_data["feed_type"] not in Feed.FeedType.values:
                return CustomResponse.errorResponse(
                    description="Invalid feed type.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if "f_category" in request_data:
            if request_data["f_category"] not in Feed.FeedCategory.values:
                return CustomResponse.errorResponse(
                    description="Invalid feed category.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if "language" in request_data:
            if request_data["language"] not in Feed.Language.values:
                return CustomResponse.errorResponse(
                    description="Invalid language.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        for field in allowed_fields:
            if field in request_data:
                setattr(feed, field, request_data.get(field))

        for field in ["feed_type", "f_category", "language"]:
            if field in request_data:
                setattr(feed, field, request_data[field])

        feed.save()

        application_logger.info(
            "feed_updated",
            feed_id=str(feed.id),
            requested_by=str(request.user.id),
        )

        return CustomResponse.successResponse(
            data={
                "id": str(feed.id),
                "heading": feed.heading,
                "status": feed.status,
            },
            description="Feed updated successfully.",
        )

    @transaction.atomic
    def delete(self, request, feed_id):

        self.required_permission = "feed.delete"

        feed = self.get_feed(request, feed_id)

        if not feed:
            return CustomResponse.errorResponse(
                description="Feed not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        feed_id = str(feed.id)
        feed.delete()

        application_logger.info(
            "feed_deleted",
            feed_id=feed_id,
            requested_by=str(request.user.id),
        )

        return CustomResponse.successResponse(
            data={"id": feed_id},
            description="Feed deleted successfully.",
        )



class FeedStatusUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    @transaction.atomic
    def patch(self, request, feed_id):

        self.required_permission = "feed.update"

        school = request.school

        feed = Feed.objects.filter(
            id=feed_id,
            school_id=school.id if school else None,
        ).first()

        if not feed:
            return CustomResponse.errorResponse(
                description="Feed not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")

        if not new_status:
            return CustomResponse.errorResponse(
                description="Status is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status not in Feed.FeedStatus.values:
            return CustomResponse.errorResponse(
                description="Invalid feed status.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        feed.status = new_status

        if new_status == Feed.FeedStatus.APPROVED:
            feed.approved_by = str(request.user.id)
            feed.approved_time = timezone.now()

        feed.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_time",
                "updated_at",
            ],
        )

        application_logger.info(
            "feed_status_updated",
            feed_id=str(feed.id),
            status=new_status,
            updated_by=str(request.user.id),
        )

        return CustomResponse.successResponse(
            data={
                "id": str(feed.id),
                "status": feed.status,
                "approved_by": feed.approved_by,
                "approved_time": feed.approved_time,
            },
            description="Feed status updated successfully.",
        )

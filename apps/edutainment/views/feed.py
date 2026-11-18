from django.db import transaction
from django.db.models import Q, F
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.edutainment.models import Feed, FeedLikes, FeedComments
from shared.mixins import CustomPageNumberPagination, CustomResponse
from shared.utils.logger import application_logger


class FeedLISTAPIView(APIView):

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get(self, request):

        try:
            category = request.query_params.get("category")
            language = request.query_params.get("language")
            feed_type = request.query_params.get("feed_type")
            trending = request.query_params.get("trending")
            search = request.query_params.get("search")
            grade_id = request.query_params.get("grade_id")

            feeds = Feed.objects.filter(
                status=Feed.FeedStatus.PUBLISHED
            )

            if category:
                feeds = feeds.filter(f_category=category)

            if language:
                feeds = feeds.filter(language=language)

            if feed_type:
                feeds = feeds.filter(feed_type=feed_type)

            if grade_id:
                feeds = feeds.filter(
                    Q(grade_id=grade_id) | Q(grade_id__isnull=True)
                )

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

            feeds = feeds.order_by("-posting_date", "-created_at")

            total = feeds.count()

            paginator = self.pagination_class()
            page = paginator.paginate_queryset(feeds, request)

            feed_ids = [feed.id for feed in page]

            liked_feed_ids = set(
                FeedLikes.objects.filter(
                    user_id=request.user.id,
                    feed_id__in=feed_ids,
                ).values_list("feed_id", flat=True)
            )

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
                    "likes_count": feed.likes_count,
                    "comments_count": feed.comments_count,
                    "whatsapp_share_count": feed.whatsapp_share_count,
                    "is_liked": feed.id in liked_feed_ids,
                }
                for feed in page
            ]

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
class FeedLikeAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, feed_id):

        try:
            feed = Feed.objects.filter(
                id=feed_id,
                status=Feed.FeedStatus.PUBLISHED,
            ).first()

            if not feed:
                return CustomResponse.errorResponse(
                    description="Feed not found.",
                )

            like, created = FeedLikes.objects.get_or_create(
                feed_id=feed.id,
                user_id=request.user.id,
            )

            if created:
                Feed.objects.filter(id=feed.id).update(
                    likes_count=F("likes_count") + 1
                )

            feed.refresh_from_db()

            return CustomResponse.successResponse(
                data={
                    "feed_id": str(feed.id),
                    "is_liked": True,
                    "likes_count": feed.likes_count,
                },
                description=(
                    "Feed liked successfully."
                    if created else "Feed is already liked."
                )
            )

        except Exception as e:

            application_logger.exception(
                "feed_like_failed feed_id=%s user_id=%s error=%s",
                feed_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to like feed."
            )

class FeedUnlikeAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def delete(self, request, feed_id):

        try:
            feed = Feed.objects.filter(id=feed_id).first()

            if not feed:
                return CustomResponse.errorResponse(
                    description="Feed not found.",
                )

            deleted_count, _ = FeedLikes.objects.filter(
                feed_id=feed.id,
                user_id=request.user.id,
            ).delete()

            if deleted_count:
                Feed.objects.filter(
                    id=feed.id,
                    likes_count__gt=0,
                ).update(
                    likes_count=F("likes_count") - 1
                )

            feed.refresh_from_db()

            return CustomResponse.successResponse(
                data={
                    "feed_id": str(feed.id),
                    "is_liked": False,
                    "likes_count": feed.likes_count,
                },
                description="Feed unliked successfully."
            )

        except Exception as e:

            application_logger.exception(
                "feed_unlike_failed feed_id=%s user_id=%s error=%s",
                feed_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to unlike feed."
            )

class FeedCommentsListAPIView(APIView):

    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get(self, request, feed_id):

        try:
            feed = Feed.objects.filter(
                id=feed_id,
                status=Feed.FeedStatus.PUBLISHED,
            ).first()

            if not feed:
                return CustomResponse.errorResponse(
                    description="Feed not found.",
                )

            parent_id = request.query_params.get("parent_id")

            comments = FeedComments.objects.filter(
                feed_id=feed.id,
                parent_id=parent_id if parent_id else None,
            ).order_by("created_at")

            total = comments.count()

            paginator = self.pagination_class()
            page = paginator.paginate_queryset(comments, request)

            data = [
                {
                    "id": str(comment.id),
                    "feed_id": str(comment.feed_id),
                    "parent_id": str(comment.parent_id) if comment.parent_id else None,
                    "user_id": str(comment.user_id),
                    "user_name": comment.user_name,
                    "profile_pic": comment.profile_pic,
                    "comment": comment.comment,
                    "image": comment.image,
                    "likes_count": comment.likes_count,
                    "comments_count": comment.comments_count,
                    "created_at": comment.created_at,
                }
                for comment in page
            ]

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Feed comments fetched successfully."
            )

        except Exception as e:

            application_logger.exception(
                "feed_comments_list_failed feed_id=%s error=%s",
                feed_id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch feed comments."
            )

class FeedCommentCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, feed_id):

        try:
            feed = Feed.objects.filter(
                id=feed_id,
                status=Feed.FeedStatus.PUBLISHED,
            ).first()

            if not feed:
                return CustomResponse.errorResponse(
                    description="Feed not found.",
                )

            comment_text = request.data.get("comment")
            image = request.data.get("image")
            parent_id = request.data.get("parent_id")

            if not comment_text and not image:
                return CustomResponse.errorResponse(
                    description="Comment or image is required.",
                )

            if comment_text and len(comment_text) > 500:
                return CustomResponse.errorResponse(
                    description="Comment cannot exceed 500 characters.",
                )

            parent_comment = None

            if parent_id:

                parent_comment = FeedComments.objects.filter(
                    id=parent_id,
                    feed_id=feed.id,
                    parent_id__isnull=True,
                ).first()

                if not parent_comment:
                    return CustomResponse.errorResponse(
                        description="Parent comment not found.",
                    )

            user_name = (
                request.user.get_full_name()
                or getattr(request.user, "username", "")
            )

            comment = FeedComments.objects.create(
                feed_id=feed.id,
                user_id=request.user.id,
                parent_id=parent_comment.id if parent_comment else None,
                comment=comment_text,
                image=image,
                user_name=user_name,
            )

            Feed.objects.filter(id=feed.id).update(
                comments_count=F("comments_count") + 1
            )

            if parent_comment:
                FeedComments.objects.filter(
                    id=parent_comment.id
                ).update(
                    comments_count=F("comments_count") + 1
                )

            feed.refresh_from_db()

            return CustomResponse.successResponse(
                data={
                    "id": str(comment.id),
                    "feed_id": str(comment.feed_id),
                    "parent_id": str(comment.parent_id) if comment.parent_id else None,
                    "user_id": str(comment.user_id),
                    "user_name": comment.user_name,
                    "comment": comment.comment,
                    "image": comment.image,
                    "created_at": comment.created_at,
                    "feed_comments_count": feed.comments_count,
                },
                description="Comment added successfully."
            )

        except Exception as e:

            application_logger.exception(
                "feed_comment_create_failed feed_id=%s user_id=%s error=%s",
                feed_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to add comment."
            )

class FeedCommentDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def delete(self, request, feed_id, comment_id):

        try:
            feed = Feed.objects.filter(id=feed_id).first()

            if not feed:
                return CustomResponse.errorResponse(
                    description="Feed not found.",
                )

            comment = FeedComments.objects.filter(
                id=comment_id,
                feed_id=feed.id,
                user_id=request.user.id,
            ).first()

            if not comment:
                return CustomResponse.errorResponse(
                    description="Comment not found or you cannot delete this comment.",
                )

            if comment.parent_id is None:

                reply_ids = list(
                    FeedComments.objects.filter(
                        parent_id=comment.id,
                        feed_id=feed.id,
                    ).values_list("id", flat=True)
                )

                FeedComments.objects.filter(
                    id__in=reply_ids
                ).delete()

                FeedComments.objects.filter(
                    id=comment.id
                ).delete()

                FeedComments.objects.filter(
                    id=comment.id
                ).update(comments_count=0)

                Feed.objects.filter(
                    id=feed.id,
                    comments_count__gte=len(reply_ids) + 1,
                ).update(
                    comments_count=F("comments_count") - len(reply_ids) - 1
                )

                # Handle a counter lower than the number of deleted records.
                if len(reply_ids) + 1 > feed.comments_count:
                    Feed.objects.filter(id=feed.id).update(
                        comments_count=0
                    )

            else:

                parent_id = comment.parent_id

                FeedComments.objects.filter(id=comment.id).delete()

                FeedComments.objects.filter(
                    id=parent_id,
                    comments_count__gt=0,
                ).update(
                    comments_count=F("comments_count") - 1
                )

                Feed.objects.filter(
                    id=feed.id,
                    comments_count__gt=0,
                ).update(
                    comments_count=F("comments_count") - 1
                )

            application_logger.info(
                "feed_comment_deleted feed_id=%s comment_id=%s user_id=%s",
                feed.id,
                comment_id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "comment_id": str(comment_id),
                },
                description="Comment deleted successfully."
            )

        except Exception as e:

            application_logger.exception(
                "feed_comment_delete_failed comment_id=%s user_id=%s error=%s",
                comment_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to delete comment."
            )

class FeedShareAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, feed_id):

        try:
            feed = Feed.objects.filter(
                id=feed_id,
                status=Feed.FeedStatus.PUBLISHED,
            ).first()

            if not feed:
                return CustomResponse.errorResponse(
                    description="Feed not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            Feed.objects.filter(id=feed.id).update(
                whatsapp_share_count=F("whatsapp_share_count") + 1
            )

            feed.refresh_from_db()

            application_logger.info(
                "feed_shared feed_id=%s user_id=%s",
                feed.id,
                request.user.id,
            )

            return CustomResponse.successResponse(
                data={
                    "feed_id": str(feed.id),
                    "whatsapp_share_count": feed.whatsapp_share_count,
                },
                description="Feed share count updated successfully."
            )

        except Exception as e:

            application_logger.exception(
                "feed_share_failed feed_id=%s user_id=%s error=%s",
                feed_id,
                request.user.id,
                str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to update feed share count."
            )
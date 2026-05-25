from django.db.models import Prefetch
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.feed.models.feed import Feed, FeedReaction, FeedSave
from apps.feed.serializers.feed import (
    FeedCommentSerializer,
    FeedCommentWriteSerializer,
    FeedCreateSerializer,
    FeedListQuerySerializer,
    FeedListSerializer,
    FeedReactionWriteSerializer,
    FeedShareWriteSerializer,
    FeedUpdateSerializer,
)
from apps.feed.services.feed_service import FeedService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomResponse
from shared.mixins.pagination import CustomPageNumberPagination


def _feed_prefetch(user) -> list[Prefetch]:
    return [
        Prefetch(
            "reactions",
            queryset=FeedReaction.objects.filter(user=user),
            to_attr="user_reactions",
        ),
        Prefetch("reactions", to_attr="all_reactions"),
        Prefetch(
            "saves",
            queryset=FeedSave.objects.filter(user=user),
            to_attr="user_saves",
        ),
    ]


def _load_feed_response(user, feed_id: str) -> Feed | None:
    return (
        FeedService.get_feed_queryset(user)
        .filter(id=feed_id)
        .prefetch_related(*_feed_prefetch(user))
        .first()
    )


def _pagination_meta(total: int, page: int, page_size: int) -> dict[str, int]:
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {"total": total, "page": page, "page_size": page_size, "total_pages": total_pages}


class FeedAPIView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def _forbidden_response(self, exc: PermissionDenied) -> Response:
        return self.build_response(
            success=False,
            error={
                "code": GlobalAPIMessageCodes.FORBIDDEN,
                "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                "details": [{"type": "detail", "message": str(exc.detail)}],
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    def _validation_response(self, detail: object, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        return self.build_response(
            success=False,
            error={
                "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                "details": self._format_validation_errors(detail),
            },
            status=status_code,
        )

    def _not_found_response(self) -> Response:
        return self.build_response(
            success=False,
            error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
            status=status.HTTP_404_NOT_FOUND,
        )


class FeedListCreateView(FeedAPIView):
    def get(self, request: Request) -> Response:
        query_serializer = FeedListQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            return self._validation_response(query_serializer.errors)

        creator_id = query_serializer.validated_data.get("creator_id")

        paginator = CustomPageNumberPagination()
        page_size = paginator.get_page_size(request) or paginator.page_size
        page_number = int(request.query_params.get("page", 1))

        queryset = FeedService.get_feed_queryset(request.user, creator_id=creator_id).prefetch_related(
            *_feed_prefetch(request.user),
        )
        total = queryset.count()
        offset = (page_number - 1) * page_size
        feeds = list(queryset[offset : offset + page_size])

        data = FeedListSerializer(feeds, many=True, context={"request": request}).data
        return self.build_response(
            success=True,
            message="Feed loaded.",
            data=data,
            meta=_pagination_meta(total, page_number, page_size),
        )

    def post(self, request: Request) -> Response:
        serializer = FeedCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self._validation_response(serializer.errors)

        validated = serializer.validated_data
        try:
            feed = FeedService.create_feed(
                user=request.user,
                text=validated.get("body_text"),
                media_urls=validated.get("media_urls"),
                youtube_url=validated.get("youtube_url"),
                external_urls=validated.get("external_urls"),
                access_type=validated.get("access_type", "only_me"),
                access_family_ids=validated.get("access_family_ids"),
                access_close_group_ids=validated.get("access_close_group_ids"),
                access_user_ids=validated.get("access_user_ids"),
            )
        except PermissionDenied as exc:
            return self._forbidden_response(exc)
        except ValidationError as exc:
            return self._validation_response(exc.detail)

        response_feed = _load_feed_response(request.user, str(feed.id)) or feed
        return self.build_response(
            success=True,
            data=FeedListSerializer(response_feed, context={"request": request}).data,
            message="Feed created successfully",
            status=status.HTTP_201_CREATED,
        )


class FeedDetailView(FeedAPIView):
    def get(self, request: Request, feed_id: str) -> Response:
        feed = _load_feed_response(request.user, feed_id)
        if feed is None:
            return self._not_found_response()
        return self.build_response(
            success=True,
            message="Feed retrieved.",
            data=FeedListSerializer(feed, context={"request": request}).data,
        )

    def delete(self, request: Request, feed_id: str) -> Response:
        try:
            FeedService.delete_feed(request.user, feed_id)
        except PermissionDenied as exc:
            return self._forbidden_response(exc)
        except ValidationError as exc:
            return self._validation_response(exc.detail, status.HTTP_404_NOT_FOUND)

        return self.build_response(success=True, message="Feed deleted successfully", data={})

    def put(self, request: Request, feed_id: str) -> Response:
        return self._perform_feed_update(request, feed_id, partial=False)

    def patch(self, request: Request, feed_id: str) -> Response:
        return self._perform_feed_update(request, feed_id, partial=True)

    def _perform_feed_update(self, request: Request, feed_id: str, *, partial: bool) -> Response:
        serializer = FeedUpdateSerializer(data=request.data, partial=partial)
        if not serializer.is_valid():
            return self._validation_response(serializer.errors)

        validated = serializer.validated_data
        try:
            feed = FeedService.update_feed(
                user=request.user,
                feed_id=feed_id,
                text=validated.get("body_text"),
                media_urls=validated.get("media_urls"),
                youtube_url=validated.get("youtube_url"),
                external_urls=validated.get("external_urls"),
                access_type=validated.get("access_type"),
                access_family_ids=validated.get("access_family_ids"),
                access_close_group_ids=validated.get("access_close_group_ids"),
                access_user_ids=validated.get("access_user_ids"),
                text_provided="body_text" in request.data if partial else True,
                media_urls_provided="media_urls" in request.data if partial else True,
                youtube_url_provided="youtube_url" in request.data if partial else True,
                external_urls_provided="external_urls" in request.data if partial else True,
            )
        except PermissionDenied as exc:
            return self._forbidden_response(exc)
        except ValidationError as exc:
            return self._validation_response(exc.detail)

        response_feed = _load_feed_response(request.user, str(feed.id))
        if response_feed is None:
            return self._not_found_response()
        return self.build_response(
            success=True,
            data=FeedListSerializer(response_feed, context={"request": request}).data,
            message="Feed updated successfully",
        )


class FeedCommentListCreateView(FeedAPIView):
    def get(self, request: Request, feed_id: str) -> Response:
        paginator = CustomPageNumberPagination()
        page_size = paginator.get_page_size(request) or paginator.page_size
        page_number = int(request.query_params.get("page", 1))

        try:
            comments, total = FeedService.get_feed_comments(request.user, feed_id, page_number, page_size)
        except PermissionDenied as exc:
            return self._forbidden_response(exc)
        except ValidationError as exc:
            return self._validation_response(exc.detail, status.HTTP_404_NOT_FOUND)

        return self.build_response(
            success=True,
            message="Comments retrieved.",
            data=FeedCommentSerializer(comments, many=True).data,
            meta=_pagination_meta(total, page_number, page_size),
        )

    def post(self, request: Request, feed_id: str) -> Response:
        serializer = FeedCommentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return self._validation_response(serializer.errors)

        try:
            comment_obj = FeedService.comment_on_feed(
                request.user,
                feed_id,
                serializer.validated_data["comment_text"],
            )
        except PermissionDenied as exc:
            return self._forbidden_response(exc)
        except ValidationError as exc:
            return self._validation_response(exc.detail)

        return self.build_response(
            success=True,
            data=FeedCommentSerializer(comment_obj).data,
            message="Comment added successfully",
        )


class FeedCommentDestroyView(FeedAPIView):
    def delete(self, request: Request, feed_id: str, comment_id: str) -> Response:
        try:
            FeedService.delete_feed_comment(request.user, feed_id, comment_id)
        except PermissionDenied as exc:
            return self._forbidden_response(exc)
        except ValidationError as exc:
            return self._validation_response(exc.detail, status.HTTP_404_NOT_FOUND)

        return self.build_response(success=True, message="Comment deleted successfully", data={})

    def patch(self, request: Request, feed_id: str, comment_id: str) -> Response:
        serializer = FeedCommentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return self._validation_response(serializer.errors)

        try:
            comment_obj = FeedService.update_feed_comment(
                request.user,
                feed_id,
                comment_id,
                serializer.validated_data["comment_text"],
            )
        except PermissionDenied as exc:
            return self._forbidden_response(exc)
        except ValidationError as exc:
            return self._validation_response(exc.detail)

        return self.build_response(
            success=True,
            data=FeedCommentSerializer(comment_obj).data,
            message="Comment updated successfully",
        )


class FeedReactionView(FeedAPIView):
    def post(self, request: Request, feed_id: str) -> Response:
        serializer = FeedReactionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return self._validation_response(serializer.errors)

        try:
            FeedService.react_to_feed(
                request.user,
                feed_id,
                serializer.validated_data.get("reaction"),
            )
        except PermissionDenied as exc:
            return self._forbidden_response(exc)
        except ValidationError as exc:
            return self._validation_response(exc.detail)

        response_feed = _load_feed_response(request.user, feed_id)
        if response_feed is None:
            return self._not_found_response()
        return self.build_response(
            success=True,
            message="Reaction recorded successfully",
            data=FeedListSerializer(response_feed, context={"request": request}).data,
        )


class FeedSaveView(FeedAPIView):
    def post(self, request: Request, feed_id: str) -> Response:
        try:
            FeedService.save_feed(request.user, feed_id)
        except PermissionDenied as exc:
            return self._forbidden_response(exc)

        response_feed = _load_feed_response(request.user, feed_id)
        if response_feed is None:
            return self._not_found_response()
        return self.build_response(
            success=True,
            message="Feed saved successfully",
            data=FeedListSerializer(response_feed, context={"request": request}).data,
        )

    def delete(self, request: Request, feed_id: str) -> Response:
        try:
            FeedService.unsave_feed(request.user, feed_id)
        except PermissionDenied as exc:
            return self._forbidden_response(exc)

        response_feed = _load_feed_response(request.user, feed_id)
        if response_feed is None:
            return self._not_found_response()
        return self.build_response(
            success=True,
            message="Feed unsaved successfully",
            data=FeedListSerializer(response_feed, context={"request": request}).data,
        )


class FeedSavedListView(FeedAPIView):
    def get(self, request: Request) -> Response:
        paginator = CustomPageNumberPagination()
        page_size = paginator.get_page_size(request) or paginator.page_size
        page_number = int(request.query_params.get("page", 1))

        feeds, total = FeedService.get_saved_feeds(request.user, page_number, page_size)
        feeds_with_prefetch = list(
            Feed.objects.filter(id__in=[feed.id for feed in feeds])
            .select_related("creator")
            .prefetch_related(*_feed_prefetch(request.user)),
        )
        feed_by_id = {feed.id: feed for feed in feeds_with_prefetch}
        ordered_feeds = [feed_by_id[feed.id] for feed in feeds if feed.id in feed_by_id]

        data = FeedListSerializer(ordered_feeds, many=True, context={"request": request}).data
        return self.build_response(
            success=True,
            message="Saved feeds loaded.",
            data=data,
            meta=_pagination_meta(total, page_number, page_size),
        )


class FeedShareView(FeedAPIView):
    def post(self, request: Request, feed_id: str) -> Response:
        serializer = FeedShareWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return self._validation_response(serializer.errors)

        try:
            FeedService.share_feed(request.user, feed_id, serializer.validated_data["platform"])
        except PermissionDenied as exc:
            return self._forbidden_response(exc)
        except ValidationError as exc:
            return self._validation_response(exc.detail)

        return self.build_response(success=True, message="Share logged successfully", data={})

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.enums import CommentParentType
from apps.calendar.models import Event
from apps.calendar.serializers.comment import CommentBodySerializer, CommentReadSerializer
from apps.calendar.serializers.event import EventListSerializer, EventReadSerializer, EventWriteSerializer
from apps.calendar.services.access import assert_is_creator
from apps.calendar.services.comment import CommentService
from apps.calendar.services.event import EventService
from apps.calendar.services.list_queries import EventListQuery
from apps.calendar.services.query_common import (
    build_validation_error_details,
    parse_occurrence_date,
    parse_query_date,
    validate_query_date_window,
    validate_recurrence_scope,
)
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomResponse


class EventListCreateView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = EventListQuery(request.user)
        params = request.query_params
        try:
            from_date = parse_query_date(params.get("from_date"), "from_date")
            to_date = parse_query_date(params.get("to_date"), "to_date")
            validate_query_date_window(from_date, to_date)
            result = query.execute(params, from_date, to_date)
        except ValueError as exc:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": build_validation_error_details(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return self.build_response(
            success=True,
            message="Events retrieved.",
            data=EventListSerializer(result.items, many=True).data,
            meta=result.meta,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = EventWriteSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        service = EventService(request.user)
        try:
            event = service.create(serializer.validated_data)
        except ValueError as exc:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": build_validation_error_details(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self.build_response(
            success=True,
            message="Event created successfully.",
            data=EventReadSerializer(event, context={"include_comments": False}).data,
            status=status.HTTP_201_CREATED,
        )


class EventDetailView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def _get_event(self, request, pk):
        service = EventService(request.user)
        try:
            return service.get_single(pk), service
        except Event.DoesNotExist:
            return None, service

    def get(self, request, pk):
        event, _ = self._get_event(request, pk)
        if event is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        return self.build_response(
            success=True,
            message="Event details retrieved.",
            data=EventReadSerializer(event, context={"include_comments": True}).data,
        )

    def put(self, request, pk):
        event, service = self._get_event(request, pk)
        if event is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            assert_is_creator(request.user, event)
        except PermissionError:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.FORBIDDEN, "message": GlobalAPIMessageCodes.FORBIDDEN.label},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = EventWriteSerializer(data=request.data, partial=True, context={"request": request})
        if not serializer.is_valid():
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        update_scope = request.data.get("update_scope", "all")
        scope_error = validate_recurrence_scope(update_scope, serializer.validated_data.get("recurrence_date"))
        if scope_error:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(scope_error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = service.update(event, serializer.validated_data, update_scope=update_scope)
        except ValueError as exc:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": build_validation_error_details(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self.build_response(
            success=True,
            message="Event updated successfully.",
            data=EventReadSerializer(result, context={"include_comments": False}).data,
        )

    def delete(self, request, pk):
        event, service = self._get_event(request, pk)
        if event is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            assert_is_creator(request.user, event)
        except PermissionError:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.FORBIDDEN, "message": GlobalAPIMessageCodes.FORBIDDEN.label},
                status=status.HTTP_403_FORBIDDEN,
            )
        scope = request.query_params.get("scope", "all")
        try:
            recurrence_date = parse_occurrence_date(request.query_params.get("occurrence_date"))
        except ValueError as exc:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": build_validation_error_details(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            service.delete(event, scope=scope, recurrence_date=recurrence_date)
        except ValueError as exc:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": build_validation_error_details(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self.build_response(success=True, message="Event deleted successfully.", data={"deleted": True})


class EventCommentListCreateView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def _get_event(self, request, pk):
        service = EventService(request.user)
        try:
            return service.get_single(pk), service
        except Event.DoesNotExist:
            return None, service

    def get(self, request, pk):
        event, service = self._get_event(request, pk)
        if event is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            target_event = service.resolve_occurrence_target(
                event,
                parse_occurrence_date(request.query_params.get("occurrence_date")),
            )
        except ValueError as exc:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": build_validation_error_details(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        comments = CommentService(request.user).list_for_parent(CommentParentType.EVENT, target_event.id)
        return self.build_response(
            success=True,
            message="Comments retrieved.",
            data=CommentReadSerializer(comments, many=True).data,
        )

    def post(self, request, pk):
        event, service = self._get_event(request, pk)
        if event is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CommentBodySerializer(data=request.data)
        if not serializer.is_valid():
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(serializer.errors),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            target_event = service.resolve_occurrence_target(
                event,
                serializer.validated_data.get("occurrence_date"),
            )
        except ValueError as exc:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": build_validation_error_details(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        comment = CommentService(request.user).create(
            parent_type=CommentParentType.EVENT,
            parent_id=target_event.id,
            body=serializer.validated_data["comment"],
        )
        return self.build_response(
            success=True,
            message="Comment added successfully.",
            data=CommentReadSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )

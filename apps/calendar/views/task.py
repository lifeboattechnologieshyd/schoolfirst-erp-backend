from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.enums import CommentParentType, TaskStatus
from apps.calendar.models import Task
from apps.calendar.serializers.comment import CommentBodySerializer, CommentReadSerializer
from apps.calendar.serializers.task import (
    TaskListSerializer,
    TaskReadSerializer,
    TaskStatusSerializer,
    TaskWriteSerializer,
)
from apps.calendar.services.access import assert_is_creator
from apps.calendar.services.comment import CommentService
from apps.calendar.services.list_queries import TaskListQuery
from apps.calendar.services.query_common import (
    build_validation_error_details,
    parse_occurrence_date,
    parse_query_date,
    validate_query_date_window,
    validate_recurrence_scope,
)
from apps.calendar.services.task import TaskService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomResponse


class TaskListCreateView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def _build_query_validation_error(self, exc: ValueError):
        return self.build_response(
            success=False,
            error={
                "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                "details": build_validation_error_details(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request):
        query = TaskListQuery(request.user)

        params = request.query_params
        try:
            from_date = parse_query_date(params.get("from_date"), "from_date")
            to_date = parse_query_date(params.get("to_date"), "to_date")
            validate_query_date_window(from_date, to_date)
            result = query.execute(params, from_date, to_date)
        except ValueError as exc:
            return self._build_query_validation_error(exc)

        return self.build_response(
            success=True,
            message="Tasks retrieved.",
            data=TaskListSerializer(result.items, many=True).data,
            meta=result.meta,
        )

    def post(self, request):
        serializer = TaskWriteSerializer(data=request.data, context={"request": request})
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
        service = TaskService(request.user)
        try:
            task = service.create(serializer.validated_data)
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
            message="Task created successfully.",
            data=TaskReadSerializer(task, context={"include_comments": False}).data,
            status=status.HTTP_201_CREATED,
        )


class TaskDetailView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def _get_task(self, request, pk):
        service = TaskService(request.user)
        try:
            return service.get_single(pk), service
        except Task.DoesNotExist:
            return None, service

    def get(self, request, pk):
        task, _ = self._get_task(request, pk)
        if task is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        return self.build_response(
            success=True,
            message="Task details retrieved.",
            data=TaskReadSerializer(task, context={"include_comments": True}).data,
        )

    def put(self, request, pk):
        task, service = self._get_task(request, pk)
        if task is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            assert_is_creator(request.user, task)
        except PermissionError:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.FORBIDDEN, "message": GlobalAPIMessageCodes.FORBIDDEN.label},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = TaskWriteSerializer(data=request.data, partial=True, context={"request": request})
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
            result = service.update(task, serializer.validated_data, update_scope=update_scope)
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
            message="Task updated successfully.",
            data=TaskReadSerializer(result, context={"include_comments": False}).data,
        )

    def delete(self, request, pk):
        task, service = self._get_task(request, pk)
        if task is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            assert_is_creator(request.user, task)
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
            service.delete(task, scope=scope, recurrence_date=recurrence_date)
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
        return self.build_response(success=True, message="Task deleted successfully.", data={"deleted": True})


class TaskCommentListCreateView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def _get_task(self, request, pk):
        service = TaskService(request.user)
        try:
            return service.get_single(pk), service
        except Task.DoesNotExist:
            return None, service

    def get(self, request, pk):
        task, service = self._get_task(request, pk)
        if task is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            target_task = service.resolve_occurrence_target(
                task,
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
        comments = CommentService(request.user).list_for_parent(CommentParentType.TASK, target_task.id)
        return self.build_response(
            success=True,
            message="Comments retrieved.",
            data=CommentReadSerializer(comments, many=True).data,
        )

    def post(self, request, pk):
        task, service = self._get_task(request, pk)
        if task is None:
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
            target_task = service.resolve_occurrence_target(
                task,
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
            parent_type=CommentParentType.TASK,
            parent_id=target_task.id,
            body=serializer.validated_data["comment"],
        )
        return self.build_response(
            success=True,
            message="Comment added successfully.",
            data=CommentReadSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )


class TaskStatusView(APIView, CustomResponse):
    """
    PUT /calendar/tasks/<pk>/status

    Update task status. Any user with access to the task can call this.
    """

    permission_classes = [IsAuthenticated]

    def _get_task(self, request, pk):
        service = TaskService(request.user)
        try:
            return service.get_single(pk), service
        except Task.DoesNotExist:
            return None, service

    def put(self, request, pk):
        task, service = self._get_task(request, pk)
        if task is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = TaskStatusSerializer(data=request.data)
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
        task = service.update_status(task, serializer.validated_data["status"])
        return self.build_response(
            success=True,
            message="Task status updated.",
            data={
                "task_id": str(task.id),
                "status": task.status,
                "completed_at": task.completed_at,
                "done_by": str(task.done_by) if task.done_by else None,
                "is_visible": task.is_visible,
            },
        )


class TaskStatusAcknowledgeView(APIView, CustomResponse):
    """
    PUT /calendar/tasks/<pk>/status/acknowledge

    Creator accepts or rejects a completion made by someone else.

    Body:
        action: "accept" — hides the task (is_visible=False, acknowledged_at=now).
        action: "reject" — reverts to pending (done_by/completed_at cleared).

    Only the task creator can call this endpoint.
    Guards: returns 400 if task is pending, self-completed, or already acknowledged.
    """

    permission_classes = [IsAuthenticated]

    def _get_task(self, request, pk):
        service = TaskService(request.user)
        try:
            return service.get_single(pk), service
        except Task.DoesNotExist:
            return None, service

    def put(self, request, pk):
        task, service = self._get_task(request, pk)
        if task is None:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.NOT_FOUND, "message": GlobalAPIMessageCodes.NOT_FOUND.label},
                status=status.HTTP_404_NOT_FOUND,
            )

        action = request.data.get("action")
        if action not in ("accept", "reject"):
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors({"action": "action must be 'accept' or 'reject'."}),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if task.status != TaskStatus.DONE:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(
                        {"status": "Task must be in done status to acknowledge."}
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if task.done_by and str(task.done_by) == str(task.creator_id):
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(
                        {"done_by": "Task was completed by the creator and requires no acknowledgment."}
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if task.acknowledged_at is not None:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(
                        {"acknowledged_at": "Task has already been acknowledged."}
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task = service.review_completion(task, action)
        except PermissionError:
            return self.build_response(
                success=False,
                error={"code": GlobalAPIMessageCodes.FORBIDDEN, "message": GlobalAPIMessageCodes.FORBIDDEN.label},
                status=status.HTTP_403_FORBIDDEN,
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

        if action == "accept":
            return self.build_response(
                success=True,
                message="Task completion accepted.",
                data={
                    "task_id": str(task.id),
                    "acknowledged_at": task.acknowledged_at,
                    "is_visible": task.is_visible,
                },
            )
        return self.build_response(
            success=True,
            message="Task completion rejected — reverted to pending.",
            data={
                "task_id": str(task.id),
                "status": task.status,
                "done_by": None,
                "completed_at": None,
                "is_visible": task.is_visible,
            },
        )

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.serializers.calendar import CalendarDayRequestSerializer, CalendarRequestSerializer
from apps.calendar.serializers.event import (
    EventCalendarSummarySerializer,
    EventReadSerializer,
    GeneralEventCalendarSerializer,
)
from apps.calendar.serializers.task import TaskCalendarSummarySerializer, TaskReadSerializer
from apps.calendar.services.calendar import CalendarDayService, CalendarSummaryService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomResponse


class UnifiedCalendarView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def _validation_error_response(self, serializer):
        return self.build_response(
            success=False,
            error={
                "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                "details": self._format_validation_errors(serializer.errors),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _handle(self, request):
        serializer = CalendarRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return self._validation_error_response(serializer)
        service = CalendarSummaryService(request.user)
        raw = service.get_summary_view(
            from_date=serializer.validated_data["from_date"],
            to_date=serializer.validated_data["to_date"],
        )
        result = {
            "from_date": raw["from_date"],
            "to_date": raw["to_date"],
            "events": EventCalendarSummarySerializer(raw["events"], many=True).data,
            "tasks": TaskCalendarSummarySerializer(raw["tasks"], many=True).data,
            "general_events": GeneralEventCalendarSerializer(raw["general_events"], many=True).data,
        }
        return self.build_response(success=True, message="Calendar loaded.", data=result)

    def get(self, request):
        return self._handle(request)


class CalendarDayView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CalendarDayRequestSerializer(data=request.query_params)
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

        raw = CalendarDayService(request.user).get_day_view(serializer.validated_data["date"])
        result = {
            "date": raw["date"],
            "events": EventReadSerializer(raw["events"], many=True, context={"include_comments": True}).data,
            "tasks": TaskReadSerializer(raw["tasks"], many=True, context={"include_comments": True}).data,
            "general_events": GeneralEventCalendarSerializer(raw["general_events"], many=True).data,
        }
        return self.build_response(success=True, message="Calendar day loaded.", data=result)

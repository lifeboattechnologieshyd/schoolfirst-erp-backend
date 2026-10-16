from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.models import Leave, StudentAttendance
from apps.school.models.school import Student
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.utils.logger import application_logger


class StudentLeaveRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school = request.school

        student_id = request.data.get("student_id")
        leave_type = request.data.get("leave_type", "CASUAL")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        duration = request.data.get("duration", "FULL_DAY")
        reason = request.data.get("reason")
        pdf = request.data.get("pdf")

        if not all([
            student_id,
            start_date,
            end_date,
            reason,
        ]):
            return CustomResponse.errorResponse(
                description="Student, dates, and reason are required."
            )

        # Validate leave type.
        if leave_type not in Leave.LeaveType.values:
            return CustomResponse.errorResponse(
                description="Invalid leave type."
            )

        # Validate duration.
        if duration not in Leave.LeaveDuration.values:
            return CustomResponse.errorResponse(
                description="Invalid leave duration."
            )

        # Parse dates.
        try:
            start_date = date.fromisoformat(start_date)
            end_date = date.fromisoformat(end_date)
        except (ValueError, TypeError):
            return CustomResponse.errorResponse(
                description="Invalid date format. Use YYYY-MM-DD."
            )

        if end_date < start_date:
            return CustomResponse.errorResponse(
                description="End date cannot be before start date."
            )

        if start_date < timezone.localdate():
            return CustomResponse.errorResponse(
                description="Leave cannot start in the past."
            )

        if duration == Leave.LeaveDuration.HALF_DAY and start_date != end_date:
            return CustomResponse.errorResponse(
                description="Half-day leave must be for a single date."
            )

        if not reason.strip():
            return CustomResponse.errorResponse(
                description="Leave reason cannot be empty."
            )


        student = Student.objects.filter(
            id=student_id,
            school=school,
        ).first()

        if not student:
            return CustomResponse.errorResponse(
                description="Student not found "
            )

        # Calculate requested leave days.
        total_days = (
            Decimal("0.5")
            if duration == Leave.LeaveDuration.HALF_DAY
            else Decimal((end_date - start_date).days + 1)
        )

        try:
            with transaction.atomic():
                leave = Leave.objects.create(
                    school=school,
                    branch=getattr(student, "branch", None),
                    applicant_type=Leave.ApplicantType.STUDENT,
                    student=student,
                    staff=None,
                    leave_type=leave_type,
                    start_date=start_date,
                    end_date=end_date,
                    duration=duration,
                    total_days=total_days,
                    reason=reason.strip(),
                    pdf=pdf,
                    status=Leave.LeaveStatus.PENDING,
                    created_by=request.user,
                )

            application_logger.info(
                "student_leave_request_created",
                leave_id=str(leave.id),
                student_id=str(student.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "leave_id": str(leave.id),
                    "student_id": str(student.id),
                    "student_name": student.name,
                    "leave_type": leave.leave_type,
                    "start_date": str(leave.start_date),
                    "end_date": str(leave.end_date),
                    "duration": leave.duration,
                    "total_days": str(leave.total_days),
                    "reason": leave.reason,
                    "pdf": leave.pdf,
                    "status": leave.status,
                },
                description="Student leave request submitted successfully."
            )

        except Exception:
            application_logger.exception(
                "student_leave_request_creation_failed",
                student_id=str(student.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to submit leave request."
            )

class StudentAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        student_id = request.query_params.get("student_id")
        month = request.query_params.get("month")
        year = request.query_params.get("year")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        status = request.query_params.get("status")

        if not student_id:
            return CustomResponse.errorResponse(
                description="Student ID is required."
            )


        student = Student.objects.filter(
            id=student_id,
            school=school,
        ).first()

        if not student:
            return CustomResponse.errorResponse(
                description="Student not found "
            )

        attendance = StudentAttendance.objects.filter(
            school=student.school,
            student=student,
        ).select_related(
            "grade",
            "section",
            "branch",
        )

        # Filter by month and year.
        if month or year:
            if not month or not year:
                return CustomResponse.errorResponse(
                    description="Both month and year are required."
                )

            try:
                month = int(month)
                year = int(year)

                if not 1 <= month <= 12:
                    raise ValueError

                if not 1900 <= year <= 9999:
                    raise ValueError

                first_day = date(year, month, 1)
                last_day = date(
                    year,
                    month,
                    monthrange(year, month)[1],
                )

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid month or year."
                )

            attendance = attendance.filter(
                attendance_date__gte=first_day,
                attendance_date__lte=last_day,
            )

        # Custom date range.
        if start_date:
            parsed_start_date = parse_date(start_date)

            if not parsed_start_date:
                return CustomResponse.errorResponse(
                    description="Invalid start_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date__gte=parsed_start_date
            )

        if end_date:
            parsed_end_date = parse_date(end_date)

            if not parsed_end_date:
                return CustomResponse.errorResponse(
                    description="Invalid end_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date__lte=parsed_end_date
            )

        if (
            start_date
            and end_date
            and parse_date(start_date) > parse_date(end_date)
        ):
            return CustomResponse.errorResponse(
                description="Start date cannot be after end date."
            )

        # Filter by attendance status.
        if status:
            if status not in StudentAttendance.AttendanceStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid attendance status."
                )

            attendance = attendance.filter(status=status)

        # Calculate summary for the selected filters.
        summary = attendance.aggregate(
            total_days=Count("id"),
            present_days=Count(
                "id",
                filter=Q(status="PRESENT"),
            ),
            absent_days=Count(
                "id",
                filter=Q(status="ABSENT"),
            ),
            late_days=Count(
                "id",
                filter=Q(status="LATE"),
            ),
            half_days=Count(
                "id",
                filter=Q(status="HALF_DAY"),
            ),
            leave_days=Count(
                "id",
                filter=Q(status="LEAVE"),
            ),
        )

        # Exclude approved leave and unmarked days from the
        # attendance percentage denominator.
        eligible_days = (
            summary["present_days"]
            + summary["absent_days"]
            + summary["late_days"]
            + summary["half_days"]
        )

        # Count PRESENT and LATE as attended days.
        attended_days = (
            summary["present_days"]
            + summary["late_days"]
        )

        summary["attendance_percentage"] = (
            round(attended_days / eligible_days * 100, 2)
            if eligible_days
            else 0
        )

        # Paginate daily attendance records.
        attendance = attendance.order_by("-attendance_date")

        paginator = CustomPageNumberPagination()
        paginated_attendance = paginator.paginate_queryset(
            attendance,
            request,
        )

        data = []

        for record in paginated_attendance:
            data.append({
                "attendance_id": str(record.id),
                "attendance_date": str(record.attendance_date),
                "status": record.status,
                "remarks": record.remarks,
                "grade": str(record.grade),
                "section": str(record.section),
            })

        return CustomResponse.successResponse(
            data={
                "student": {
                    "student_id": str(student.id),
                    "student_name": student.name,
                },
                "summary": summary,
                "attendance": data,
            },
            total=paginator.page.paginator.count,
            description="Student attendance fetched successfully.",
        )
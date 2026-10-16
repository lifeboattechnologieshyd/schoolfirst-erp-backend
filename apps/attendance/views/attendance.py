from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.models import Leave, StudentAttendance, LeaveDay
from apps.school.models.school import Student
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.utils.logger import application_logger


class StudentLeaveRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school = request.school

        student_id = request.data.get("student_id")
        leave_type = request.data.get("leave_type", "CASUAL")
        leave_days_data = request.data.get("leave_days", [])
        reason = request.data.get("reason")
        pdf = request.data.get("pdf")

        if not all([student_id, leave_days_data, reason]):
            return CustomResponse.errorResponse(
                description="Student, leave dates, and reason are required."
            )

        if not isinstance(leave_days_data, list):
            return CustomResponse.errorResponse(
                description="leave_days must be a list."
            )

        if leave_type not in Leave.LeaveType.values:
            return CustomResponse.errorResponse(
                description="Invalid leave type."
            )

        if not isinstance(reason, str) or not reason.strip():
            return CustomResponse.errorResponse(
                description="Leave reason cannot be empty."
            )

        today = timezone.localdate()
        seen_dates = set()
        validated_days = []
        total_days = Decimal("0.0")

        # Validate individual leave dates.
        for item in leave_days_data:
            if not isinstance(item, dict):
                return CustomResponse.errorResponse(
                    description="Each leave day must be an object."
                )

            leave_date = parse_date(item.get("date", ""))
            duration = item.get("duration")

            if not leave_date:
                return CustomResponse.errorResponse(
                    description="Invalid leave date. Use YYYY-MM-DD."
                )

            if leave_date < today:
                return CustomResponse.errorResponse(
                    description="Leave cannot start in the past."
                )

            if leave_date in seen_dates:
                return CustomResponse.errorResponse(
                    description=f"Duplicate leave date: {leave_date}."
                )

            if duration not in LeaveDay.Duration.values:
                return CustomResponse.errorResponse(
                    description=(
                        f"Invalid duration for {leave_date}. "
                        "Use FULL_DAY or HALF_DAY."
                    )
                )

            seen_dates.add(leave_date)

            days = (
                Decimal("1.0")
                if duration == LeaveDay.Duration.FULL_DAY
                else Decimal("0.5")
            )

            total_days += days

            validated_days.append({
                "leave_date": leave_date,
                "duration": duration,
            })

        # Sort dates chronologically.
        validated_days.sort(key=lambda item: item["leave_date"])

        start_date = validated_days[0]["leave_date"]
        end_date = validated_days[-1]["leave_date"]

        # Validate student.
        student = Student.objects.filter(
            id=student_id,
            school=school,
        ).first()

        if not student:
            return CustomResponse.errorResponse(
                description="Student not found."
            )

        try:
            with transaction.atomic():

                # Create the main leave request.
                leave = Leave.objects.create(
                    school=school,
                    branch=getattr(student, "branch", None),
                    applicant_type=Leave.ApplicantType.STUDENT,
                    student=student,
                    staff=None,
                    leave_type=leave_type,
                    start_date=start_date,
                    end_date=end_date,
                    total_days=total_days,
                    reason=reason.strip(),
                    pdf=pdf,
                    status=Leave.LeaveStatus.PENDING,
                    created_by=request.user,
                )

                # Create individual leave-day records.
                LeaveDay.objects.bulk_create([
                    LeaveDay(
                        leave=leave,
                        leave_date=item["leave_date"],
                        duration=item["duration"],
                        created_by=request.user,
                    )
                    for item in validated_days
                ])

            application_logger.info(
                "student_leave_request_created",
                leave_id=str(leave.id),
                student_id=str(student.id),
                school_id=str(school.id),
                total_days=str(total_days),
            )

            return CustomResponse.successResponse(
                data={
                    "leave_id": str(leave.id),
                    "student_id": str(student.id),
                    "student_name": student.name,
                    "leave_type": leave.leave_type,
                    "start_date": str(leave.start_date),
                    "end_date": str(leave.end_date),
                    "leave_days": [
                        {
                            "date": str(item["leave_date"]),
                            "duration": item["duration"],
                            "days": str(
                                Decimal("1.0")
                                if item["duration"] == LeaveDay.Duration.FULL_DAY
                                else Decimal("0.5")
                            ),
                        }
                        for item in validated_days
                    ],
                    "total_days": str(leave.total_days),
                    "reason": leave.reason,
                    "pdf": leave.pdf,
                    "status": leave.status,
                },
                description="Student leave request submitted successfully.",
            )

        except Exception:
            application_logger.exception(
                "student_leave_request_creation_failed",
                student_id=str(student.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to submit student leave request."
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
                description="Student not found."
            )

        # Validate month and year.
        first_day = None
        last_day = None

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

        # Validate custom date range.
        parsed_start_date = None
        parsed_end_date = None

        if start_date:
            parsed_start_date = parse_date(start_date)

            if not parsed_start_date:
                return CustomResponse.errorResponse(
                    description="Invalid start_date. Use YYYY-MM-DD."
                )

        if end_date:
            parsed_end_date = parse_date(end_date)

            if not parsed_end_date:
                return CustomResponse.errorResponse(
                    description="Invalid end_date. Use YYYY-MM-DD."
                )

        if (
            parsed_start_date
            and parsed_end_date
            and parsed_start_date > parsed_end_date
        ):
            return CustomResponse.errorResponse(
                description="Start date cannot be after end date."
            )

        if status and status not in StudentAttendance.AttendanceStatus.values:
            return CustomResponse.errorResponse(
                description="Invalid attendance status."
            )

        # Base attendance queryset.
        attendance = StudentAttendance.objects.filter(
            school=school,
            student=student,
        ).select_related(
            "grade",
            "section",
            "branch",
        )

        # Apply date filters to both summary and attendance history.
        if first_day and last_day:
            attendance = attendance.filter(
                attendance_date__range=(first_day, last_day)
            )

        if parsed_start_date:
            attendance = attendance.filter(
                attendance_date__gte=parsed_start_date
            )

        if parsed_end_date:
            attendance = attendance.filter(
                attendance_date__lte=parsed_end_date
            )

        # Calculate summary BEFORE applying the status filter.
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

        # Exclude full-day leave from the denominator.
        eligible_days = (
            summary["present_days"]
            + summary["absent_days"]
            + summary["late_days"]
            + summary["half_days"]
        )

        attended_days = (
            summary["present_days"]
            + summary["late_days"]
        )

        summary["attendance_percentage"] = (
            round(attended_days / eligible_days * 100, 2)
            if eligible_days
            else 0
        )

        # Apply status filter only to the returned history.
        if status:
            attendance = attendance.filter(status=status)

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
from calendar import monthrange
from datetime import date
from decimal import Decimal
from tkinter.constants import ACTIVE
from uuid import UUID

from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.models import Leave, StudentAttendance, LeaveDay
from apps.school.models.school import Student, AcademicYear
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
        note = request.data.get("note")
        if isinstance(note, str):
            note = note.strip() or None

        # -----------------------------
        # Basic validation
        # -----------------------------
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

        # -----------------------------
        # Validate leave days
        # -----------------------------
        today = timezone.localdate()
        seen_dates = set()
        validated_days = []
        total_days = Decimal("0.0")

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
                    description=f"Leave date {leave_date} cannot be in the past."
                )

            # Duplicate dates inside the same request
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

        # Sort chronologically
        validated_days.sort(
            key=lambda item: item["leave_date"]
        )

        start_date = validated_days[0]["leave_date"]
        end_date = validated_days[-1]["leave_date"]

        # -----------------------------
        # Validate student
        # -----------------------------
        student = Student.objects.filter(
            id=student_id,
            school=school,
        ).first()

        if not student:
            return CustomResponse.errorResponse(
                description="Student not found."
            )

        requested_dates = [
            item["leave_date"]
            for item in validated_days
        ]

        try:
            with transaction.atomic():

                # -----------------------------
                # Check existing leave
                # -----------------------------
                existing_leave_days = LeaveDay.objects.filter(
                    leave__school=school,
                    leave__student=student,
                    leave__applicant_type=Leave.ApplicantType.STUDENT,
                    leave__status__in=[
                        Leave.LeaveStatus.PENDING,
                        Leave.LeaveStatus.APPROVED,
                    ],
                    leave_date__in=requested_dates,
                ).values_list(
                    "leave_date",
                    flat=True,
                ).distinct()

                if existing_leave_days.exists():

                    duplicate_dates = sorted(
                        str(date)
                        for date in existing_leave_days
                    )

                    return CustomResponse.errorResponse(
                        description=(
                            "Leave already exists for the following dates: "
                            f"{', '.join(duplicate_dates)}."
                        )
                    )

                # -----------------------------
                # Create main leave
                # -----------------------------
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
                    note = note,
                    pdf=pdf,
                    status=Leave.LeaveStatus.PENDING,
                    created_by=request.user,
                )

                # -----------------------------
                # Create leave days
                # -----------------------------
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
                                if item["duration"]
                                == LeaveDay.Duration.FULL_DAY
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



class StudentLeaveLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        student_id = request.GET.get("student_id")
        status = request.GET.get("status")
        leave_type = request.GET.get("leave_type")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        try:
            # -----------------------------
            # Base queryset
            # -----------------------------
            leaves = Leave.objects.filter(
                school=school,
                applicant_type=Leave.ApplicantType.STUDENT,
            ).select_related(
                "student",
                "branch",
                "reviewed_by",
            ).prefetch_related(
                "leave_days"
            ).order_by("-created_at")

            # -----------------------------
            # Filters
            # -----------------------------
            if student_id:
                leaves = leaves.filter(student_id=student_id)

            if status:
                if status not in Leave.LeaveStatus.values:
                    return CustomResponse.errorResponse(
                        description="Invalid leave status."
                    )

                leaves = leaves.filter(status=status)

            if leave_type:
                if leave_type not in Leave.LeaveType.values:
                    return CustomResponse.errorResponse(
                        description="Invalid leave type."
                    )

                leaves = leaves.filter(leave_type=leave_type)

            # -----------------------------
            # Date filters
            # -----------------------------
            if start_date:
                parsed_start_date = parse_date(start_date)

                if not parsed_start_date:
                    return CustomResponse.errorResponse(
                        description="Invalid start_date. Use YYYY-MM-DD."
                    )

                leaves = leaves.filter(
                    end_date__gte=parsed_start_date
                )

            if end_date:
                parsed_end_date = parse_date(end_date)

                if not parsed_end_date:
                    return CustomResponse.errorResponse(
                        description="Invalid end_date. Use YYYY-MM-DD."
                    )

                leaves = leaves.filter(
                    start_date__lte=parsed_end_date
                )

            # -----------------------------
            # Prepare response
            # -----------------------------
            data = []

            for leave in leaves:

                leave_days = []

                for leave_day in leave.leave_days.all():

                    days = (
                        Decimal("1.0")
                        if leave_day.duration
                        == LeaveDay.Duration.FULL_DAY
                        else Decimal("0.5")
                    )

                    leave_days.append({
                        "id": str(leave_day.id),
                        "date": str(leave_day.leave_date),
                        "duration": leave_day.duration,
                        "days": str(days),
                    })

                reviewed_by = None

                if leave.reviewed_by:
                    reviewed_by = {
                        "id": str(leave.reviewed_by.id),
                        "name": leave.reviewed_by.name,
                    }

                data.append({
                    "leave_id": str(leave.id),

                    "student": {
                        "id": str(leave.student.id),
                        "name": leave.student.name,
                        "admission_number": getattr(
                            leave.student,
                            "admission_number",
                            None
                        ),
                    },

                    "branch": (
                        {
                            "id": str(leave.branch.id),
                            "name": leave.branch.name,
                        }
                        if leave.branch
                        else None
                    ),

                    "leave_type": leave.leave_type,

                    "start_date": str(leave.start_date),
                    "end_date": str(leave.end_date),

                    "leave_days": leave_days,

                    "total_days": str(leave.total_days),

                    "reason": leave.reason,
                    "note": leave.note,
                    "pdf": leave.pdf,

                    "status": leave.status,

                    "review_remarks": leave.review_remarks,

                    "reviewed_by": reviewed_by,

                    "reviewed_at": (
                        leave.reviewed_at.isoformat()
                        if leave.reviewed_at
                        else None
                    ),

                    "created_at": (
                        leave.created_at.isoformat()
                        if leave.created_at
                        else None
                    ),
                })

            return CustomResponse.successResponse(
                total=len(data),
                data={
                    "data": data,
                },
                description="Student leave requests fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "student_leave_list_failed",
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch student leave requests."
            )




class StudentAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            school = request.school

            student_id = request.query_params.get("student_id")
            month = request.query_params.get("month")
            year = request.query_params.get("year")
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")
            status = request.query_params.get("status")

            trend_start_date = request.query_params.get(
                "trend_start_date"
            )
            trend_end_date = request.query_params.get(
                "trend_end_date"
            )

            # ---------------------------------------------------------
            # Validate student_id
            # ---------------------------------------------------------
            if not student_id:
                return CustomResponse.errorResponse(
                    description="student_id is required."
                )

            try:
                student_uuid = UUID(student_id)
            except ValueError:
                return CustomResponse.errorResponse(
                    description="Invalid student_id."
                )

            # ---------------------------------------------------------
            # Get student
            # ---------------------------------------------------------
            student = (
                Student.objects.filter(
                    id=student_uuid,
                    school=school,
                    status=Student.Status.ACTIVE,
                )
                .select_related(
                    "grade",
                    "section",
                    "branch",
                )
                .first()
            )

            if not student:
                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            # ---------------------------------------------------------
            # Base attendance queryset
            # ---------------------------------------------------------
            attendance = (
                StudentAttendance.objects.filter(
                    school=school,
                    student=student,
                )
                .select_related(
                    "student",
                    "grade",
                    "section",
                    "branch",
                    "created_by",
                )
            )

            # ---------------------------------------------------------
            # Month filter
            # ---------------------------------------------------------
            parsed_month = None

            if month:
                try:
                    parsed_month = int(month)
                except ValueError:
                    return CustomResponse.errorResponse(
                        description="Invalid month."
                    )

                if parsed_month < 1 or parsed_month > 12:
                    return CustomResponse.errorResponse(
                        description="Month must be between 1 and 12."
                    )

                attendance = attendance.filter(
                    attendance_date__month=parsed_month
                )

            # ---------------------------------------------------------
            # Year filter
            # ---------------------------------------------------------
            parsed_year = None

            if year:
                try:
                    parsed_year = int(year)
                except ValueError:
                    return CustomResponse.errorResponse(
                        description="Invalid year."
                    )

                attendance = attendance.filter(
                    attendance_date__year=parsed_year
                )

            # ---------------------------------------------------------
            # Start / End date filter
            # ---------------------------------------------------------
            parsed_start_date = None
            parsed_end_date = None

            if start_date:
                parsed_start_date = parse_date(start_date)

                if not parsed_start_date:
                    return CustomResponse.errorResponse(
                        description=(
                            "Invalid start_date. "
                            "Use YYYY-MM-DD."
                        )
                    )

                attendance = attendance.filter(
                    attendance_date__gte=parsed_start_date
                )

            if end_date:
                parsed_end_date = parse_date(end_date)

                if not parsed_end_date:
                    return CustomResponse.errorResponse(
                        description=(
                            "Invalid end_date. "
                            "Use YYYY-MM-DD."
                        )
                    )

                attendance = attendance.filter(
                    attendance_date__lte=parsed_end_date
                )

            if (
                parsed_start_date
                and parsed_end_date
                and parsed_start_date > parsed_end_date
            ):
                return CustomResponse.errorResponse(
                    description=(
                        "start_date cannot be greater than "
                        "end_date."
                    )
                )

            # ---------------------------------------------------------
            # Status filter
            # ---------------------------------------------------------
            if status:
                valid_statuses = [
                    choice[0]
                    for choice in StudentAttendance.STATUS_CHOICES
                ]

                if status not in valid_statuses:
                    return CustomResponse.errorResponse(
                        description=(
                            "Invalid status. "
                            f"Allowed values: "
                            f"{', '.join(valid_statuses)}."
                        )
                    )

                attendance = attendance.filter(
                    status=status
                )

            # ---------------------------------------------------------
            # Attendance records
            # ---------------------------------------------------------
            attendance_records = attendance.order_by(
                "-attendance_date",
                "-created_at",
            )

            # =========================================================
            # SUMMARY
            # =========================================================

            summary_queryset = StudentAttendance.objects.filter(
                school=school,
                student=student,
            )

            if parsed_start_date:
                summary_queryset = summary_queryset.filter(
                    attendance_date__gte=parsed_start_date
                )

            if parsed_end_date:
                summary_queryset = summary_queryset.filter(
                    attendance_date__lte=parsed_end_date
                )

            if parsed_month:
                summary_queryset = summary_queryset.filter(
                    attendance_date__month=parsed_month
                )

            if parsed_year:
                summary_queryset = summary_queryset.filter(
                    attendance_date__year=parsed_year
                )

            total_days = summary_queryset.count()

            present_count = summary_queryset.filter(
                status=StudentAttendance.Status.PRESENT
            ).count()

            absent_count = summary_queryset.filter(
                status=StudentAttendance.Status.ABSENT
            ).count()

            late_count = summary_queryset.filter(
                status=StudentAttendance.Status.LATE
            ).count()

            leave_count = summary_queryset.filter(
                status=StudentAttendance.Status.LEAVE
            ).count()

            half_day_count = summary_queryset.filter(
                status=StudentAttendance.Status.HALF_DAY
            ).count()

            # Leave is excluded from eligible days.
            eligible_days = (
                present_count
                + absent_count
                + late_count
                + half_day_count
            )

            attended_days = (
                present_count
                + late_count
                + (half_day_count * 0.5)
            )

            attendance_percentage = (
                round(
                    (attended_days / eligible_days) * 100,
                    2,
                )
                if eligible_days
                else 0
            )

            summary = {
                "total_days": total_days,
                "present": present_count,
                "absent": absent_count,
                "late": late_count,
                "leave": leave_count,
                "half_day": half_day_count,
                "eligible_days": eligible_days,
                "attended_days": attended_days,
                "attendance_percentage": attendance_percentage,
            }

            # =========================================================
            # CURRENT ACADEMIC YEAR
            # =========================================================

            today = timezone.localdate()

            academic_year = (
                AcademicYear.objects.filter(
                    school=school,
                    status=AcademicYear.Status.ACTIVE,
                    start_date__lte=today,
                    end_date__gte=today,
                )
                .order_by("-start_date")
                .first()
            )

            if not academic_year:
                return CustomResponse.errorResponse(
                    description="Active academic year not found."
                )

            # =========================================================
            # MONTHLY TREND
            # =========================================================

            # By default, use the school's academic year.
            parsed_trend_start = academic_year.start_date
            parsed_trend_end = min(
                academic_year.end_date,
                today,
            )

            # Allow frontend to override the trend range.
            if trend_start_date:
                parsed_trend_start = parse_date(
                    trend_start_date
                )

                if not parsed_trend_start:
                    return CustomResponse.errorResponse(
                        description=(
                            "Invalid trend_start_date. "
                            "Use YYYY-MM-DD."
                        )
                    )

            if trend_end_date:
                parsed_trend_end = parse_date(
                    trend_end_date
                )

                if not parsed_trend_end:
                    return CustomResponse.errorResponse(
                        description=(
                            "Invalid trend_end_date. "
                            "Use YYYY-MM-DD."
                        )
                    )

            if parsed_trend_start > parsed_trend_end:
                return CustomResponse.errorResponse(
                    description=(
                        "trend_start_date cannot be greater "
                        "than trend_end_date."
                    )
                )

            # ---------------------------------------------------------
            # Trend attendance query
            # ---------------------------------------------------------
            trend_attendance = StudentAttendance.objects.filter(
                school=school,
                student=student,
                attendance_date__gte=parsed_trend_start,
                attendance_date__lte=parsed_trend_end,
            )

            monthly_summary = (
                trend_attendance
                .annotate(
                    month=TruncMonth("attendance_date")
                )
                .values("month")
                .annotate(
                    total_records=Count("id"),

                    present=Count(
                        "id",
                        filter=Q(
                            status=StudentAttendance.Status.PRESENT
                        ),
                    ),

                    absent=Count(
                        "id",
                        filter=Q(
                            status=StudentAttendance.Status.ABSENT
                        ),
                    ),

                    late=Count(
                        "id",
                        filter=Q(
                            status=StudentAttendance.Status.LATE
                        ),
                    ),

                    leave=Count(
                        "id",
                        filter=Q(
                            status=StudentAttendance.Status.LEAVE
                        ),
                    ),

                    half_day=Count(
                        "id",
                        filter=Q(
                            status=StudentAttendance.Status.HALF_DAY
                        ),
                    ),
                )
                .order_by("month")
            )

            monthly_trend = []

            for item in monthly_summary:
                month_present = item["present"]
                month_absent = item["absent"]
                month_late = item["late"]
                month_leave = item["leave"]
                month_half_day = item["half_day"]

                month_attended_units = (
                    month_present
                    + month_late
                    + (month_half_day * 0.5)
                )

                month_eligible_days = (
                    month_present
                    + month_absent
                    + month_late
                    + month_half_day
                )

                month_percentage = (
                    round(
                        (
                            month_attended_units
                            / month_eligible_days
                        ) * 100,
                        2,
                    )
                    if month_eligible_days
                    else 0
                )

                monthly_trend.append(
                    {
                        "month": item["month"].strftime("%b"),
                        "year": item["month"].year,
                        "total_attendance_records": (
                            item["total_records"]
                        ),
                        "present": month_present,
                        "absent": month_absent,
                        "late": month_late,
                        "leave": month_leave,
                        "half_day": month_half_day,
                        "attendance_percentage": month_percentage,
                    }
                )

            # =========================================================
            # ATTENDANCE HISTORY
            # =========================================================

            attendance_data = []

            for record in attendance_records:
                created_by = None

                if (
                    record.created_by_id
                    and record.created_by
                ):
                    if hasattr(
                        record.created_by,
                        "get_full_name",
                    ):
                        created_by_name = (
                            record.created_by.get_full_name()
                        )
                    elif hasattr(
                        record.created_by,
                        "name",
                    ):
                        created_by_name = (
                            record.created_by.name
                        )
                    else:
                        created_by_name = str(
                            record.created_by
                        )

                    created_by = {
                        "id": str(record.created_by_id),
                        "name": created_by_name,
                    }

                attendance_data.append(
                    {
                        "id": str(record.id),

                        "attendance_date": (
                            record.attendance_date.isoformat()
                            if record.attendance_date
                            else None
                        ),

                        "status": record.status,

                        "student": {
                            "id": str(record.student_id),
                            "name": record.student.name,
                            "admission_number": (
                                record.student.admission_number
                            ),
                        },

                        "grade": (
                            {
                                "id": str(record.grade_id),
                                "name": record.grade.name,
                            }
                            if record.grade
                            else None
                        ),

                        "section": (
                            {
                                "id": str(record.section_id),
                                "name": record.section.name,
                            }
                            if record.section
                            else None
                        ),

                        "branch": (
                            {
                                "id": str(record.branch_id),
                                "name": record.branch.name,
                            }
                            if record.branch
                            else None
                        ),

                        "remarks": record.remarks,

                        "created_at": (
                            record.created_at.isoformat()
                            if record.created_at
                            else None
                        ),

                        "created_by": created_by,
                    }
                )

            # =========================================================
            # FINAL RESPONSE
            # =========================================================

            data = {
                "student": {
                    "id": str(student.id),
                    "name": student.name,
                    "admission_number": (
                        student.admission_number
                    ),

                    "grade": (
                        {
                            "id": str(student.grade_id),
                            "name": student.grade.name,
                        }
                        if student.grade
                        else None
                    ),

                    "section": (
                        {
                            "id": str(student.section_id),
                            "name": student.section.name,
                        }
                        if student.section
                        else None
                    ),

                    "branch": (
                        {
                            "id": str(student.branch_id),
                            "name": student.branch.name,
                        }
                        if student.branch
                        else None
                    ),
                },

                "academic_year": {
                    "id": str(academic_year.id),
                    "name": academic_year.name,
                    "start_date": (
                        academic_year.start_date.isoformat()
                    ),
                    "end_date": (
                        academic_year.end_date.isoformat()
                    ),
                },

                "summary": summary,

                "monthly_trend": monthly_trend,

                "attendance": attendance_data,
            }

            application_logger.info(
                "Student attendance details fetched successfully. "
                "student_id=%s school_id=%s",
                student_id,
                school.id,
            )

            return CustomResponse.successResponse(
                data=data,
                description=(
                    "Student attendance fetched successfully."
                ),
            )

        except Exception as e:
            application_logger.exception(
                "Error fetching student attendance. "
                "student_id=%s error=%s",
                request.query_params.get("student_id"),
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to fetch student attendance."
                )
            )
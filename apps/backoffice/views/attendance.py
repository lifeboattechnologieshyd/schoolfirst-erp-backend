import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Prefetch, Max
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.models import StudentAttendance, StaffAttendance, Leave, LeaveDay
from apps.school.models.school import Grade, Section, Student, Staff, Branch
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class BulkMarkStudentAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_attendance.create"

    def post(self, request):
        school = request.school

        grade_id = request.data.get("grade_id")
        section_id = request.data.get("section_id")
        attendance_date_input = request.data.get("attendance_date")
        students_data = request.data.get("students")

        application_logger.info(
            "bulk_student_attendance_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            grade_id=grade_id,
            section_id=section_id,
            attendance_date=attendance_date_input,
        )

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        staff = Staff.objects.filter(
            user=request.user,
            school=school,
            status=Staff.Status.ACTIVE,
        ).first()

        if staff is None:
            return CustomResponse.errorResponse(
                description="Active staff record not found for this user."
            )

        required_fields = {
            "grade_id": grade_id,
            "section_id": section_id,
            "attendance_date": attendance_date_input,
            "students": students_data,
        }

        for field, value in required_fields.items():
            if value is None or value == "":
                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        if not isinstance(students_data, list) or not students_data:
            return CustomResponse.errorResponse(
                description="Students must be a non-empty list."
            )

        try:
            grade_uuid = uuid.UUID(str(grade_id))
            section_uuid = uuid.UUID(str(section_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid grade or section ID."
            )

        attendance_date = parse_date(str(attendance_date_input))

        if attendance_date is None:
            return CustomResponse.errorResponse(
                description="Invalid attendance date. Use YYYY-MM-DD."
            )

        if attendance_date > timezone.localdate():
            return CustomResponse.errorResponse(
                description="Attendance date cannot be in the future."
            )

        grade = Grade.objects.filter(
            id=grade_uuid,
            school=school,
        ).first()

        if grade is None:
            return CustomResponse.errorResponse(
                description="Grade not found."
            )

        section = Section.objects.filter(
            id=section_uuid,
        ).first()

        if section is None:
            return CustomResponse.errorResponse(
                description="Section not found."
            )

        # Validate the selected section belongs to the selected grade.
        # Adjust these fields if your Section model uses another relationship.
        if (
            hasattr(section, "grade_id")
            and section.grade_id != grade.id
        ):
            return CustomResponse.errorResponse(
                description="Section does not belong to the selected grade."
            )

        validated_students = []
        seen_student_ids = set()

        for index, item in enumerate(students_data):
            if not isinstance(item, dict):
                return CustomResponse.errorResponse(
                    description=f"Invalid student data at index {index}."
                )

            student_id = item.get("student_id")
            status = item.get("status")

            if not student_id:
                return CustomResponse.errorResponse(
                    description=f"Student ID is required at index {index}."
                )

            if status not in StudentAttendance.AttendanceStatus.values:
                return CustomResponse.errorResponse(
                    description=f"Invalid attendance status at index {index}."
                )

            try:
                student_uuid = uuid.UUID(str(student_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description=f"Invalid student ID at index {index}."
                )

            if student_uuid in seen_student_ids:
                return CustomResponse.errorResponse(
                    description=f"Duplicate student ID: {student_id}."
                )

            seen_student_ids.add(student_uuid)

            validated_students.append({
                "student_id": student_uuid,
                "status": status,
                "remarks": item.get("remarks"),
            })

        student_ids = [
            item["student_id"]
            for item in validated_students
        ]

        students = Student.objects.filter(
            id__in=student_ids,
            school=school,
        )

        students_by_id = {
            student.id: student
            for student in students
        }

        if len(students_by_id) != len(student_ids):
            return CustomResponse.errorResponse(
                description="One or more students were not found in this school."
            )

        for item in validated_students:
            student = students_by_id[item["student_id"]]

            if student.section_id != section.id:
                return CustomResponse.errorResponse(
                    description=(
                        f"Student {student.id} does not belong "
                        "to the selected section."
                    )
                )

            if (
                hasattr(student, "grade_id")
                and student.grade_id != grade.id
            ):
                return CustomResponse.errorResponse(
                    description=(
                        f"Student {student.id} does not belong "
                        "to the selected grade."
                    )
                )

        updated_attendance_count = 0
        final_statuses = []

        try:
            with transaction.atomic():

                # Find approved leave for the exact attendance date.
                # Do not use start_date/end_date because leave dates
                # may be nonconsecutive.
                approved_leave_days = LeaveDay.objects.filter(
                    leave__school=school,
                    leave__applicant_type=Leave.ApplicantType.STUDENT,
                    leave__student_id__in=student_ids,
                    leave__status=Leave.LeaveStatus.APPROVED,
                    leave_date=attendance_date,
                ).select_related("leave")

                leave_by_student = {
                    leave_day.leave.student_id: leave_day
                    for leave_day in approved_leave_days
                }

                for item in validated_students:
                    student_id = item["student_id"]
                    attendance_status = item["status"]
                    remarks = item["remarks"]

                    approved_leave_day = leave_by_student.get(student_id)

                    # Approved full-day leave takes precedence over
                    # the attendance status submitted by the frontend.
                    if (
                        approved_leave_day
                        and approved_leave_day.duration
                        == LeaveDay.Duration.FULL_DAY
                    ):
                        attendance_status = (
                            StudentAttendance.AttendanceStatus.LEAVE
                        )

                    # For approved half-day leave, preserve the submitted
                    # attendance status. LeaveDay records the partial leave.
                    attendance, created = (
                        StudentAttendance.objects.update_or_create(
                            school=school,
                            student_id=student_id,
                            attendance_date=attendance_date,
                            defaults={
                                "branch": staff.branch,
                                "grade": grade,
                                "section": section,
                                "status": attendance_status,
                                "remarks": remarks,
                                "marked_by": staff,
                            },
                        )
                    )

                    final_statuses.append(attendance.status)

                    if created:
                        updated_attendance_count += 1

        except Exception:
            application_logger.exception(
                "bulk_student_attendance_failed",
                school_id=str(school.id),
                grade_id=str(grade.id),
                section_id=str(section.id),
                attendance_date=str(attendance_date),
            )

            return CustomResponse.errorResponse(
                description="Failed to save student attendance."
            )

        attendance_summary = {
            status: final_statuses.count(status)
            for status in StudentAttendance.AttendanceStatus.values
        }

        application_logger.info(
            "bulk_student_attendance_marked",
            school_id=str(school.id),
            staff_id=str(staff.id),
            grade_id=str(grade.id),
            section_id=str(section.id),
            attendance_date=str(attendance_date),
            total_students=len(validated_students),
            created_attendance_count=updated_attendance_count,
        )

        return CustomResponse.successResponse(
            description="Student attendance saved successfully.",
            data={
                "grade_id": str(grade.id),
                "section_id": str(section.id),
                "attendance_date": str(attendance_date),
                "marked_by": {
                    "id": str(staff.id),
                    "name": staff.name,
                },
                "total_students": len(validated_students),
                "created_attendance_count": updated_attendance_count,
                "attendance_summary": attendance_summary,
            },
        )


class StudentAttendanceListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_attendance.view"

    def get(self, request):
        school = request.school

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        attendance = StudentAttendance.objects.filter(
            school=school,
        ).select_related(
            "student",
            "grade",
            "section",
            "branch",
            "marked_by",
        ).order_by(
            "-attendance_date",
            "student__name",
        )

        # Query parameters
        attendance_date = request.query_params.get("attendance_date")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        student_id = request.query_params.get("student_id")
        admission_number = request.query_params.get("admission_number")
        grade_id = request.query_params.get("grade_id")
        section_id = request.query_params.get("section_id")
        branch_id = request.query_params.get("branch_id")
        status = request.query_params.get("status")
        search = request.query_params.get("search")

        # Filter exact attendance date
        if attendance_date:
            parsed_date = parse_date(attendance_date)

            if parsed_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid attendance_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date=parsed_date
            )

        # Filter start date
        parsed_start_date = None
        parsed_end_date = None

        if start_date:
            parsed_start_date = parse_date(start_date)

            if parsed_start_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid start_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date__gte=parsed_start_date
            )

        # Filter end date
        if end_date:
            parsed_end_date = parse_date(end_date)

            if parsed_end_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid end_date. Use YYYY-MM-DD."
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
                description="start_date cannot be after end_date."
            )

        # Filter by student ID
        if student_id:
            try:
                student_uuid = uuid.UUID(str(student_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid student ID."
                )

            attendance = attendance.filter(
                student_id=student_uuid
            )

        # Filter by admission number
        if admission_number:
            attendance = attendance.filter(
                student__admission_number__iexact=admission_number.strip()
            )

        # Filter by grade
        if grade_id:
            try:
                grade_uuid = uuid.UUID(str(grade_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid grade ID."
                )

            attendance = attendance.filter(
                grade_id=grade_uuid
            )

        # Filter by section
        if section_id:
            try:
                section_uuid = uuid.UUID(str(section_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid section ID."
                )

            attendance = attendance.filter(
                section_id=section_uuid
            )

        # Filter by branch
        if branch_id:
            try:
                branch_uuid = uuid.UUID(str(branch_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid branch ID."
                )

            attendance = attendance.filter(
                branch_id=branch_uuid
            )

        # Filter by attendance status
        if status:
            if status not in StudentAttendance.AttendanceStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid attendance status."
                )

            attendance = attendance.filter(
                status=status
            )

        # Search by student name or admission number
        if search:
            attendance = attendance.filter(
                Q(student__name__icontains=search)
                | Q(student__admission_number__icontains=search)
            )

        # Get total before pagination
        total = attendance.count()

        # Pagination
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(
            attendance,
            request,
        )

        page_records = list(page)

        # Fetch approved leave days for students and dates
        approved_leave_days = []

        if page_records:
            page_student_ids = {
                item.student_id for item in page_records
            }

            page_dates = {
                item.attendance_date for item in page_records
            }

            approved_leave_days = LeaveDay.objects.filter(
                leave__school=school,
                leave__applicant_type=Leave.ApplicantType.STUDENT,
                leave__status=Leave.LeaveStatus.APPROVED,
                leave__student_id__in=page_student_ids,
                leave_date__in=page_dates,
            ).select_related(
                "leave"
            )

        # Map approved leave by student and date
        leave_days_by_student_date = {
            (
                leave_day.leave.student_id,
                leave_day.leave_date,
            ): leave_day
            for leave_day in approved_leave_days
        }

        # Build response
        data = []

        for item in page_records:
            leave_day = leave_days_by_student_date.get(
                (
                    item.student_id,
                    item.attendance_date,
                )
            )

            data.append({
                "id": str(item.id),

                "student": {
                    "id": str(item.student_id),
                    "admission_number": item.student.admission_number,
                    "name": item.student.name,
                },

                "grade": {
                    "id": str(item.grade_id),
                    "name": str(item.grade),
                },

                "section": {
                    "id": str(item.section_id),
                    "name": str(item.section),
                },

                "branch": {
                    "id": str(item.branch_id),
                    "name": str(item.branch),
                } if item.branch_id else None,

                "attendance_date": str(item.attendance_date),
                "status": item.status,
                "remarks": item.remarks,

                "approved_leave": leave_day is not None,

                "leave_duration": (
                    leave_day.duration
                    if leave_day
                    else None
                ),

                "marked_by": {
                    "id": str(item.marked_by_id),
                    "name": item.marked_by.name,
                } if item.marked_by_id else None,
            })

        application_logger.info(
            "student_attendance_list_fetched",
            school_id=str(school.id),
            requested_by=str(request.user.id),
            total=total,
        )

        return CustomResponse.successResponse(
            data=data,
            total=total,
            description="Student attendance fetched successfully.",
        )

class UpdateStudentAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_attendance.update"

    def put(self, request, attendance_id):
        school = request.school

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        # Validate attendance ID
        try:
            attendance_uuid = uuid.UUID(str(attendance_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid attendance ID."
            )

        # Get authenticated staff
        staff = Staff.objects.filter(
            user=request.user,
            school=school,
            status=Staff.Status.ACTIVE,
        ).first()

        if staff is None:
            return CustomResponse.errorResponse(
                description="Active staff record not found for this user."
            )

        # Validate request fields
        allowed_fields = {"status", "remarks"}
        invalid_fields = set(request.data.keys()) - allowed_fields

        if invalid_fields:
            return CustomResponse.errorResponse(
                description=(
                    f"Fields cannot be updated: "
                    f"{', '.join(sorted(invalid_fields))}."
                )
            )

        if not request.data:
            return CustomResponse.errorResponse(
                description="At least one field is required to update."
            )

        try:
            with transaction.atomic():

                # Lock the attendance record during the update.
                attendance = StudentAttendance.objects.select_for_update().filter(
                    id=attendance_uuid,
                    school=school,
                ).first()

                if attendance is None:
                    return CustomResponse.errorResponse(
                        description="Student attendance not found."
                    )

                # Validate status
                if "status" in request.data:
                    status = request.data.get("status")

                    if status not in StudentAttendance.AttendanceStatus.values:
                        return CustomResponse.errorResponse(
                            description="Invalid attendance status."
                        )

                    # Check approved leave for this exact date.
                    approved_leave_day = LeaveDay.objects.filter(
                        leave__school=school,
                        leave__student_id=attendance.student_id,
                        leave__applicant_type=Leave.ApplicantType.STUDENT,
                        leave__status=Leave.LeaveStatus.APPROVED,
                        leave_date=attendance.attendance_date,
                        duration=LeaveDay.Duration.FULL_DAY,
                    ).exists()

                    # Prevent overriding approved full-day leave.
                    if (
                        approved_leave_day
                        and status != StudentAttendance.AttendanceStatus.LEAVE
                    ):
                        return CustomResponse.errorResponse(
                            description=(
                                "Attendance cannot be changed because "
                                "the student has approved full-day leave."
                            )
                        )

                    attendance.status = status

                # Update remarks
                if "remarks" in request.data:
                    attendance.remarks = request.data.get("remarks")

                # Record the staff member making the correction
                attendance.marked_by = staff

                attendance.save(
                    update_fields=[
                        "status",
                        "remarks",
                        "marked_by",
                        "updated_at",
                        "updated_by",
                    ]
                )

        except Exception:
            application_logger.exception(
                "student_attendance_update_failed",
                school_id=str(school.id),
                attendance_id=str(attendance_uuid),
                updated_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update student attendance."
            )

        application_logger.info(
            "student_attendance_updated",
            school_id=str(school.id),
            attendance_id=str(attendance.id),
            student_id=str(attendance.student_id),
            status=attendance.status,
            updated_by=str(request.user.id),
        )

        return CustomResponse.successResponse(
            description="Student attendance updated successfully.",
            data={
                "id": str(attendance.id),
                "student_id": str(attendance.student_id),
                "student_name": attendance.student.name,
                "grade_id": str(attendance.grade_id),
                "section_id": str(attendance.section_id),
                "attendance_date": str(attendance.attendance_date),
                "status": attendance.status,
                "remarks": attendance.remarks,
                "marked_by": {
                    "id": str(staff.id),
                    "name": staff.name,
                },
            },
        )



class BulkMarkStaffAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "staff_attendance.create"

    def post(self, request):
        school = request.school

        attendance_date = request.data.get("attendance_date")
        staff_attendance = request.data.get("staff_attendance")

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        marked_by = Staff.objects.filter(
            user=request.user,
            school=school,
            status=Staff.Status.ACTIVE,
        ).first()

        if marked_by is None:
            return CustomResponse.errorResponse(
                description="Active staff record not found for this user."
            )

        if not attendance_date:
            return CustomResponse.errorResponse(
                description="Attendance date is required."
            )

        attendance_date = parse_date(str(attendance_date))

        if attendance_date is None:
            return CustomResponse.errorResponse(
                description="Invalid attendance date. Use YYYY-MM-DD."
            )

        if attendance_date > timezone.localdate():
            return CustomResponse.errorResponse(
                description="Attendance date cannot be in the future."
            )

        if not isinstance(staff_attendance, list) or not staff_attendance:
            return CustomResponse.errorResponse(
                description="Staff attendance must be a non-empty list."
            )

        validated_records = []
        seen_staff_ids = set()

        # Validate request data
        for index, item in enumerate(staff_attendance):
            if not isinstance(item, dict):
                return CustomResponse.errorResponse(
                    description=f"Invalid staff data at index {index}."
                )

            staff_id = item.get("staff_id")
            status = item.get("status")

            if not staff_id:
                return CustomResponse.errorResponse(
                    description=f"Staff ID is required at index {index}."
                )

            if status not in StaffAttendance.AttendanceStatus.values:
                return CustomResponse.errorResponse(
                    description=f"Invalid attendance status at index {index}."
                )

            try:
                staff_uuid = uuid.UUID(str(staff_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description=f"Invalid staff ID at index {index}."
                )

            if staff_uuid in seen_staff_ids:
                return CustomResponse.errorResponse(
                    description=f"Duplicate staff ID: {staff_id}."
                )

            seen_staff_ids.add(staff_uuid)

            check_in = item.get("check_in")
            check_out = item.get("check_out")

            if check_in:
                check_in = parse_time(str(check_in))

                if check_in is None:
                    return CustomResponse.errorResponse(
                        description=f"Invalid check-in time at index {index}."
                    )

            if check_out:
                check_out = parse_time(str(check_out))

                if check_out is None:
                    return CustomResponse.errorResponse(
                        description=f"Invalid check-out time at index {index}."
                    )

            if check_in and check_out and check_out <= check_in:
                return CustomResponse.errorResponse(
                    description=(
                        f"Check-out must be after check-in at index {index}."
                    )
                )

            validated_records.append({
                "staff_id": staff_uuid,
                "status": status,
                "check_in": check_in,
                "check_out": check_out,
                "remarks": item.get("remarks"),
            })

        # Fetch staff members in one query
        staff_ids = [
            item["staff_id"] for item in validated_records
        ]

        staff_members = Staff.objects.filter(
            id__in=staff_ids,
            school=school,
        )

        staff_by_id = {
            member.id: member for member in staff_members
        }

        if len(staff_by_id) != len(staff_ids):
            return CustomResponse.errorResponse(
                description=(
                    "One or more staff members were not found in this school."
                )
            )

        attendance_summary = {
            status: 0
            for status in StaffAttendance.AttendanceStatus.values
        }

        created_count = 0
        updated_count = 0

        try:
            with transaction.atomic():

                # Fetch approved leave for the selected staff and date.
                approved_leave_days = LeaveDay.objects.filter(
                    leave__school=school,
                    leave__applicant_type=Leave.ApplicantType.STAFF,
                    leave__staff_id__in=staff_ids,
                    leave__status=Leave.LeaveStatus.APPROVED,
                    leave_date=attendance_date,
                ).select_related("leave")

                leave_by_staff = {
                    leave_day.leave.staff_id: leave_day
                    for leave_day in approved_leave_days
                }

                for item in validated_records:
                    member = staff_by_id[item["staff_id"]]

                    status = item["status"]
                    check_in = item["check_in"]
                    check_out = item["check_out"]
                    remarks = item["remarks"]

                    leave_day = leave_by_staff.get(member.id)

                    if leave_day:
                        if (
                            leave_day.duration
                            == LeaveDay.Duration.FULL_DAY
                        ):
                            # Approved full-day leave takes precedence.
                            status = StaffAttendance.AttendanceStatus.LEAVE
                            check_in = None
                            check_out = None

                        elif (
                            leave_day.duration
                            == LeaveDay.Duration.HALF_DAY
                        ):
                            # Approved half-day leave is represented by
                            # the attendance HALF_DAY status.
                            status = StaffAttendance.AttendanceStatus.HALF_DAY

                    attendance, created = (
                        StaffAttendance.objects.update_or_create(
                            school=school,
                            staff=member,
                            attendance_date=attendance_date,
                            defaults={
                                "branch": member.branch,
                                "status": status,
                                "check_in": check_in,
                                "check_out": check_out,
                                "remarks": remarks,
                                "marked_by": marked_by,
                            },
                        )
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                    attendance_summary[attendance.status] += 1

        except Exception:
            application_logger.exception(
                "bulk_staff_attendance_failed",
                school_id=str(school.id),
                attendance_date=str(attendance_date),
            )

            return CustomResponse.errorResponse(
                description="Failed to save staff attendance."
            )

        application_logger.info(
            "bulk_staff_attendance_marked",
            school_id=str(school.id),
            marked_by=str(marked_by.id),
            attendance_date=str(attendance_date),
            total_staff=len(validated_records),
            created_count=created_count,
            updated_count=updated_count,
        )

        return CustomResponse.successResponse(
            description="Staff attendance saved successfully.",
            data={
                "attendance_date": str(attendance_date),
                "total_staff": len(validated_records),
                "created_count": created_count,
                "updated_count": updated_count,
                "marked_by": {
                    "id": str(marked_by.id),
                    "name": marked_by.name,
                },
                "attendance_summary": attendance_summary,
            },
        )


class StaffAttendanceListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "staff_attendance.view"

    def get(self, request):
        school = request.school

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        attendance = StaffAttendance.objects.filter(
            school=school,
        ).select_related(
            "staff",
            "branch",
            "marked_by",
        ).order_by(
            "-attendance_date",
            "staff__name",
        )

        attendance_date = request.query_params.get("attendance_date")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        staff_id = request.query_params.get("staff_id")
        branch_id = request.query_params.get("branch_id")
        status = request.query_params.get("status")
        search = request.query_params.get("search")

        # Exact attendance date
        if attendance_date:
            parsed_date = parse_date(attendance_date)

            if parsed_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid attendance_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date=parsed_date
            )

        # Date range
        parsed_start_date = None
        parsed_end_date = None

        if start_date:
            parsed_start_date = parse_date(start_date)

            if parsed_start_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid start_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date__gte=parsed_start_date
            )

        if end_date:
            parsed_end_date = parse_date(end_date)

            if parsed_end_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid end_date. Use YYYY-MM-DD."
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
                description="start_date cannot be after end_date."
            )

        # Filter by staff
        if staff_id:
            try:
                staff_uuid = uuid.UUID(str(staff_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid staff ID."
                )

            attendance = attendance.filter(
                staff_id=staff_uuid
            )

        # Filter by branch
        if branch_id:
            try:
                branch_uuid = uuid.UUID(str(branch_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid branch ID."
                )

            attendance = attendance.filter(
                branch_id=branch_uuid
            )

        # Filter by attendance status
        if status:
            if status not in StaffAttendance.AttendanceStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid attendance status."
                )

            attendance = attendance.filter(
                status=status
            )

        # Search by staff name
        if search:
            attendance = attendance.filter(
                staff__name__icontains=search.strip()
            )

        # Total before pagination
        total = attendance.count()

        # Pagination
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(
            attendance,
            request,
        )

        page_records = list(page)

        # Fetch approved leave days for the staff and dates
        # represented on the current page.
        leave_days_by_staff_date = {}

        if page_records:
            page_staff_ids = {
                item.staff_id for item in page_records
            }

            page_dates = {
                item.attendance_date for item in page_records
            }

            approved_leave_days = LeaveDay.objects.filter(
                leave__school=school,
                leave__applicant_type=Leave.ApplicantType.STAFF,
                leave__status=Leave.LeaveStatus.APPROVED,
                leave__staff_id__in=page_staff_ids,
                leave_date__in=page_dates,
            ).select_related(
                "leave"
            )

            leave_days_by_staff_date = {
                (
                    leave_day.leave.staff_id,
                    leave_day.leave_date,
                ): leave_day
                for leave_day in approved_leave_days
            }

        # Response data
        data = []

        for item in page_records:
            leave_day = leave_days_by_staff_date.get(
                (
                    item.staff_id,
                    item.attendance_date,
                )
            )

            data.append({
                "id": str(item.id),

                "staff": {
                    "id": str(item.staff_id),
                    "name": item.staff.name,
                    "employee_id": item.staff.employee_id,
                    "staff_type": item.staff.staff_type,
                },

                "branch": {
                    "id": str(item.branch_id),
                    "name": str(item.branch),
                } if item.branch_id else None,

                "attendance_date": str(item.attendance_date),
                "status": item.status,

                "check_in": (
                    item.check_in.isoformat()
                    if item.check_in else None
                ),

                "check_out": (
                    item.check_out.isoformat()
                    if item.check_out else None
                ),

                "remarks": item.remarks,

                "approved_leave": leave_day is not None,

                "leave_duration": (
                    leave_day.duration
                    if leave_day else None
                ),

                "marked_by": {
                    "id": str(item.marked_by_id),
                    "name": item.marked_by.name,
                } if item.marked_by_id else None,
            })

        application_logger.info(
            "staff_attendance_list_fetched",
            school_id=str(school.id),
            requested_by=str(request.user.id),
            total=total,
        )

        return CustomResponse.successResponse(
            data=data,
            total=total,
            description="Staff attendance fetched successfully.",
        )



class UpdateStaffAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "staff_attendance.update"

    def put(self, request, attendance_id):
        school = request.school

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        try:
            attendance_uuid = uuid.UUID(str(attendance_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid attendance ID."
            )

        marked_by = Staff.objects.filter(
            user=request.user,
            school=school,
            status=Staff.Status.ACTIVE,
        ).first()

        if marked_by is None:
            return CustomResponse.errorResponse(
                description="Active staff record not found for this user."
            )

        allowed_fields = {
            "status",
            "check_in",
            "check_out",
            "remarks",
        }

        invalid_fields = set(request.data.keys()) - allowed_fields

        if invalid_fields:
            return CustomResponse.errorResponse(
                description=(
                    f"Invalid fields: {', '.join(sorted(invalid_fields))}."
                )
            )

        if not request.data:
            return CustomResponse.errorResponse(
                description="Provide at least one field to update."
            )

        try:
            with transaction.atomic():

                attendance = StaffAttendance.objects.select_for_update().filter(
                    id=attendance_uuid,
                    school=school,
                ).first()

                if attendance is None:
                    return CustomResponse.errorResponse(
                        description="Staff attendance not found."
                    )

                # Check approved leave for this staff member and date.
                approved_leave_day = LeaveDay.objects.filter(
                    leave__school=school,
                    leave__staff_id=attendance.staff_id,
                    leave__applicant_type=Leave.ApplicantType.STAFF,
                    leave__status=Leave.LeaveStatus.APPROVED,
                    leave_date=attendance.attendance_date,
                ).first()

                requested_status = request.data.get(
                    "status",
                    attendance.status,
                )

                if requested_status not in StaffAttendance.AttendanceStatus.values:
                    return CustomResponse.errorResponse(
                        description="Invalid attendance status."
                    )

                if approved_leave_day:
                    if (
                        approved_leave_day.duration
                        == LeaveDay.Duration.FULL_DAY
                    ):
                        # Full-day approved leave must remain LEAVE.
                        if (
                            "status" in request.data
                            and requested_status
                            != StaffAttendance.AttendanceStatus.LEAVE
                        ):
                            return CustomResponse.errorResponse(
                                description=(
                                    "Attendance cannot be changed because "
                                    "the staff member has approved full-day leave."
                                )
                            )

                        attendance.status = (
                            StaffAttendance.AttendanceStatus.LEAVE
                        )
                        attendance.check_in = None
                        attendance.check_out = None

                    elif (
                        approved_leave_day.duration
                        == LeaveDay.Duration.HALF_DAY
                    ):
                        # Preserve the half-day leave attendance status.
                        if (
                            "status" in request.data
                            and requested_status
                            != StaffAttendance.AttendanceStatus.HALF_DAY
                        ):
                            return CustomResponse.errorResponse(
                                description=(
                                    "Attendance cannot be changed because "
                                    "the staff member has approved half-day leave."
                                )
                            )

                        attendance.status = (
                            StaffAttendance.AttendanceStatus.HALF_DAY
                        )

                elif "status" in request.data:
                    attendance.status = requested_status

                # Update check-in/check-out only when full-day leave
                # does not require them to be cleared.
                if not (
                    approved_leave_day
                    and approved_leave_day.duration
                    == LeaveDay.Duration.FULL_DAY
                ):
                    for field in ["check_in", "check_out"]:
                        if field in request.data:
                            value = request.data.get(field)

                            if value in [None, ""]:
                                setattr(attendance, field, None)
                            else:
                                parsed_time = parse_time(str(value))

                                if parsed_time is None:
                                    return CustomResponse.errorResponse(
                                        description=(
                                            f"Invalid {field} time. Use HH:MM."
                                        )
                                    )

                                setattr(attendance, field, parsed_time)

                if (
                    attendance.check_in
                    and attendance.check_out
                    and attendance.check_out <= attendance.check_in
                ):
                    return CustomResponse.errorResponse(
                        description=(
                            "Check-out time must be after check-in time."
                        )
                    )

                if "remarks" in request.data:
                    attendance.remarks = request.data.get("remarks")

                attendance.marked_by = marked_by
                attendance.save()

        except Exception:
            application_logger.exception(
                "staff_attendance_update_failed",
                school_id=str(school.id),
                attendance_id=str(attendance_uuid),
                updated_by=str(marked_by.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update staff attendance."
            )

        application_logger.info(
            "staff_attendance_updated",
            school_id=str(school.id),
            attendance_id=str(attendance.id),
            staff_id=str(attendance.staff_id),
            status=attendance.status,
            updated_by=str(marked_by.id),
        )

        return CustomResponse.successResponse(
            description="Staff attendance updated successfully.",
            data={
                "id": str(attendance.id),
                "staff_id": str(attendance.staff_id),
                "staff_name": attendance.staff.name,
                "attendance_date": str(attendance.attendance_date),
                "status": attendance.status,
                "check_in": (
                    attendance.check_in.isoformat()
                    if attendance.check_in else None
                ),
                "check_out": (
                    attendance.check_out.isoformat()
                    if attendance.check_out else None
                ),
                "remarks": attendance.remarks,
                "marked_by": {
                    "id": str(marked_by.id),
                    "name": marked_by.name,
                },
            },
        )


class StaffAttendanceSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "staff_attendance.view"

    def get(self, request):
        try:
            school = request.school

            attendance_date = request.GET.get("attendance_date")
            start_date = request.GET.get("start_date")
            end_date = request.GET.get("end_date")
            branch_id = request.GET.get("branch_id")
            staff_id = request.GET.get("staff_id")
            recent_limit = request.GET.get("recent_limit", 10)

            # ---------------------------------------------------------
            # Validate recent limit
            # ---------------------------------------------------------
            try:
                recent_limit = int(recent_limit)
            except (TypeError, ValueError):
                return CustomResponse.errorResponse(
                    "recent_limit must be a valid number."
                )

            if recent_limit < 1 or recent_limit > 50:
                return CustomResponse.errorResponse(
                    "recent_limit must be between 1 and 50."
                )

            # ---------------------------------------------------------
            # Validate dates
            # ---------------------------------------------------------
            parsed_attendance_date = None
            parsed_start_date = None
            parsed_end_date = None

            if attendance_date:
                parsed_attendance_date = parse_date(attendance_date)

                if not parsed_attendance_date:
                    return CustomResponse.errorResponse(
                        "Invalid attendance_date. Use YYYY-MM-DD."
                    )

            if start_date:
                parsed_start_date = parse_date(start_date)

                if not parsed_start_date:
                    return CustomResponse.errorResponse(
                        "Invalid start_date. Use YYYY-MM-DD."
                    )

            if end_date:
                parsed_end_date = parse_date(end_date)

                if not parsed_end_date:
                    return CustomResponse.errorResponse(
                        "Invalid end_date. Use YYYY-MM-DD."
                    )

            if (
                parsed_start_date
                and parsed_end_date
                and parsed_start_date > parsed_end_date
            ):
                return CustomResponse.errorResponse(
                    "start_date cannot be greater than end_date."
                )

            # ---------------------------------------------------------
            # Resolve report range
            # ---------------------------------------------------------
            today = timezone.localdate()

            if parsed_attendance_date:
                report_start_date = parsed_attendance_date
                report_end_date = parsed_attendance_date

            elif parsed_start_date or parsed_end_date:
                report_start_date = parsed_start_date or parsed_end_date
                report_end_date = parsed_end_date or parsed_start_date

            else:
                report_start_date = today
                report_end_date = today

            # ---------------------------------------------------------
            # Staff queryset
            # ---------------------------------------------------------
            staff_queryset = Staff.objects.filter(
                school=school,
                status=Staff.Status.ACTIVE,
            )

            if branch_id:
                staff_queryset = staff_queryset.filter(
                    branch_id=branch_id
                )

            if staff_id:
                staff_queryset = staff_queryset.filter(
                    id=staff_id
                )

            staff_queryset = staff_queryset.select_related(
                "branch"
            )

            # ---------------------------------------------------------
            # Validate branch
            # ---------------------------------------------------------
            if branch_id:
                if not staff_queryset.exists():
                    return CustomResponse.errorResponse(
                        "No active staff found for the selected branch."
                    )

            # ---------------------------------------------------------
            # Validate staff
            # ---------------------------------------------------------
            if staff_id:
                if not staff_queryset.filter(id=staff_id).exists():
                    return CustomResponse.errorResponse(
                        "Staff member not found."
                    )

            # ---------------------------------------------------------
            # Attendance queryset
            # ---------------------------------------------------------
            attendance_queryset = StaffAttendance.objects.filter(
                school=school,
                attendance_date__range=[
                    report_start_date,
                    report_end_date,
                ],
                staff__status=Staff.Status.ACTIVE,
            )

            if branch_id:
                attendance_queryset = attendance_queryset.filter(
                    branch_id=branch_id
                )

            if staff_id:
                attendance_queryset = attendance_queryset.filter(
                    staff_id=staff_id
                )

            attendance_queryset = attendance_queryset.select_related(
                "staff",
                "staff__branch",
                "marked_by",
                "branch",
            )

            # ---------------------------------------------------------
            # Helper
            # ---------------------------------------------------------
            def attendance_units(status):
                if status in [
                    StaffAttendance.AttendanceStatus.PRESENT,
                    StaffAttendance.AttendanceStatus.LATE,
                ]:
                    return Decimal("1.0")

                if status == StaffAttendance.AttendanceStatus.HALF_DAY:
                    return Decimal("0.5")

                return Decimal("0.0")

            # ---------------------------------------------------------
            # Attendance records grouped in memory
            # ---------------------------------------------------------
            attendance_records = list(attendance_queryset)

            # ---------------------------------------------------------
            # Approved leave days
            #
            # LeaveDay supports:
            # FULL_DAY  = 1
            # HALF_DAY  = 0.5
            # ---------------------------------------------------------
            approved_leave_days = LeaveDay.objects.filter(
                leave__school=school,
                leave__applicant_type=Leave.ApplicantType.STAFF,
                leave__status=Leave.LeaveStatus.APPROVED,
                leave_date__range=[
                    report_start_date,
                    report_end_date,
                ],
            ).select_related(
                "leave",
                "leave__staff",
                "leave__branch",
            )

            if branch_id:
                approved_leave_days = approved_leave_days.filter(
                    leave__branch_id=branch_id
                )

            if staff_id:
                approved_leave_days = approved_leave_days.filter(
                    leave__staff_id=staff_id
                )

            approved_leave_days = list(approved_leave_days)

            # ---------------------------------------------------------
            # Leave lookup
            # ---------------------------------------------------------
            leave_map = {}

            for leave_day in approved_leave_days:
                key = (
                    leave_day.leave.staff_id,
                    leave_day.leave_date,
                )

                if leave_day.duration == LeaveDay.Duration.HALF_DAY:
                    duration = Decimal("0.5")
                else:
                    duration = Decimal("1.0")

                leave_map[key] = duration

            # ---------------------------------------------------------
            # Number of calendar days
            #
            # NOTE:
            # If your school has a working-day/calendar model,
            # replace this with actual working days.
            # ---------------------------------------------------------
            total_calendar_days = (
                report_end_date - report_start_date
            ).days + 1

            # ---------------------------------------------------------
            # OVERALL SUMMARY
            # ---------------------------------------------------------
            overall_present = 0
            overall_absent = 0
            overall_late = 0
            overall_half_day = 0
            overall_leave = 0

            attended_units = Decimal("0.0")

            for attendance in attendance_records:
                status = attendance.status

                if status == StaffAttendance.AttendanceStatus.PRESENT:
                    overall_present += 1
                    attended_units += Decimal("1.0")

                elif status == StaffAttendance.AttendanceStatus.ABSENT:
                    overall_absent += 1

                elif status == StaffAttendance.AttendanceStatus.LATE:
                    overall_late += 1
                    attended_units += Decimal("1.0")

                elif status == StaffAttendance.AttendanceStatus.HALF_DAY:
                    overall_half_day += 1
                    attended_units += Decimal("0.5")

                elif status == StaffAttendance.AttendanceStatus.LEAVE:
                    overall_leave += 1

            # ---------------------------------------------------------
            # Expected staff-days
            # ---------------------------------------------------------
            total_active_staff = staff_queryset.count()

            expected_staff_days = (
                total_active_staff * total_calendar_days
            )

            # Remove approved leave from eligible attendance days
            approved_leave_units = sum(
                leave_map.values(),
                Decimal("0.0"),
            )

            eligible_staff_days = (
                Decimal(str(expected_staff_days))
                - approved_leave_units
            )

            if eligible_staff_days < 0:
                eligible_staff_days = Decimal("0.0")

            if eligible_staff_days:
                attendance_percentage = (
                    attended_units
                    / eligible_staff_days
                    * Decimal("100")
                )
            else:
                attendance_percentage = Decimal("0.0")

            # ---------------------------------------------------------
            # OVERALL RESPONSE
            # ---------------------------------------------------------
            overall = {
                "total_staff": total_active_staff,
                "expected_staff_days": expected_staff_days,
                "attendance_records": len(attendance_records),
                "present": overall_present,
                "absent": overall_absent,
                "late": overall_late,
                "half_day": overall_half_day,
                "leave": overall_leave,
                "attended_units": float(attended_units),
                "approved_leave_units": float(approved_leave_units),
                "eligible_staff_days": float(eligible_staff_days),
                "attendance_percentage": round(
                    float(attendance_percentage),
                    2,
                ),
            }

            # =========================================================
            # STAFF TYPE SUMMARY
            # =========================================================
            staff_type_summary = {}

            for staff in staff_queryset:
                staff_type = staff.staff_type

                if staff_type not in staff_type_summary:
                    staff_type_summary[staff_type] = {
                        "staff_type": staff_type,
                        "total_staff": 0,
                        "expected_staff_days": 0,
                        "present": 0,
                        "absent": 0,
                        "late": 0,
                        "half_day": 0,
                        "leave": 0,
                        "attended_units": Decimal("0.0"),
                        "approved_leave_units": Decimal("0.0"),
                    }

                staff_type_summary[staff_type]["total_staff"] += 1

            # Expected staff days
            for item in staff_type_summary.values():
                item["expected_staff_days"] = (
                    item["total_staff"] * total_calendar_days
                )

            # Attendance
            for attendance in attendance_records:
                staff_type = attendance.staff.staff_type

                if staff_type not in staff_type_summary:
                    continue

                summary = staff_type_summary[staff_type]

                status = attendance.status

                if status == StaffAttendance.AttendanceStatus.PRESENT:
                    summary["present"] += 1
                    summary["attended_units"] += Decimal("1.0")

                elif status == StaffAttendance.AttendanceStatus.ABSENT:
                    summary["absent"] += 1

                elif status == StaffAttendance.AttendanceStatus.LATE:
                    summary["late"] += 1
                    summary["attended_units"] += Decimal("1.0")

                elif status == StaffAttendance.AttendanceStatus.HALF_DAY:
                    summary["half_day"] += 1
                    summary["attended_units"] += Decimal("0.5")

                elif status == StaffAttendance.AttendanceStatus.LEAVE:
                    summary["leave"] += 1

            # Approved leave grouped by staff type
            for leave_day in approved_leave_days:
                staff = leave_day.leave.staff

                if not staff:
                    continue

                staff_type = staff.staff_type

                if staff_type not in staff_type_summary:
                    continue

                if leave_day.duration == LeaveDay.Duration.HALF_DAY:
                    duration = Decimal("0.5")
                else:
                    duration = Decimal("1.0")

                staff_type_summary[staff_type][
                    "approved_leave_units"
                ] += duration

            staff_types = []

            for item in staff_type_summary.values():

                eligible_days = (
                    Decimal(str(item["expected_staff_days"]))
                    - item["approved_leave_units"]
                )

                if eligible_days < 0:
                    eligible_days = Decimal("0.0")

                if eligible_days:
                    percentage = (
                        item["attended_units"]
                        / eligible_days
                        * Decimal("100")
                    )
                else:
                    percentage = Decimal("0.0")

                staff_types.append(
                    {
                        "staff_type": item["staff_type"],
                        "total_staff": item["total_staff"],
                        "expected_staff_days": item[
                            "expected_staff_days"
                        ],
                        "present": item["present"],
                        "absent": item["absent"],
                        "late": item["late"],
                        "half_day": item["half_day"],
                        "leave": item["leave"],
                        "attended_units": float(
                            item["attended_units"]
                        ),
                        "approved_leave_units": float(
                            item["approved_leave_units"]
                        ),
                        "eligible_staff_days": float(
                            eligible_days
                        ),
                        "attendance_percentage": round(
                            float(percentage),
                            2,
                        ),
                    }
                )

            # =========================================================
            # MONTHLY TREND
            # =========================================================

            # If user supplied start/end, trend uses that range.
            # Otherwise use academic year: April 1 -> today.
            if (
                parsed_attendance_date
                or parsed_start_date
                or parsed_end_date
            ):
                trend_start_date = report_start_date
                trend_end_date = report_end_date
            else:
                if today.month >= 4:
                    academic_year_start = date(
                        today.year,
                        4,
                        1,
                    )
                else:
                    academic_year_start = date(
                        today.year - 1,
                        4,
                        1,
                    )

                trend_start_date = academic_year_start
                trend_end_date = today

            trend_attendance = StaffAttendance.objects.filter(
                school=school,
                attendance_date__range=[
                    trend_start_date,
                    trend_end_date,
                ],
                staff__status=Staff.Status.ACTIVE,
            )

            if branch_id:
                trend_attendance = trend_attendance.filter(
                    branch_id=branch_id
                )

            if staff_id:
                trend_attendance = trend_attendance.filter(
                    staff_id=staff_id
                )

            trend_attendance = trend_attendance.select_related(
                "staff"
            )

            trend_leave_days = LeaveDay.objects.filter(
                leave__school=school,
                leave__applicant_type=Leave.ApplicantType.STAFF,
                leave__status=Leave.LeaveStatus.APPROVED,
                leave_date__range=[
                    trend_start_date,
                    trend_end_date,
                ],
            )

            if branch_id:
                trend_leave_days = trend_leave_days.filter(
                    leave__branch_id=branch_id
                )

            if staff_id:
                trend_leave_days = trend_leave_days.filter(
                    leave__staff_id=staff_id
                )

            trend_leave_days = list(trend_leave_days)

            trend_leave_map = {}

            for leave_day in trend_leave_days:
                key = (
                    leave_day.leave.staff_id,
                    leave_day.leave_date,
                )

                if leave_day.duration == LeaveDay.Duration.HALF_DAY:
                    duration = Decimal("0.5")
                else:
                    duration = Decimal("1.0")

                trend_leave_map[key] = duration

            # ---------------------------------------------------------
            # Build months
            # ---------------------------------------------------------
            monthly_trend = []

            current_month = date(
                trend_start_date.year,
                trend_start_date.month,
                1,
            )

            end_month = date(
                trend_end_date.year,
                trend_end_date.month,
                1,
            )

            while current_month <= end_month:

                if current_month.month == 12:
                    next_month = date(
                        current_month.year + 1,
                        1,
                        1,
                    )
                else:
                    next_month = date(
                        current_month.year,
                        current_month.month + 1,
                        1,
                    )

                month_start = max(
                    current_month,
                    trend_start_date.replace(day=1),
                )

                month_end = min(
                    next_month - timedelta(days=1),
                    trend_end_date,
                )

                month_days = (
                    month_end - month_start
                ).days + 1

                # Attendance in this month
                month_records = [
                    item
                    for item in trend_attendance
                    if month_start
                    <= item.attendance_date
                    <= month_end
                ]

                month_attended_units = Decimal("0.0")

                month_present = 0
                month_absent = 0
                month_late = 0
                month_half_day = 0
                month_leave = 0

                for item in month_records:

                    if item.status == StaffAttendance.AttendanceStatus.PRESENT:
                        month_present += 1
                        month_attended_units += Decimal("1.0")

                    elif item.status == StaffAttendance.AttendanceStatus.ABSENT:
                        month_absent += 1

                    elif item.status == StaffAttendance.AttendanceStatus.LATE:
                        month_late += 1
                        month_attended_units += Decimal("1.0")

                    elif item.status == StaffAttendance.AttendanceStatus.HALF_DAY:
                        month_half_day += 1
                        month_attended_units += Decimal("0.5")

                    elif item.status == StaffAttendance.AttendanceStatus.LEAVE:
                        month_leave += 1

                month_leave_units = Decimal("0.0")

                for key, duration in trend_leave_map.items():
                    staff_pk, leave_date = key

                    if month_start <= leave_date <= month_end:
                        month_leave_units += duration

                month_expected_days = (
                    total_active_staff * month_days
                )

                month_eligible_days = (
                    Decimal(str(month_expected_days))
                    - month_leave_units
                )

                if month_eligible_days < 0:
                    month_eligible_days = Decimal("0.0")

                if month_eligible_days:
                    month_percentage = (
                        month_attended_units
                        / month_eligible_days
                        * Decimal("100")
                    )
                else:
                    month_percentage = Decimal("0.0")

                monthly_trend.append(
                    {
                        "month": current_month.strftime("%Y-%m"),
                        "month_name": current_month.strftime("%B"),
                        "expected_staff_days": month_expected_days,
                        "attendance_records": len(month_records),
                        "present": month_present,
                        "absent": month_absent,
                        "late": month_late,
                        "half_day": month_half_day,
                        "leave": month_leave,
                        "attended_units": float(
                            month_attended_units
                        ),
                        "approved_leave_units": float(
                            month_leave_units
                        ),
                        "eligible_staff_days": float(
                            month_eligible_days
                        ),
                        "attendance_percentage": round(
                            float(month_percentage),
                            2,
                        ),
                    }
                )

                current_month = next_month

            # =========================================================
            # RECENT EXCEPTIONS
            # =========================================================
            #
            # Exceptions are now taken from the selected report range,
            # not only from today.
            #
            # ABSENT + LATE are returned.
            # =========================================================
            exceptions = []

            exception_records = (
                attendance_queryset
                .filter(
                    status__in=[
                        StaffAttendance.AttendanceStatus.ABSENT,
                        StaffAttendance.AttendanceStatus.LATE,
                    ]
                )
                .order_by(
                    "-attendance_date",
                    "-created_at",
                )[:recent_limit]
            )

            for item in exception_records:
                exceptions.append(
                    {
                        "staff": {
                            "id": str(item.staff_id),
                            "name": item.staff.name,
                            "employee_id": getattr(
                                item.staff,
                                "employee_id",
                                None,
                            ),
                            "staff_type": item.staff.staff_type,
                        },
                        "attendance_date": item.attendance_date,
                        "status": item.status,
                        "remarks": item.remarks,
                    }
                )

            # =========================================================
            # APPROVED LEAVES
            # =========================================================
            approved_leaves = []

            for leave_day in approved_leave_days:
                staff = leave_day.leave.staff

                if not staff:
                    continue

                approved_leaves.append(
                    {
                        "leave_id": str(
                            leave_day.leave_id
                        ),
                        "staff": {
                            "id": str(staff.id),
                            "name": staff.name,
                            "employee_id": getattr(
                                staff,
                                "employee_id",
                                None,
                            ),
                            "staff_type": staff.staff_type,
                        },
                        "leave_date": leave_day.leave_date,
                        "duration": leave_day.duration,
                        "leave_type": leave_day.leave.leave_type,
                        "reason": leave_day.leave.reason,
                        "status": leave_day.leave.status,
                    }
                )

            # =========================================================
            # PENDING LEAVE REQUESTS
            # =========================================================
            pending_leave_queryset = Leave.objects.filter(
                school=school,
                applicant_type=Leave.ApplicantType.STAFF,
                status=Leave.LeaveStatus.PENDING,
                staff__status=Staff.Status.ACTIVE,
            )

            if branch_id:
                pending_leave_queryset = pending_leave_queryset.filter(
                    branch_id=branch_id
                )

            if staff_id:
                pending_leave_queryset = pending_leave_queryset.filter(
                    staff_id=staff_id
                )

            pending_leave_requests = (
                pending_leave_queryset.count()
            )

            # =========================================================
            # RESPONSE
            # =========================================================
            response_data = {
                "filters": {
                    "attendance_date": (
                        str(parsed_attendance_date)
                        if parsed_attendance_date
                        else None
                    ),
                    "start_date": (
                        str(report_start_date)
                        if report_start_date
                        else None
                    ),
                    "end_date": (
                        str(report_end_date)
                        if report_end_date
                        else None
                    ),
                    "branch_id": branch_id,
                    "staff_id": staff_id,
                },

                "overall": overall,

                "staff_types": staff_types,

                "monthly_trend": {
                    "start_date": str(trend_start_date),
                    "end_date": str(trend_end_date),
                    "data": monthly_trend,
                },

                "exceptions": exceptions,

                "approved_leaves": approved_leaves,

                "pending_leave_requests": (
                    pending_leave_requests
                ),
            }

            application_logger.info(
                "Staff attendance summary generated. "
                "school=%s start_date=%s end_date=%s",
                school.id,
                report_start_date,
                report_end_date,
            )

            return CustomResponse.successResponse(
                response_data,
                "Staff attendance summary fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "Error while generating staff attendance summary: %s",
                str(e),
            )

            return CustomResponse.errorResponse(
                "Unable to fetch staff attendance summary."
            )

class StaffLeaveRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school = request.school

        leave_type = request.data.get("leave_type", "CASUAL")
        leave_days_data = request.data.get("leave_days", [])
        reason = request.data.get("reason")
        pdf = request.data.get("pdf")

        if not leave_days_data or not reason:
            return CustomResponse.errorResponse(
                description="Leave dates and reason are required."
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

        # Validate leave dates and calculate total days.
        seen_dates = set()
        validated_days = []
        total_days = Decimal("0.0")
        today = timezone.localdate()

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

        # Identify the authenticated staff member.
        staff = Staff.objects.filter(
            user=request.user,
            school=school,
            status=Staff.Status.ACTIVE,
        ).first()

        if not staff:
            return CustomResponse.errorResponse(
                description="Active staff record not found."
            )
        requested_dates = [
            item["leave_date"]
            for item in validated_days
        ]

        existing_leave_days = LeaveDay.objects.filter(
            leave__school=school,
            leave__staff=staff,
            leave__applicant_type=Leave.ApplicantType.STAFF,
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
                str(leave_date)
                for leave_date in existing_leave_days
            )

            return CustomResponse.errorResponse(
                description=(
                    "Leave already exists for the following dates: "
                    f"{', '.join(duplicate_dates)}."
                )
            )

        try:
            with transaction.atomic():

                # Create the main leave request.
                leave = Leave.objects.create(
                    school=school,
                    branch=staff.branch,
                    applicant_type=Leave.ApplicantType.STAFF,
                    student=None,
                    staff=staff,
                    leave_type=leave_type,
                    start_date=start_date,
                    end_date=end_date,
                    total_days=total_days,
                    reason=reason.strip(),
                    pdf=pdf,
                    status=Leave.LeaveStatus.PENDING,
                    created_by=request.user,
                )

                # Create individual leave dates.
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
                "staff_leave_request_created",
                leave_id=str(leave.id),
                staff_id=str(staff.id),
                school_id=str(school.id),
                total_days=str(total_days),
            )

            return CustomResponse.successResponse(
                data={
                    "leave_id": str(leave.id),
                    "staff_id": str(staff.id),
                    "staff_name": staff.name,
                    "leave_type": leave.leave_type,
                    "start_date": str(leave.start_date),
                    "end_date": str(leave.end_date),
                    "total_days": str(leave.total_days),
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
                    "reason": leave.reason,
                    "pdf": leave.pdf,
                    "status": leave.status,
                },
                description="Staff leave request submitted successfully.",
            )

        except Exception:
            application_logger.exception(
                "staff_leave_request_creation_failed",
                staff_id=str(staff.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to submit leave request."
            )


class StudentLeaveListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_leave.view"

    def get(self, request):
        school = request.school

        leaves = Leave.objects.filter(
            school=school,
            applicant_type=Leave.ApplicantType.STUDENT,
        ).select_related(
            "student",
            "student__grade",
            "student__section",
            "branch",
            "reviewed_by",
        ).prefetch_related(
            Prefetch(
                "leave_days",
                queryset=LeaveDay.objects.order_by("leave_date"),
            )
        ).order_by("-created_at")

        status = request.query_params.get("status")
        student_id = request.query_params.get("student_id")
        leave_type = request.query_params.get("leave_type")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        search = request.query_params.get("search")

        # Filter by status.
        if status:
            if status not in Leave.LeaveStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid leave status."
                )

            leaves = leaves.filter(status=status)

        # Filter by student.
        if student_id:
            leaves = leaves.filter(student_id=student_id)

        # Filter by leave type.
        if leave_type:
            if leave_type not in Leave.LeaveType.values:
                return CustomResponse.errorResponse(
                    description="Invalid leave type."
                )

            leaves = leaves.filter(leave_type=leave_type)

        # Filter by start date.
        if start_date:
            parsed_start_date = parse_date(start_date)

            if not parsed_start_date:
                return CustomResponse.errorResponse(
                    description="Invalid start_date. Use YYYY-MM-DD."
                )

            leaves = leaves.filter(
                start_date__gte=parsed_start_date
            )

        # Filter by end date.
        if end_date:
            parsed_end_date = parse_date(end_date)

            if not parsed_end_date:
                return CustomResponse.errorResponse(
                    description="Invalid end_date. Use YYYY-MM-DD."
                )

            leaves = leaves.filter(
                end_date__lte=parsed_end_date
            )

        # Validate date range.
        if start_date and end_date:
            if parse_date(start_date) > parse_date(end_date):
                return CustomResponse.errorResponse(
                    description="Start date cannot be after end date."
                )

        # Search student name or leave reason.
        if search:
            leaves = leaves.filter(
                Q(student__name__icontains=search)
                | Q(reason__icontains=search)
            )

        paginator = CustomPageNumberPagination()

        paginated_leaves = paginator.paginate_queryset(
            leaves,
            request,
        )

        data = []

        for leave in paginated_leaves:
            leave_days_data = [
                {
                    "date": str(leave_day.leave_date),
                    "duration": leave_day.duration,
                    "days": (
                        "1.0"
                        if leave_day.duration == LeaveDay.Duration.FULL_DAY
                        else "0.5"
                    ),
                }
                for leave_day in leave.leave_days.all()
            ]

            data.append({
                "leave_id": str(leave.id),
                "student_id": str(leave.student_id),
                "student_name": leave.student.name,
                "admission_number": leave.student.admission_number,
                "grade": ({
                    "id": str(leave.student.grade_id),
                    "name": leave.student.grade.name,}
                    if leave.student.grade_id else None),
                "section": ({
                     "id": str(leave.student.section_id),
                     "name": leave.student.section.name,
                             }
                    if leave.student.section_id else None
                 ),
                "branch_id": (
                    str(leave.branch_id)
                    if leave.branch_id else None
                ),
                "leave_type": leave.leave_type,
                "start_date": str(leave.start_date),
                "end_date": str(leave.end_date),
                "leave_days": leave_days_data,
                "total_days": str(leave.total_days),
                "reason": leave.reason,
                "pdf": leave.pdf,
                "status": leave.status,
                "review_remarks": leave.review_remarks,
                "reviewed_by": ({
                    "id": str(leave.reviewed_by_id),
                    "name": leave.reviewed_by.name,}
                if leave.reviewed_by
                else None),
                "reviewed_at": (
                    leave.reviewed_at.isoformat()
                    if leave.reviewed_at else None
                ),
                "created_at": leave.created_at.isoformat(),
            })

        return CustomResponse.successResponse(
            data=data,
            total=paginator.page.paginator.count,
            description="Student leave requests fetched successfully.",
        )



class StaffLeaveListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "staff_leave.view"

    def get(self, request):
        school = request.school

        leaves = Leave.objects.filter(
            school=school,
            applicant_type=Leave.ApplicantType.STAFF,
        ).select_related(
            "staff",
            "branch",
            "reviewed_by",
        ).prefetch_related(
            Prefetch(
                "leave_days",
                queryset=LeaveDay.objects.order_by("leave_date"),
            )
        ).order_by("-created_at")

        status = request.query_params.get("status")
        staff_id = request.query_params.get("staff_id")
        leave_type = request.query_params.get("leave_type")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        search = request.query_params.get("search")

        # Filter by status.
        if status:
            if status not in Leave.LeaveStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid leave status."
                )

            leaves = leaves.filter(status=status)

        # Filter by staff.
        if staff_id:
            leaves = leaves.filter(staff_id=staff_id)

        # Filter by leave type.
        if leave_type:
            if leave_type not in Leave.LeaveType.values:
                return CustomResponse.errorResponse(
                    description="Invalid leave type."
                )

            leaves = leaves.filter(leave_type=leave_type)

        # Filter by start date.
        if start_date:
            parsed_start_date = parse_date(start_date)

            if not parsed_start_date:
                return CustomResponse.errorResponse(
                    description="Invalid start_date. Use YYYY-MM-DD."
                )

            leaves = leaves.filter(
                start_date__gte=parsed_start_date
            )

        # Filter by end date.
        if end_date:
            parsed_end_date = parse_date(end_date)

            if not parsed_end_date:
                return CustomResponse.errorResponse(
                    description="Invalid end_date. Use YYYY-MM-DD."
                )

            leaves = leaves.filter(
                end_date__lte=parsed_end_date
            )

        # Validate date range.
        if start_date and end_date:
            if parse_date(start_date) > parse_date(end_date):
                return CustomResponse.errorResponse(
                    description="Start date cannot be after end date."
                )

        # Search staff name or leave reason.
        if search:
            leaves = leaves.filter(
                Q(staff__name__icontains=search)
                | Q(reason__icontains=search)
            )

        paginator = CustomPageNumberPagination()

        paginated_leaves = paginator.paginate_queryset(
            leaves,
            request,
        )

        data = []

        for leave in paginated_leaves:

            leave_days_data = [
                {
                    "date": str(leave_day.leave_date),
                    "duration": leave_day.duration,
                    "days": (
                        "1.0"
                        if leave_day.duration == LeaveDay.Duration.FULL_DAY
                        else "0.5"
                    ),
                }
                for leave_day in leave.leave_days.all()
            ]

            data.append({
                "leave_id": str(leave.id),
                "staff_id": str(leave.staff_id),
                "staff_name": leave.staff.name,
                "employee_id": leave.staff.employee_id,
                "staff_type": leave.staff.staff_type,
                "branch_id": (
                    str(leave.branch_id)
                    if leave.branch_id else None
                ),
                "leave_type": leave.leave_type,
                "start_date": str(leave.start_date),
                "end_date": str(leave.end_date),
                "leave_days": leave_days_data,
                "total_days": str(leave.total_days),
                "reason": leave.reason,
                "pdf": leave.pdf,
                "status": leave.status,
                "review_remarks": leave.review_remarks,
                "reviewed_by": (
                    leave.reviewed_by.get_full_name()
                    if leave.reviewed_by else None
                ),
                "reviewed_at": (
                    leave.reviewed_at.isoformat()
                    if leave.reviewed_at else None
                ),
                "created_at": leave.created_at.isoformat(),
            })

        return CustomResponse.successResponse(
            data=data,
            total=paginator.page.paginator.count,
            description="Staff leave requests fetched successfully.",
        )


class StudentLeaveReviewAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_leave.review"

    def put(self, request, leave_id):
        school = request.school

        review_status = request.data.get("status")
        review_remarks = request.data.get("review_remarks", "")

        if review_status not in [
            Leave.LeaveStatus.APPROVED,
            Leave.LeaveStatus.REJECTED,
        ]:
            return CustomResponse.errorResponse(
                description="Status must be APPROVED or REJECTED."
            )
        reviewer = Staff.objects.filter(
            user=request.user,
            school=school,
            status=Staff.Status.ACTIVE,
        ).first()

        if not reviewer:
            return CustomResponse.errorResponse(
                description="Active staff record not found."
            )

        # Only Principal or Admin can review staff leave.
        if reviewer.staff_type not in [
            Staff.StaffType.PRINCIPAL,
            Staff.StaffType.ADMIN,
        ]:
            return CustomResponse.errorResponse(
                description="Only Admin or Principal can review staff leave."
            )

        try:
            with transaction.atomic():
                leave = Leave.objects.select_for_update().filter(
                    id=leave_id,
                    school=school,
                    applicant_type=Leave.ApplicantType.STUDENT,
                ).first()

                if not leave:
                    return CustomResponse.errorResponse(
                        description="Student leave request not found."
                    )

                if leave.status != Leave.LeaveStatus.PENDING:
                    return CustomResponse.errorResponse(
                        description="This leave request has already been reviewed."
                    )

                leave_days = list(
                    leave.leave_days.order_by("leave_date")
                )

                if not leave_days:
                    return CustomResponse.errorResponse(
                        description="No leave dates found for this request."
                    )

                leave.status = review_status
                leave.reviewed_by = reviewer
                leave.reviewed_at = timezone.now()
                leave.review_remarks = review_remarks
                leave.save()

                updated_attendance_count = 0

                if review_status == Leave.LeaveStatus.APPROVED:
                    for leave_day in leave_days:

                        # Update attendance only for approved full-day leave.
                        if leave_day.duration == LeaveDay.Duration.FULL_DAY:
                            updated_count = StudentAttendance.objects.filter(
                                school=school,
                                student=leave.student,
                                attendance_date=leave_day.leave_date,
                                status=StudentAttendance.AttendanceStatus.ABSENT,
                            ).update(
                                status=StudentAttendance.AttendanceStatus.LEAVE
                            )

                            updated_attendance_count += updated_count

                        # Half-day leave is represented by the approved
                        # LeaveDay record. Attendance remains unchanged
                        # because StudentAttendance has one status per day.

            application_logger.info(
                "student_leave_reviewed",
                leave_id=str(leave.id),
                status=review_status,
                reviewer_id=str(request.user.id),
                updated_attendance_count=updated_attendance_count,
            )

            return CustomResponse.successResponse(
                data={
                    "leave_id": str(leave.id),
                    "student_id": str(leave.student_id),
                    "status": leave.status,
                    "review_remarks": leave.review_remarks,
                    "total_days": str(leave.total_days),
                    "leave_days": [
                        {
                            "date": str(leave_day.leave_date),
                            "duration": leave_day.duration,
                        }
                        for leave_day in leave_days
                    ],
                    "updated_attendance_count": updated_attendance_count,
                },
                description=(
                    "Student leave approved successfully."
                    if review_status == Leave.LeaveStatus.APPROVED
                    else "Student leave rejected successfully."
                ),
            )

        except Exception:
            application_logger.exception(
                "student_leave_review_failed",
                leave_id=str(leave_id),
            )

            return CustomResponse.errorResponse(
                description="Unable to review student leave request."
            )



class StaffLeaveReviewAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "staff_leave.review"

    def put(self, request, leave_id):
        school = request.school

        status = request.data.get("status")
        review_remarks = request.data.get("review_remarks", "")

        if status not in [
            Leave.LeaveStatus.APPROVED,
            Leave.LeaveStatus.REJECTED,
        ]:
            return CustomResponse.errorResponse(
                description="Status must be APPROVED or REJECTED."
            )

        reviewer = Staff.objects.filter(
            user=request.user,
            school=school,
            status=Staff.Status.ACTIVE,
        ).first()

        if not reviewer:
            return CustomResponse.errorResponse(
                description="Active staff record not found."
            )

        # Only Principal or Admin can review staff leave.
        if reviewer.staff_type not in [
            Staff.StaffType.PRINCIPAL,
            Staff.StaffType.ADMIN,
        ]:
            return CustomResponse.errorResponse(
                description="Only Admin or Principal can review staff leave."
            )

        try:
            with transaction.atomic():

                leave = Leave.objects.select_for_update().filter(
                    id=leave_id,
                    school=school,
                    applicant_type=Leave.ApplicantType.STAFF,
                ).first()

                if not leave:
                    return CustomResponse.errorResponse(
                        description="Staff leave request not found."
                    )

                if leave.status != Leave.LeaveStatus.PENDING:
                    return CustomResponse.errorResponse(
                        description="This leave request has already been reviewed."
                    )

                # Prevent reviewing your own leave request.
                if leave.staff.user_id == request.user.id:
                    return CustomResponse.errorResponse(
                        description="You cannot review your own leave request."
                    )

                leave_days = list(
                    LeaveDay.objects.filter(
                        leave=leave
                    ).order_by("leave_date")
                )

                if not leave_days:
                    return CustomResponse.errorResponse(
                        description="No leave dates found for this request."
                    )

                leave.status = status
                leave.reviewed_by = reviewer
                leave.reviewed_at = timezone.now()
                leave.review_remarks = review_remarks.strip() if review_remarks else None
                leave.save()

                updated_attendance_count = 0

                if status == Leave.LeaveStatus.APPROVED:

                    for leave_day in leave_days:

                        # Update only existing ABSENT attendance records.
                        if (
                            leave_day.duration
                            == LeaveDay.Duration.FULL_DAY
                        ):
                            updated_attendance_count += (
                                StaffAttendance.objects.filter(
                                    school=school,
                                    staff=leave.staff,
                                    attendance_date=leave_day.leave_date,
                                    status=(
                                        StaffAttendance
                                        .AttendanceStatus.ABSENT
                                    ),
                                ).update(
                                    status=(
                                        StaffAttendance
                                        .AttendanceStatus.LEAVE
                                    )
                                )
                            )

                        else:
                            # A single daily attendance status cannot
                            # accurately represent half-day leave.
                            # Keep the attendance status unchanged and
                            # use the approved LeaveDay record when
                            # calculating leave totals.

                            application_logger.info(
                                "staff_half_day_leave_approved",
                                leave_id=str(leave.id),
                                staff_id=str(leave.staff_id),
                                leave_date=str(leave_day.leave_date),
                            )

            application_logger.info(
                "staff_leave_reviewed",
                leave_id=str(leave.id),
                status=status,
                reviewer_id=str(request.user.id),
                updated_attendance_count=updated_attendance_count,
            )

            return CustomResponse.successResponse(
                data={
                    "leave_id": str(leave.id),
                    "staff_id": str(leave.staff_id),
                    "start_date": str(leave.start_date),
                    "end_date": str(leave.end_date),
                    "total_days": str(leave.total_days),
                    "status": leave.status,
                    "review_remarks": leave.review_remarks,
                    "updated_attendance_count": updated_attendance_count,
                },
                description=(
                    "Staff leave approved successfully."
                    if status == Leave.LeaveStatus.APPROVED
                    else "Staff leave rejected successfully."
                ),
            )

        except Exception:
            application_logger.exception(
                "staff_leave_review_failed",
                leave_id=str(leave_id),
            )

            return CustomResponse.errorResponse(
                description="Unable to review staff leave request."
            )









class StudentAttendanceSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_attendance.view"

    def get(self, request):
        school = request.school

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        try:
            # ==========================================================
            # QUERY PARAMETERS
            # ==========================================================

            attendance_date = request.query_params.get(
                "attendance_date"
            )
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            student_id = request.query_params.get("student_id")
            grade_id = request.query_params.get("grade_id")
            section_id = request.query_params.get("section_id")
            branch_id = request.query_params.get("branch_id")

            trend_start_date = request.query_params.get(
                "trend_start_date"
            )
            trend_end_date = request.query_params.get(
                "trend_end_date"
            )

            recent_limit = request.query_params.get(
                "recent_limit",
                10,
            )

            # ==========================================================
            # RECENT LIMIT
            # ==========================================================

            try:
                recent_limit = int(recent_limit)

                if recent_limit < 1 or recent_limit > 50:
                    raise ValueError

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="recent_limit must be between 1 and 50."
                )

            # ==========================================================
            # PARSE DATES
            # ==========================================================

            parsed_attendance_date = None
            parsed_start_date = None
            parsed_end_date = None

            if attendance_date:
                parsed_attendance_date = parse_date(
                    attendance_date
                )

                if not parsed_attendance_date:
                    return CustomResponse.errorResponse(
                        description=(
                            "Invalid attendance_date. "
                            "Use YYYY-MM-DD."
                        )
                    )

            if start_date:
                parsed_start_date = parse_date(start_date)

                if not parsed_start_date:
                    return CustomResponse.errorResponse(
                        description=(
                            "Invalid start_date. "
                            "Use YYYY-MM-DD."
                        )
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

            if (
                parsed_start_date
                and parsed_end_date
                and parsed_start_date > parsed_end_date
            ):
                return CustomResponse.errorResponse(
                    description=(
                        "start_date cannot be after end_date."
                    )
                )

            # ==========================================================
            # VALIDATE UUID
            # ==========================================================

            def get_uuid(value, field_name):
                if not value:
                    return None, None

                try:
                    parsed_uuid = uuid.UUID(str(value))
                except (
                    ValueError,
                    TypeError,
                    AttributeError,
                ):
                    return None, CustomResponse.errorResponse(
                        description=f"Invalid {field_name}."
                    )

                return parsed_uuid, None

            student_uuid, error = get_uuid(
                student_id,
                "student ID",
            )
            if error:
                return error

            grade_uuid, error = get_uuid(
                grade_id,
                "grade ID",
            )
            if error:
                return error

            section_uuid, error = get_uuid(
                section_id,
                "section ID",
            )
            if error:
                return error

            branch_uuid, error = get_uuid(
                branch_id,
                "branch ID",
            )
            if error:
                return error

            # ==========================================================
            # VALIDATE STUDENT
            # ==========================================================

            if student_uuid:
                if not Student.objects.filter(
                    id=student_uuid,
                    school=school,
                ).exists():
                    return CustomResponse.errorResponse(
                        description="Student not found."
                    )

            # ==========================================================
            # VALIDATE GRADE
            # ==========================================================

            if grade_uuid:
                if not Grade.objects.filter(
                    id=grade_uuid,
                    school=school,
                ).exists():
                    return CustomResponse.errorResponse(
                        description="Grade not found."
                    )

            # ==========================================================
            # VALIDATE SECTION
            # ==========================================================

            if section_uuid:
                if not Section.objects.filter(
                    id=section_uuid,
                ).exists():
                    return CustomResponse.errorResponse(
                        description="Section not found."
                    )

            # ==========================================================
            # VALIDATE BRANCH
            # ==========================================================

            if branch_uuid:
                if not Branch.objects.filter(
                    id=branch_uuid,
                    school=school,
                ).exists():
                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

            # ==========================================================
            # STUDENT POPULATION
            # ==========================================================

            students = Student.objects.filter(
                school=school,
            )

            if student_uuid:
                students = students.filter(
                    id=student_uuid,
                )

            if grade_uuid:
                students = students.filter(
                    grade_id=grade_uuid,
                )

            if section_uuid:
                students = students.filter(
                    section_id=section_uuid,
                )

            if branch_uuid:
                students = students.filter(
                    branch_id=branch_uuid,
                )

            total_students = students.count()

            # ==========================================================
            # ATTENDANCE QUERY
            # ==========================================================

            attendance = StudentAttendance.objects.filter(
                school=school,
            )

            if parsed_attendance_date:
                attendance = attendance.filter(
                    attendance_date=parsed_attendance_date,
                )
            else:
                if parsed_start_date:
                    attendance = attendance.filter(
                        attendance_date__gte=parsed_start_date,
                    )

                if parsed_end_date:
                    attendance = attendance.filter(
                        attendance_date__lte=parsed_end_date,
                    )

            if student_uuid:
                attendance = attendance.filter(
                    student_id=student_uuid,
                )

            if grade_uuid:
                attendance = attendance.filter(
                    grade_id=grade_uuid,
                )

            if section_uuid:
                attendance = attendance.filter(
                    section_id=section_uuid,
                )

            if branch_uuid:
                attendance = attendance.filter(
                    branch_id=branch_uuid,
                )

            # ==========================================================
            # OVERALL SUMMARY
            # ==========================================================

            overall_data = attendance.aggregate(
                marked_students=Count(
                    "student_id",
                    distinct=True,
                ),

                attendance_records=Count("id"),

                present=Count(
                    "id",
                    filter=Q(
                        status=(
                            StudentAttendance
                            .AttendanceStatus
                            .PRESENT
                        )
                    ),
                ),

                absent=Count(
                    "id",
                    filter=Q(
                        status=(
                            StudentAttendance
                            .AttendanceStatus
                            .ABSENT
                        )
                    ),
                ),

                late=Count(
                    "id",
                    filter=Q(
                        status=(
                            StudentAttendance
                            .AttendanceStatus
                            .LATE
                        )
                    ),
                ),

                leave=Count(
                    "id",
                    filter=Q(
                        status=(
                            StudentAttendance
                            .AttendanceStatus
                            .LEAVE
                        )
                    ),
                ),

                half_day=Count(
                    "id",
                    filter=Q(
                        status=(
                            StudentAttendance
                            .AttendanceStatus
                            .HALF_DAY
                        )
                    ),
                ),
            )

            marked_students = (
                overall_data["marked_students"] or 0
            )

            attendance_records = (
                overall_data["attendance_records"] or 0
            )

            present = overall_data["present"] or 0
            absent = overall_data["absent"] or 0
            late = overall_data["late"] or 0
            leave = overall_data["leave"] or 0
            half_day = overall_data["half_day"] or 0

            # ==========================================================
            # OVERALL ATTENDANCE PERCENTAGE
            # ==========================================================

            attended_units = (
                present
                + late
                + (half_day * 0.5)
            )

            # For a single day:
            # Total students - leave students
            #
            # For a date range:
            # use marked students as denominator because
            # attendance records represent the selected range.

            if parsed_attendance_date:

                eligible_students = (
                    total_students - leave
                )

                if eligible_students > 0:
                    attendance_percentage = round(
                        (
                            attended_units
                            / eligible_students
                        ) * 100,
                        2,
                    )
                else:
                    attendance_percentage = 0

            else:

                eligible_students = (
                    marked_students - leave
                )

                if eligible_students > 0:
                    attendance_percentage = round(
                        (
                            attended_units
                            / eligible_students
                        ) * 100,
                        2,
                    )
                else:
                    attendance_percentage = 0

            overall = {
                "total_students": total_students,
                "marked_students": marked_students,
                "attendance_records": attendance_records,
                "present": present,
                "absent": absent,
                "late": late,
                "leave": leave,
                "half_day": half_day,
                "attendance_percentage": (
                    attendance_percentage
                ),
            }

            # ==========================================================
            # GRADE + SECTION SUMMARY
            # ==========================================================

            class_summary = (
                students
                .values(
                    "grade_id",
                    "grade__name",
                    "section_id",
                    "section__name",
                )
                .annotate(
                    total_students=Count(
                        "id",
                        distinct=True,
                    )
                )
                .order_by(
                    "grade__name",
                    "section__name",
                )
            )

            grades = []

            for class_data in class_summary:

                class_grade_id = class_data["grade_id"]
                class_section_id = class_data["section_id"]

                # ------------------------------------------------------
                # Attendance ONLY for this grade + section
                # ------------------------------------------------------

                class_attendance = attendance.filter(
                    grade_id=class_grade_id,
                    section_id=class_section_id,
                )

                # ------------------------------------------------------
                # For a single day, count unique students by status.
                #
                # This prevents duplicate attendance rows from causing
                # 200%, 300%, 350%, etc.
                # ------------------------------------------------------

                if parsed_attendance_date:

                    class_data_summary = (
                        class_attendance.values(
                            "student_id",
                        )
                        .annotate(
                            student_status=Count("id"),
                        )
                    )

                    student_ids = [
                        item["student_id"]
                        for item in class_data_summary
                    ]

                    # Get one attendance status per student.
                    #
                    # Normally your unique constraint should guarantee
                    # only one record per student/date.
                    class_records = (
                        class_attendance
                        .filter(
                            student_id__in=student_ids,
                        )
                        .order_by(
                            "student_id",
                            "-created_at",
                        )
                    )

                    student_status_map = {}

                    for record in class_records:

                        if record.student_id not in student_status_map:
                            student_status_map[
                                record.student_id
                            ] = record.status

                    class_present = 0
                    class_absent = 0
                    class_late = 0
                    class_leave = 0
                    class_half_day = 0

                    for status in student_status_map.values():

                        if status == (
                            StudentAttendance
                            .AttendanceStatus
                            .PRESENT
                        ):
                            class_present += 1

                        elif status == (
                            StudentAttendance
                            .AttendanceStatus
                            .ABSENT
                        ):
                            class_absent += 1

                        elif status == (
                            StudentAttendance
                            .AttendanceStatus
                            .LATE
                        ):
                            class_late += 1

                        elif status == (
                            StudentAttendance
                            .AttendanceStatus
                            .LEAVE
                        ):
                            class_leave += 1

                        elif status == (
                            StudentAttendance
                            .AttendanceStatus
                            .HALF_DAY
                        ):
                            class_half_day += 1

                    class_marked_students = len(
                        student_status_map
                    )

                else:

                    class_present = (
                        class_attendance.filter(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .PRESENT
                            )
                        ).count()
                    )

                    class_absent = (
                        class_attendance.filter(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .ABSENT
                            )
                        ).count()
                    )

                    class_late = (
                        class_attendance.filter(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .LATE
                            )
                        ).count()
                    )

                    class_leave = (
                        class_attendance.filter(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .LEAVE
                            )
                        ).count()
                    )

                    class_half_day = (
                        class_attendance.filter(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .HALF_DAY
                            )
                        ).count()
                    )

                    class_marked_students = (
                        class_attendance.values(
                            "student_id"
                        ).distinct().count()
                    )

                # ------------------------------------------------------
                # TOTAL STUDENTS IN THIS CLASS
                # ------------------------------------------------------

                class_total_students = (
                    class_data["total_students"] or 0
                )

                # ------------------------------------------------------
                # ATTENDED UNITS
                # ------------------------------------------------------

                class_attended_units = (
                    class_present
                    + class_late
                    + (class_half_day * 0.5)
                )

                # ------------------------------------------------------
                # ATTENDANCE PERCENTAGE
                # ------------------------------------------------------

                if parsed_attendance_date:

                    # Approved leave should not reduce attendance.
                    eligible_students = (
                        class_total_students
                        - class_leave
                    )

                    if eligible_students > 0:
                        class_percentage = round(
                            (
                                class_attended_units
                                / eligible_students
                            ) * 100,
                            2,
                        )
                    else:
                        class_percentage = 0

                else:

                    eligible_students = (
                        class_marked_students
                        - class_leave
                    )

                    if eligible_students > 0:
                        class_percentage = round(
                            (
                                class_attended_units
                                / eligible_students
                            ) * 100,
                            2,
                        )
                    else:
                        class_percentage = 0

                # ------------------------------------------------------
                # FINAL GRADE RESPONSE
                # ------------------------------------------------------

                grades.append(
                    {
                        "grade": {
                            "id": (
                                str(class_grade_id)
                                if class_grade_id
                                else None
                            ),
                            "name": class_data[
                                "grade__name"
                            ],
                        },

                        "section": {
                            "id": (
                                str(class_section_id)
                                if class_section_id
                                else None
                            ),
                            "name": class_data[
                                "section__name"
                            ],
                        },

                        "total_students": (
                            class_total_students
                        ),

                        "present": class_present,

                        "absent": class_absent,

                        "late": class_late,

                        "leave": class_leave,

                        "attendance_percentage": (
                            class_percentage
                        ),
                    }
                )

            # ==========================================================
            # MONTHLY TREND
            # ==========================================================

            today = timezone.localdate()

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
            else:
                if today.month >= 4:
                    parsed_trend_start = date(
                        today.year,
                        4,
                        1,
                    )
                else:
                    parsed_trend_start = date(
                        today.year - 1,
                        4,
                        1,
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
            else:
                parsed_trend_end = today

            if parsed_trend_start > parsed_trend_end:
                return CustomResponse.errorResponse(
                    description=(
                        "trend_start_date cannot be "
                        "after trend_end_date."
                    )
                )

            trend_attendance = (
                StudentAttendance.objects.filter(
                    school=school,
                    attendance_date__gte=(
                        parsed_trend_start
                    ),
                    attendance_date__lte=(
                        parsed_trend_end
                    ),
                )
            )

            if student_uuid:
                trend_attendance = (
                    trend_attendance.filter(
                        student_id=student_uuid
                    )
                )

            if grade_uuid:
                trend_attendance = (
                    trend_attendance.filter(
                        grade_id=grade_uuid
                    )
                )

            if section_uuid:
                trend_attendance = (
                    trend_attendance.filter(
                        section_id=section_uuid
                    )
                )

            if branch_uuid:
                trend_attendance = (
                    trend_attendance.filter(
                        branch_id=branch_uuid
                    )
                )

            monthly_summary = (
                trend_attendance
                .annotate(
                    month=TruncMonth(
                        "attendance_date"
                    )
                )
                .values("month")
                .annotate(
                    total_records=Count("id"),

                    present=Count(
                        "id",
                        filter=Q(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .PRESENT
                            )
                        ),
                    ),

                    absent=Count(
                        "id",
                        filter=Q(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .ABSENT
                            )
                        ),
                    ),

                    late=Count(
                        "id",
                        filter=Q(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .LATE
                            )
                        ),
                    ),

                    leave=Count(
                        "id",
                        filter=Q(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .LEAVE
                            )
                        ),
                    ),

                    half_day=Count(
                        "id",
                        filter=Q(
                            status=(
                                StudentAttendance
                                .AttendanceStatus
                                .HALF_DAY
                            )
                        ),
                    ),
                )
                .order_by("month")
            )

            monthly_trend = []

            for item in monthly_summary:

                total_records = (
                    item["total_records"] or 0
                )

                month_present = (
                    item["present"] or 0
                )

                month_absent = (
                    item["absent"] or 0
                )

                month_late = (
                    item["late"] or 0
                )

                month_leave = (
                    item["leave"] or 0
                )

                month_half_day = (
                    item["half_day"] or 0
                )

                month_attended_units = (
                    month_present
                    + month_late
                    + (month_half_day * 0.5)
                )

                month_percentage = (
                    round(
                        (
                            month_attended_units
                            / total_records
                        ) * 100,
                        2,
                    )
                    if total_records
                    else 0
                )

                monthly_trend.append(
                    {
                        "month": item[
                            "month"
                        ].strftime("%b"),

                        "year": item[
                            "month"
                        ].year,

                        "total_attendance_records": (
                            total_records
                        ),

                        "present": month_present,

                        "absent": month_absent,

                        "late": month_late,

                        "leave": month_leave,

                        "half_day": month_half_day,

                        "attendance_percentage": (
                            month_percentage
                        ),
                    }
                )

            # ==========================================================
            # RECENT ABSENTEES
            # ==========================================================

            recent_absent_attendance = (
                StudentAttendance.objects.filter(
                    school=school,
                    status=(
                        StudentAttendance
                        .AttendanceStatus
                        .ABSENT
                    ),
                )
            )

            if student_uuid:
                recent_absent_attendance = (
                    recent_absent_attendance.filter(
                        student_id=student_uuid
                    )
                )

            if grade_uuid:
                recent_absent_attendance = (
                    recent_absent_attendance.filter(
                        grade_id=grade_uuid
                    )
                )

            if section_uuid:
                recent_absent_attendance = (
                    recent_absent_attendance.filter(
                        section_id=section_uuid
                    )
                )

            if branch_uuid:
                recent_absent_attendance = (
                    recent_absent_attendance.filter(
                        branch_id=branch_uuid
                    )
                )

            recent_absentees = (
                recent_absent_attendance
                .values(
                    "student_id",
                    "student__name",
                    "student__admission_number",
                    "grade_id",
                    "grade__name",
                    "section_id",
                    "section__name",
                )
                .annotate(
                    absent_days=Count("id"),
                    latest_absent_date=Max(
                        "attendance_date"
                    ),
                )
                .order_by(
                    "-latest_absent_date",
                    "student__name",
                )[:recent_limit]
            )

            recent_absentees_data = []

            for item in recent_absentees:

                recent_absentees_data.append(
                    {
                        "student": {
                            "id": str(
                                item["student_id"]
                            ),
                            "name": item[
                                "student__name"
                            ],
                            "admission_number": (
                                item[
                                    "student__admission_number"
                                ]
                            ),
                        },

                        "grade": {
                            "id": (
                                str(
                                    item["grade_id"]
                                )
                                if item["grade_id"]
                                else None
                            ),
                            "name": item[
                                "grade__name"
                            ],
                        },

                        "section": {
                            "id": (
                                str(
                                    item["section_id"]
                                )
                                if item["section_id"]
                                else None
                            ),
                            "name": item[
                                "section__name"
                            ],
                        },

                        "absent_days": (
                            item["absent_days"]
                        ),

                        "latest_absent_date": str(
                            item[
                                "latest_absent_date"
                            ]
                        ),
                    }
                )

            # ==========================================================
            # FINAL RESPONSE
            # ==========================================================

            data = {
                "overall": overall,

                "grades": grades,

                "monthly_trend": monthly_trend,

                "recent_absentees": (
                    recent_absentees_data
                ),
            }

            application_logger.info(
                "student_attendance_summary_fetched",
                school_id=str(school.id),
                requested_by=str(request.user.id),
                total_students=total_students,
                marked_students=marked_students,
                attendance_records=attendance_records,
                grade_count=len(grades),
                monthly_count=len(monthly_trend),
                recent_absentees_count=len(
                    recent_absentees_data
                ),
            )

            return CustomResponse.successResponse(
                data=data,
                description=(
                    "Student attendance summary "
                    "fetched successfully."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "Error while fetching student attendance "
                "summary: %s",
                str(e),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Unable to fetch student attendance summary."
                )
            )
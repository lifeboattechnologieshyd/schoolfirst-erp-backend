import uuid
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Prefetch
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
        school = request.school

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        attendance = StaffAttendance.objects.filter(
            school=school,
        )

        attendance_date = request.query_params.get("attendance_date")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        branch_id = request.query_params.get("branch_id")
        staff_id = request.query_params.get("staff_id")

        parsed_start = None
        parsed_end = None

        # Exact date filter
        if attendance_date:
            parsed_date = parse_date(attendance_date)

            if parsed_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid attendance_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date=parsed_date
            )

        # Start date filter
        if start_date:
            parsed_start = parse_date(start_date)

            if parsed_start is None:
                return CustomResponse.errorResponse(
                    description="Invalid start_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date__gte=parsed_start
            )

        # End date filter
        if end_date:
            parsed_end = parse_date(end_date)

            if parsed_end is None:
                return CustomResponse.errorResponse(
                    description="Invalid end_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date__lte=parsed_end
            )

        if (
            parsed_start
            and parsed_end
            and parsed_start > parsed_end
        ):
            return CustomResponse.errorResponse(
                description="start_date cannot be after end_date."
            )

        # Validate branch
        if branch_id:
            try:
                branch_uuid = uuid.UUID(str(branch_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid branch ID."
                )

            if not Branch.objects.filter(
                id=branch_uuid,
                school=school,
            ).exists():
                return CustomResponse.errorResponse(
                    description="Branch not found."
                )

            attendance = attendance.filter(
                branch_id=branch_uuid
            )

        # Validate staff
        if staff_id:
            try:
                staff_uuid = uuid.UUID(str(staff_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid staff ID."
                )

            if not Staff.objects.filter(
                id=staff_uuid,
                school=school,
            ).exists():
                return CustomResponse.errorResponse(
                    description="Staff not found."
                )

            attendance = attendance.filter(
                staff_id=staff_uuid
            )

        # Attendance summary
        summary = attendance.aggregate(
            total=Count("id"),
            present=Count(
                "id",
                filter=Q(
                    status=StaffAttendance.AttendanceStatus.PRESENT
                ),
            ),
            absent=Count(
                "id",
                filter=Q(
                    status=StaffAttendance.AttendanceStatus.ABSENT
                ),
            ),
            late=Count(
                "id",
                filter=Q(
                    status=StaffAttendance.AttendanceStatus.LATE
                ),
            ),
            half_day=Count(
                "id",
                filter=Q(
                    status=StaffAttendance.AttendanceStatus.HALF_DAY
                ),
            ),
            leave=Count(
                "id",
                filter=Q(
                    status=StaffAttendance.AttendanceStatus.LEAVE
                ),
            ),
        )

        return CustomResponse.successResponse(
            data=summary,
            description="Staff attendance summary fetched successfully.",
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
                leave.reviewed_by = request.user
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
                    leave.leave_days.order_by("leave_date")
                )

                if not leave_days:
                    return CustomResponse.errorResponse(
                        description="No leave dates found for this request."
                    )

                leave.status = status
                leave.reviewed_by = request.user
                leave.reviewed_at = timezone.now()
                leave.review_remarks = review_remarks
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
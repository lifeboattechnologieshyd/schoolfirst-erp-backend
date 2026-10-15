import uuid
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.models import StudentAttendance, StaffAttendance, Leave
from apps.school.models.school import Grade, Section, Student, Staff
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
        attendance_date = request.data.get("attendance_date")
        students_data = request.data.get("students")

        application_logger.info(
            "bulk_student_attendance_requested",
            requested_by=str(request.user.id),
            school_id=str(school.id) if school else None,
            grade_id=grade_id,
            section_id=section_id,
            attendance_date=attendance_date,
        )

        # Validate school
        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        # Get the staff record for the authenticated user
        staff = Staff.objects.filter(
            user=request.user,
            school=school,
            status=Staff.Status.ACTIVE,
        ).first()

        if staff is None:
            return CustomResponse.errorResponse(
                description="Active staff record not found for this user."
            )

        # Validate required fields
        required_fields = {
            "grade_id": grade_id,
            "section_id": section_id,
            "attendance_date": attendance_date,
            "students": students_data,
        }

        for field, value in required_fields.items():
            if value in [None, ""]:
                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        if not isinstance(students_data, list) or not students_data:
            return CustomResponse.errorResponse(
                description="Students must be a non-empty list."
            )

        # Validate UUIDs
        try:
            grade_uuid = uuid.UUID(str(grade_id))
            section_uuid = uuid.UUID(str(section_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid grade or section ID."
            )

        # Validate attendance date
        attendance_date = parse_date(str(attendance_date))

        if attendance_date is None:
            return CustomResponse.errorResponse(
                description="Invalid attendance date. Use YYYY-MM-DD."
            )

        if attendance_date > timezone.localdate():
            return CustomResponse.errorResponse(
                description="Attendance date cannot be in the future."
            )

        # Validate grade
        grade = Grade.objects.filter(
            id=grade_uuid,
            school=school,
        ).first()

        if grade is None:
            return CustomResponse.errorResponse(
                description="Grade not found."
            )

        # Validate section
        section = Section.objects.filter(
            id=section_uuid,
        ).first()

        if section is None:
            return CustomResponse.errorResponse(
                description="Section not found."
            )

        # Validate individual student attendance entries
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

        # Fetch all students in one query
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

        # Validate student-section and student-grade relationships
        for item in validated_students:
            student = students_by_id[item["student_id"]]

            if student.section_id != section.id:
                return CustomResponse.errorResponse(
                    description=(
                        f"Student {student.id} does not belong "
                        "to the selected section."
                    )
                )

            # Adjust this check if grade is related through another model.
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

        try:
            with transaction.atomic():

                for item in validated_students:
                    StudentAttendance.objects.update_or_create(
                        school=school,
                        student_id=item["student_id"],
                        attendance_date=attendance_date,
                        defaults={
                            "branch": staff.branch,
                            "grade": grade,
                            "section": section,
                            "status": item["status"],
                            "remarks": item["remarks"],
                            "marked_by": staff,
                        },
                    )

        except Exception as e:
            application_logger.exception(
                "bulk_student_attendance_failed",
                school_id=str(school.id),
                grade_id=str(grade.id),
                section_id=str(section.id),
                attendance_date=str(attendance_date),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Failed to save student attendance."
            )

        # Calculate attendance summary
        attendance_summary = {
            status: sum(
                1
                for item in validated_students
                if item["status"] == status
            )
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
        grade_id = request.query_params.get("grade_id")
        section_id = request.query_params.get("section_id")
        branch_id = request.query_params.get("branch_id")
        status = request.query_params.get("status")
        search = request.query_params.get("search")

        # Filter by exact attendance date
        if attendance_date:
            parsed_date = parse_date(attendance_date)

            if parsed_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid attendance_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date=parsed_date
            )

        # Filter by date range
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

        if start_date and end_date:
            if parsed_start_date > parsed_end_date:
                return CustomResponse.errorResponse(
                    description="start_date cannot be after end_date."
                )

        # Filter by student
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
            from django.db.models import Q

            attendance = attendance.filter(
                Q(student__name__icontains=search)
            )

        # Pagination
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(
            attendance,
            request,
        )

        data = [
            {
                "id": str(item.id),
                "student": {
                    "id": str(item.student_id),
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
                "marked_by": {
                    "id": str(item.marked_by_id),
                    "name": item.marked_by.name,
                } if item.marked_by_id else None,
            }
            for item in page
        ]

        return CustomResponse.successResponse(
            data=data,
            total=attendance.count(),
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

        # Get attendance record
        attendance = StudentAttendance.objects.filter(
            id=attendance_uuid,
            school=school,
        ).first()

        if attendance is None:
            return CustomResponse.errorResponse(
                description="Student attendance not found."
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

        # Validate status
        if "status" in request.data:
            status = request.data.get("status")

            if status not in StudentAttendance.AttendanceStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid attendance status."
                )

            attendance.status = status

        # Update remarks
        if "remarks" in request.data:
            attendance.remarks = request.data.get("remarks")

        # Update the staff member who made the correction
        attendance.marked_by = staff

        try:
            with transaction.atomic():
                attendance.save(
                    update_fields=[
                        "status",
                        "remarks",
                        "marked_by",
                        "updated_at",
                        "updated_by",
                    ]
                )

        except Exception as e:
            application_logger.exception(
                "student_attendance_update_failed",
                school_id=str(school.id),
                attendance_id=str(attendance.id),
                updated_by=str(request.user.id),
                error=str(e),
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

        # Get the authenticated user's staff record.
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

        # Validate request data.
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

        # Fetch all staff members in one query.
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
                description="One or more staff members were not found in this school."
            )

        try:
            with transaction.atomic():

                for item in validated_records:
                    member = staff_by_id[item["staff_id"]]

                    attendance, created = (
                        StaffAttendance.objects.update_or_create(
                            school=school,
                            staff=member,
                            attendance_date=attendance_date,
                            defaults={
                                "branch": member.branch,
                                "status": item["status"],
                                "check_in": item["check_in"],
                                "check_out": item["check_out"],
                                "remarks": item["remarks"],
                                "marked_by": marked_by,
                            },
                        )
                    )

        except Exception as e:
            application_logger.exception(
                "bulk_staff_attendance_failed",
                school_id=str(school.id),
                attendance_date=str(attendance_date),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Failed to save staff attendance."
            )

        summary = {
            status: sum(
                1 for item in validated_records
                if item["status"] == status
            )
            for status in StaffAttendance.AttendanceStatus.values
        }

        application_logger.info(
            "bulk_staff_attendance_marked",
            school_id=str(school.id),
            marked_by=str(marked_by.id),
            attendance_date=str(attendance_date),
            total_staff=len(validated_records),
        )

        return CustomResponse.successResponse(
            description="Staff attendance saved successfully.",
            data={
                "attendance_date": str(attendance_date),
                "total_staff": len(validated_records),
                "marked_by": {
                    "id": str(marked_by.id),
                    "name": marked_by.name,
                },
                "attendance_summary": summary,
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

        if attendance_date:
            parsed_date = parse_date(attendance_date)

            if parsed_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid attendance_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date=parsed_date
            )

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

        if status:
            if status not in StaffAttendance.AttendanceStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid attendance status."
                )

            attendance = attendance.filter(status=status)

        if search:
            attendance = attendance.filter(
                staff__name__icontains=search.strip()
            )

        total = attendance.count()

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(attendance, request)

        data = [
            {
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
                "check_in": str(item.check_in)
                if item.check_in else None,
                "check_out": str(item.check_out)
                if item.check_out else None,
                "remarks": item.remarks,
                "marked_by": {
                    "id": str(item.marked_by_id),
                    "name": item.marked_by.name,
                } if item.marked_by_id else None,
            }
            for item in page
        ]

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

        attendance = StaffAttendance.objects.filter(
            id=attendance_uuid,
            school=school,
        ).first()

        if attendance is None:
            return CustomResponse.errorResponse(
                description="Staff attendance not found."
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

        if "status" in request.data:
            status = request.data.get("status")

            if status not in StaffAttendance.AttendanceStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid attendance status."
                )

            attendance.status = status

        for field in ["check_in", "check_out"]:
            if field in request.data:
                value = request.data.get(field)

                if value in [None, ""]:
                    setattr(attendance, field, None)
                else:
                    parsed_time = parse_time(str(value))

                    if parsed_time is None:
                        return CustomResponse.errorResponse(
                            description=f"Invalid {field} time. Use HH:MM."
                        )

                    setattr(attendance, field, parsed_time)

        if (
            attendance.check_in
            and attendance.check_out
            and attendance.check_out <= attendance.check_in
        ):
            return CustomResponse.errorResponse(
                description="Check-out time must be after check-in time."
            )

        if "remarks" in request.data:
            attendance.remarks = request.data.get("remarks")

        attendance.marked_by = marked_by

        try:
            with transaction.atomic():
                attendance.save()

        except Exception as e:
            application_logger.exception(
                "staff_attendance_update_failed",
                school_id=str(school.id),
                attendance_id=str(attendance.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Failed to update staff attendance."
            )

        application_logger.info(
            "staff_attendance_updated",
            school_id=str(school.id),
            attendance_id=str(attendance.id),
            staff_id=str(attendance.staff_id),
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
                "check_in": str(attendance.check_in)
                if attendance.check_in else None,
                "check_out": str(attendance.check_out)
                if attendance.check_out else None,
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

        if attendance_date:
            parsed_date = parse_date(attendance_date)

            if parsed_date is None:
                return CustomResponse.errorResponse(
                    description="Invalid attendance_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date=parsed_date
            )

        if start_date:
            parsed_start = parse_date(start_date)

            if parsed_start is None:
                return CustomResponse.errorResponse(
                    description="Invalid start_date. Use YYYY-MM-DD."
                )

            attendance = attendance.filter(
                attendance_date__gte=parsed_start
            )

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
            start_date
            and end_date
            and parsed_start > parsed_end
        ):
            return CustomResponse.errorResponse(
                description="start_date cannot be after end_date."
            )

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

        summary = attendance.aggregate(
            total=Count("id"),
            present=Count(
                "id",
                filter=Q(status=StaffAttendance.AttendanceStatus.PRESENT),
            ),
            absent=Count(
                "id",
                filter=Q(status=StaffAttendance.AttendanceStatus.ABSENT),
            ),
            late=Count(
                "id",
                filter=Q(status=StaffAttendance.AttendanceStatus.LATE),
            ),
            half_day=Count(
                "id",
                filter=Q(status=StaffAttendance.AttendanceStatus.HALF_DAY),
            ),
            leave=Count(
                "id",
                filter=Q(status=StaffAttendance.AttendanceStatus.LEAVE),
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
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        duration = request.data.get("duration", "FULL_DAY")
        reason = request.data.get("reason")
        medical_document = request.data.get("medical_document")

        if not all([start_date, end_date, reason]):
            return CustomResponse.errorResponse(
                description="Dates and reason are required."
            )

        if leave_type not in Leave.LeaveType.values:
            return CustomResponse.errorResponse(
                description="Invalid leave type."
            )

        if duration not in Leave.LeaveDuration.values:
            return CustomResponse.errorResponse(
                description="Invalid leave duration."
            )

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

        total_days = (
            Decimal("0.5")
            if duration == Leave.LeaveDuration.HALF_DAY
            else Decimal((end_date - start_date).days + 1)
        )

        try:
            with transaction.atomic():
                leave = Leave.objects.create(
                    school=school,
                    branch=staff.branch,
                    applicant_type=Leave.ApplicantType.STAFF,
                    student=None,
                    staff=staff,
                    leave_type=leave_type,
                    start_date=start_date,
                    end_date=end_date,
                    duration=duration,
                    total_days=total_days,
                    reason=reason.strip(),
                    medical_document=medical_document,
                    status=Leave.LeaveStatus.PENDING,
                    created_by=request.user,
                )

            application_logger.info(
                "staff_leave_request_created",
                leave_id=str(leave.id),
                staff_id=str(staff.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "leave_id": str(leave.id),
                    "staff_id": str(staff.id),
                    "staff_name": staff.name,
                    "leave_type": leave.leave_type,
                    "start_date": str(leave.start_date),
                    "end_date": str(leave.end_date),
                    "duration": leave.duration,
                    "total_days": str(leave.total_days),
                    "reason": leave.reason,
                    "medical_document": leave.medical_document,
                    "status": leave.status,
                },
                description="Staff leave request submitted successfully."
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

            leaves = leaves.filter(start_date__gte=parsed_start_date)

        # Filter by end date.
        if end_date:
            parsed_end_date = parse_date(end_date)

            if not parsed_end_date:
                return CustomResponse.errorResponse(
                    description="Invalid end_date. Use YYYY-MM-DD."
                )

            leaves = leaves.filter(end_date__lte=parsed_end_date)

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
            data.append({
                "leave_id": str(leave.id),
                "student_id": str(leave.student_id),
                "student_name": leave.student.name,
                "branch_id": (
                    str(leave.branch_id) if leave.branch_id else None
                ),
                "leave_type": leave.leave_type,
                "start_date": str(leave.start_date),
                "end_date": str(leave.end_date),
                "duration": leave.duration,
                "total_days": str(leave.total_days),
                "reason": leave.reason,
                "medical_document": leave.medical_document,
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
        ).order_by("-created_at")

        status = request.query_params.get("status")
        staff_id = request.query_params.get("staff_id")
        leave_type = request.query_params.get("leave_type")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        search = request.query_params.get("search")

        if status:
            if status not in Leave.LeaveStatus.values:
                return CustomResponse.errorResponse(
                    description="Invalid leave status."
                )

            leaves = leaves.filter(status=status)

        if staff_id:
            leaves = leaves.filter(staff_id=staff_id)

        if leave_type:
            if leave_type not in Leave.LeaveType.values:
                return CustomResponse.errorResponse(
                    description="Invalid leave type."
                )

            leaves = leaves.filter(leave_type=leave_type)

        if start_date:
            parsed_start_date = parse_date(start_date)

            if not parsed_start_date:
                return CustomResponse.errorResponse(
                    description="Invalid start_date. Use YYYY-MM-DD."
                )

            leaves = leaves.filter(start_date__gte=parsed_start_date)

        if end_date:
            parsed_end_date = parse_date(end_date)

            if not parsed_end_date:
                return CustomResponse.errorResponse(
                    description="Invalid end_date. Use YYYY-MM-DD."
                )

            leaves = leaves.filter(end_date__lte=parsed_end_date)

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
            data.append({
                "leave_id": str(leave.id),
                "staff_id": str(leave.staff_id),
                "staff_name": leave.staff.name,
                "employee_id": leave.staff.employee_id,
                "staff_type": leave.staff.staff_type,
                "branch_id": (
                    str(leave.branch_id) if leave.branch_id else None
                ),
                "leave_type": leave.leave_type,
                "start_date": str(leave.start_date),
                "end_date": str(leave.end_date),
                "duration": leave.duration,
                "total_days": str(leave.total_days),
                "reason": leave.reason,
                "medical_document": leave.medical_document,
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

    def patch(self, request, leave_id):
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

                leave.status = status
                leave.reviewed_by = request.user
                leave.reviewed_at = timezone.now()
                leave.review_remarks = review_remarks
                leave.save()

                updated_attendance_count = 0

                if status == Leave.LeaveStatus.APPROVED:
                    updated_attendance_count = (
                        StudentAttendance.objects.filter(
                            school=school,
                            student=leave.student,
                            attendance_date__gte=leave.start_date,
                            attendance_date__lte=leave.end_date,
                            status=StudentAttendance.AttendanceStatus.ABSENT,
                        ).update(
                            status=StudentAttendance.AttendanceStatus.LEAVE
                        )
                    )

            application_logger.info(
                "student_leave_reviewed",
                leave_id=str(leave.id),
                status=status,
                reviewer_id=str(request.user.id),
                updated_attendance_count=updated_attendance_count,
            )

            return CustomResponse.successResponse(
                data={
                    "leave_id": str(leave.id),
                    "student_id": str(leave.student_id),
                    "status": leave.status,
                    "review_remarks": leave.review_remarks,
                    "updated_attendance_count": updated_attendance_count,
                },
                description=(
                    "Student leave approved successfully."
                    if status == Leave.LeaveStatus.APPROVED
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

    def patch(self, request, leave_id):
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

        # Identify the authenticated reviewer.
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

                # Prevent a Principal or Admin from approving their own leave.
                if leave.staff.user_id == request.user.id:
                    return CustomResponse.errorResponse(
                        description="You cannot review your own leave request."
                    )

                leave.status = status
                leave.reviewed_by = request.user
                leave.reviewed_at = timezone.now()
                leave.review_remarks = review_remarks
                leave.save()

                updated_attendance_count = 0

                if status == Leave.LeaveStatus.APPROVED:
                    updated_attendance_count = (
                        StaffAttendance.objects.filter(
                            school=school,
                            staff=leave.staff,
                            attendance_date__gte=leave.start_date,
                            attendance_date__lte=leave.end_date,
                            status=StaffAttendance.AttendanceStatus.ABSENT,
                        ).update(
                            status=StaffAttendance.AttendanceStatus.LEAVE
                        )
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
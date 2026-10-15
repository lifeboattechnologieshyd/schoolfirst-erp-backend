import uuid

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.models import StudentAttendance
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

class StudentAttendanceAPIView(APIView):

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
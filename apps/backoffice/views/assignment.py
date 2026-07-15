from django.db import transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.homework.models import Assignment, AssignmentSection
from apps.school.models.school import AcademicYear, Grade, Subject, Staff, Branch, Section
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class CreateAssignmentAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "assignment.create"

    def post(self, request):

        school = request.school

        application_logger.info(
            "assignment_create_started",
            user_id=str(request.user.id),
            school_id=str(school.id) if school else None,
        )

        try:

            if school is None:
                application_logger.warning(
                    "assignment_create_failed",
                    reason="school_not_found",
                    user_id=str(request.user.id),
                )

                return CustomResponse.errorResponse(
                    description="School not found."
                )

            required_fields = [
                "academic_year_id",
                "grade_id",
                "subject_id",
                "teacher_id",
                "section_ids",
                "title",
                "description",
                "assigned_date",
                "due_date",
                "total_marks",
            ]

            for field in required_fields:

                if request.data.get(field) in [None, "", []]:
                    application_logger.warning(
                        "assignment_create_failed",
                        reason="required_field_missing",
                        field=field,
                        school_id=str(school.id),
                    )

                    return CustomResponse.errorResponse(
                        description=f"{field} is required."
                    )
            academic_year = AcademicYear.objects.filter(
                id=request.data.get("academic_year_id"),
                school=school,
            ).first()

            if academic_year is None:
                application_logger.warning(
                    "assignment_create_failed",
                    reason="academic_year_not_found",
                    academic_year_id=request.data.get("academic_year_id"),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description="Academic year not found."
                )

            grade = Grade.objects.filter(
                id=request.data.get("grade_id"),
                school=school,
                academic_year=academic_year,
            ).first()

            if grade is None:
                application_logger.warning(
                    "homework_create_failed",
                    reason="grade_not_found",
                    grade_id=request.data.get("grade_id"),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

            subject = Subject.objects.filter(
                id=request.data.get("subject_id"),
                school=school,
                academic_year=academic_year,
                status=Subject.Status.ACTIVE,
            ).first()

            if subject is None:
                application_logger.warning(
                    "homework_create_failed",
                    reason="subject_not_found",
                    subject_id=request.data.get("subject_id"),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description="Subject not found."
                )

            teacher = Staff.objects.filter(
                id=request.data.get("teacher_id"),
                school=school,
                status=Staff.Status.ACTIVE,
            ).first()

            if teacher is None:
                application_logger.warning(
                    "homework_create_failed",
                    reason="teacher_not_found",
                    teacher_id=request.data.get("teacher_id"),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description="Teacher not found."
                )
            branch = None

            branch_id = request.data.get("branch_id")

            if branch_id:

                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school,
                ).first()

                if branch is None:
                    application_logger.warning(
                        "homework_create_failed",
                        reason="branch_not_found",
                        branch_id=branch_id,
                        school_id=str(school.id),
                    )

                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

            section_ids = request.data.get("section_ids")

            if not isinstance(section_ids, list):
                application_logger.warning(
                    "homework_create_failed",
                    reason="invalid_section_ids",
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description="section_ids must be a list."
                )

            section_ids = list(set(section_ids))

            sections = Section.objects.filter(
                id__in=section_ids,
                grade=grade,
                branch=branch,
            )

            if sections.count() != len(section_ids):
                application_logger.warning(
                    "homework_create_failed",
                    reason="invalid_sections",
                    section_ids=section_ids,
                    grade_id=str(grade.id),
                    branch_id=str(branch.id) if branch else None,
                )

                return CustomResponse.errorResponse(
                    description="One or more sections are invalid."
                )
            total_marks = request.data.get("total_marks")

            try:

                total_marks = int(total_marks)

            except (TypeError, ValueError):

                return CustomResponse.errorResponse(
                    description="total_marks must be a number."
                )

            if total_marks <= 0:
                return CustomResponse.errorResponse(
                    description="total_marks must be greater than zero."
                )
            status = request.data.get(
                "status",
                Assignment.Status.DRAFT,
            )

            if status not in Assignment.Status.values:
                return CustomResponse.errorResponse(
                    description="Invalid status."
                )
            assigned_date = request.data.get("assigned_date")

            due_date = request.data.get("due_date")

            if due_date < assigned_date:
                return CustomResponse.errorResponse(
                    description="Due date must be greater than or equal to assigned date."
                )
            with transaction.atomic():

                assignment = Assignment.objects.create(
                    school=school,
                    branch=branch,
                    academic_year=academic_year,
                    grade=grade,
                    subject=subject,
                    teacher=teacher,
                    title=request.data.get("title").strip(),
                    description=request.data.get("description").strip(),
                    assigned_date=assigned_date,
                    due_date=due_date,
                    total_marks=total_marks,
                    status=status,
                )

                AssignmentSection.objects.bulk_create(
                    [
                        AssignmentSection(
                            assignment=assignment,
                            section=section,
                        )
                        for section in sections
                    ]
                )
            application_logger.info(
                "assignment_created",
                assignment_id=str(assignment.id),
                school_id=str(school.id),
                grade_id=str(grade.id),
                subject_id=str(subject.id),
                teacher_id=str(teacher.id),
                section_count=len(section_ids),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Assignment created successfully.",
                data={
                    "id": str(assignment.id),
                    "title": assignment.title,
                },
            )
        except Exception as e:

            application_logger.exception(
                "assignment_create_failed",
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while creating assignment."
            )
class AssignmentListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "assignment.view"

    def get(self, request):

        school = request.school

        application_logger.info(
            "assignment_list_started",
            user_id=str(request.user.id),
            school_id=str(school.id) if school else None,
        )

        try:

            if school is None:

                application_logger.warning(
                    "assignment_list_failed",
                    reason="school_not_found",
                    user_id=str(request.user.id),
                )

                return CustomResponse.errorResponse(
                    description="School not found."
                )

            assignments = Assignment.objects.select_related(
                "academic_year",
                "branch",
                "grade",
                "subject",
                "teacher",
            ).prefetch_related(
                "assignment_sections__section",
            ).filter(
                school=school,
            )

            academic_year_id = request.query_params.get("academic_year_id")
            branch_id = request.query_params.get("branch_id")
            grade_id = request.query_params.get("grade_id")
            subject_id = request.query_params.get("subject_id")
            teacher_id = request.query_params.get("teacher_id")
            section_id = request.query_params.get("section_id")
            status = request.query_params.get("status")
            assigned_date = request.query_params.get("assigned_date")
            due_date = request.query_params.get("due_date")
            search = request.query_params.get("search")

            if academic_year_id:

                assignments = assignments.filter(
                    academic_year_id=academic_year_id,
                )

            if branch_id:

                assignments = assignments.filter(
                    branch_id=branch_id,
                )

            if grade_id:

                assignments = assignments.filter(
                    grade_id=grade_id,
                )

            if subject_id:

                assignments = assignments.filter(
                    subject_id=subject_id,
                )

            if teacher_id:

                assignments = assignments.filter(
                    teacher_id=teacher_id,
                )

            if section_id:

                assignments = assignments.filter(
                    assignment_sections__section_id=section_id,
                )

            if status:

                assignments = assignments.filter(
                    status=status,
                )

            if assigned_date:

                assignments = assignments.filter(
                    assigned_date=assigned_date,
                )

            if due_date:

                assignments = assignments.filter(
                    due_date=due_date,
                )

            if search:

                assignments = assignments.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                )

            assignments = assignments.distinct().order_by(
                "-assigned_date",
                "-created_at",
            )

            data = []

            for assignment in assignments:

                data.append({
                    "id": str(assignment.id),
                    "title": assignment.title,
                    "description": assignment.description,
                    "assigned_date": assignment.assigned_date,
                    "due_date": assignment.due_date,
                    "total_marks": assignment.total_marks,
                    "status": assignment.status,
                    "academic_year": {
                        "id": str(assignment.academic_year.id),
                        "name": assignment.academic_year.name,
                    },
                    "branch": {
                        "id": str(assignment.branch.id),
                        "name": assignment.branch.name,
                    } if assignment.branch else None,
                    "grade": {
                        "id": str(assignment.grade.id),
                        "name": assignment.grade.name,
                    },
                    "subject": {
                        "id": str(assignment.subject.id),
                        "name": assignment.subject.name,
                    },
                    "teacher": {
                        "id": str(assignment.teacher.id),
                        "name": assignment.teacher.name,
                    },
                    "sections": [
                        {
                            "id": str(item.section.id),
                            "name": item.section.name,
                        }
                        for item in assignment.assignment_sections.all()
                    ],
                })

            application_logger.info(
                "assignment_list_fetched",
                school_id=str(school.id),
                user_id=str(request.user.id),
                total_count=len(data),
            )

            return CustomResponse.successResponse(
                description="Assignments fetched successfully.",
                data=data,
                total_count=len(data),
            )

        except Exception:

            application_logger.exception(
                "assignment_list_failed",
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching assignments."
            )

class AssignmentUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "assignment.update"

    def put(self, request, assignment_id):

        school = request.school

        application_logger.info(
            "assignment_update_started",
            user_id=str(request.user.id),
            school_id=str(school.id) if school else None,
            assignment_id=str(assignment_id),
        )

        try:

            if school is None:

                application_logger.warning(
                    "assignment_update_failed",
                    reason="school_not_found",
                    user_id=str(request.user.id),
                )

                return CustomResponse.errorResponse(
                    description="School not found."
                )

            assignment = Assignment.objects.filter(
                id=assignment_id,
                school=school,
            ).first()

            if assignment is None:

                application_logger.warning(
                    "assignment_update_failed",
                    reason="assignment_not_found",
                    assignment_id=str(assignment_id),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description="Assignment not found."
                )

            academic_year = assignment.academic_year

            if "academic_year_id" in request.data:

                academic_year = AcademicYear.objects.filter(
                    id=request.data.get("academic_year_id"),
                    school=school,
                ).first()

                if academic_year is None:

                    return CustomResponse.errorResponse(
                        description="Academic year not found."
                    )

            grade = assignment.grade

            if "grade_id" in request.data:

                grade = Grade.objects.filter(
                    id=request.data.get("grade_id"),
                    school=school,
                    academic_year=academic_year,
                ).first()

                if grade is None:

                    return CustomResponse.errorResponse(
                        description="Grade not found."
                    )

            subject = assignment.subject

            if "subject_id" in request.data:

                subject = Subject.objects.filter(
                    id=request.data.get("subject_id"),
                    school=school,
                    academic_year=academic_year,
                    status=Subject.Status.ACTIVE,
                ).first()

                if subject is None:

                    return CustomResponse.errorResponse(
                        description="Subject not found."
                    )

            teacher = assignment.teacher

            if "teacher_id" in request.data:

                teacher = Staff.objects.filter(
                    id=request.data.get("teacher_id"),
                    school=school,
                    status=Staff.Status.ACTIVE,
                ).first()

                if teacher is None:

                    return CustomResponse.errorResponse(
                        description="Teacher not found."
                    )

            branch = assignment.branch

            if "branch_id" in request.data:

                branch_id = request.data.get("branch_id")

                if branch_id:

                    branch = Branch.objects.filter(
                        id=branch_id,
                        school=school,
                    ).first()

                    if branch is None:

                        return CustomResponse.errorResponse(
                            description="Branch not found."
                        )

                else:

                    branch = None

            sections = None

            if "section_ids" in request.data:

                section_ids = request.data.get("section_ids")

                if not isinstance(section_ids, list):

                    return CustomResponse.errorResponse(
                        description="section_ids must be a list."
                    )

                section_ids = list(set(section_ids))

                sections = Section.objects.filter(
                    id__in=section_ids,
                    grade=grade,
                    branch=branch,
                )

                if sections.count() != len(section_ids):

                    return CustomResponse.errorResponse(
                        description="One or more sections are invalid."
                    )

            status = assignment.status

            if "status" in request.data:

                status = request.data.get("status")

                if status not in Assignment.Status.values:

                    return CustomResponse.errorResponse(
                        description="Invalid status."
                    )

            assigned_date = request.data.get(
                "assigned_date",
                assignment.assigned_date,
            )

            due_date = request.data.get(
                "due_date",
                assignment.due_date,
            )

            if due_date < assigned_date:

                return CustomResponse.errorResponse(
                    description="Due date must be greater than or equal to assigned date."
                )

            total_marks = assignment.total_marks

            if "total_marks" in request.data:

                try:

                    total_marks = int(
                        request.data.get("total_marks")
                    )

                except (TypeError, ValueError):

                    return CustomResponse.errorResponse(
                        description="total_marks must be a number."
                    )

                if total_marks <= 0:

                    return CustomResponse.errorResponse(
                        description="total_marks must be greater than zero."
                    )
            with transaction.atomic():

                if "academic_year_id" in request.data:
                    assignment.academic_year = academic_year

                if "grade_id" in request.data:
                    assignment.grade = grade

                if "subject_id" in request.data:
                    assignment.subject = subject

                if "teacher_id" in request.data:
                    assignment.teacher = teacher

                if "branch_id" in request.data:
                    assignment.branch = branch

                if "title" in request.data:
                    assignment.title = request.data.get("title").strip()

                if "description" in request.data:
                    assignment.description = request.data.get("description").strip()

                if "assigned_date" in request.data:
                    assignment.assigned_date = assigned_date

                if "due_date" in request.data:
                    assignment.due_date = due_date

                if "status" in request.data:
                    assignment.status = status

                if "total_marks" in request.data:
                    assignment.total_marks = total_marks

                assignment.save()

                if "section_ids" in request.data:

                    AssignmentSection.objects.filter(
                        assignment=assignment,
                    ).delete()

                    AssignmentSection.objects.bulk_create(
                        [
                            AssignmentSection(
                                assignment=assignment,
                                section=section,
                            )
                            for section in sections
                        ]
                    )

            application_logger.info(
                "assignment_updated",
                assignment_id=str(assignment.id),
                school_id=str(school.id),
                branch_id=str(assignment.branch.id) if assignment.branch else None,
                academic_year_id=str(assignment.academic_year.id),
                grade_id=str(assignment.grade.id),
                subject_id=str(assignment.subject.id),
                teacher_id=str(assignment.teacher.id),
                section_count=(
                    assignment.assignment_sections.count()
                ),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Assignment updated successfully.",
                data={
                    "id": str(assignment.id),
                    "title": assignment.title,
                },
            )

        except Exception as e:

            application_logger.exception(
                "assignment_update_failed",
                assignment_id=str(assignment_id),
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while updating assignment."
            )

from django.db import transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.models import CalendarEvent, CalendarEventTarget
from apps.homework.models import Homework, HomeworkSubmission, HomeworkSection
from apps.school.models.school import Staff, Section, Branch, Subject, Grade, AcademicYear, Student
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.calendar import create_calendar_event
from shared.utils.logger import application_logger


class CreateHomeworkAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "homework.create"

    def post(self, request):

        school = request.school

        application_logger.info(
            "homework_create_started",
            user_id=str(request.user.id),
            school_id=str(school.id) if school else None,
        )

        if school is None:

            application_logger.warning(
                "homework_create_failed",
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
        ]

        for field in required_fields:

            if request.data.get(field) in [None, "", []]:

                application_logger.warning(
                    "homework_create_failed",
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
                "homework_create_failed",
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

        status = request.data.get(
            "status",
            Homework.Status.DRAFT,
        )

        if status not in Homework.Status.values:
            application_logger.warning(
                "homework_create_failed",
                reason="invalid_status",
                status=status,
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Invalid status."
            )

        assigned_date = request.data.get("assigned_date")

        due_date = request.data.get("due_date")

        if due_date < assigned_date:
            application_logger.warning(
                "homework_create_failed",
                reason="invalid_due_date",
                assigned_date=assigned_date,
                due_date=due_date,
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Due date must be greater than or equal to assigned date."
            )
        try:

            with transaction.atomic():

                homework = Homework.objects.create(
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
                    status=status,
                )

                HomeworkSection.objects.bulk_create(
                    [
                        HomeworkSection(
                            homework=homework,
                            section=section,
                        )
                        for section in sections
                    ]
                )
                create_calendar_event(
                    school=school,
                    title=homework.title,
                    description=homework.description,
                    event_type=CalendarEvent.EventType.HOMEWORK,
                    event_date=homework.due_date,
                    reference_id=homework.id,
                    target_type=CalendarEventTarget.TargetType.SECTION,
                    academic_year=academic_year,
                    branch=branch,
                    grade=grade,
                    sections=sections,
                )


        except Exception as e:

            application_logger.exception(
                "homework_create_failed",
                school_id=str(school.id),
                user_id=str(request.user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while creating homework."
            )

        application_logger.info(
            "homework_created",
            homework_id=str(homework.id),
            school_id=str(school.id),
            branch_id=str(branch.id) if branch else None,
            academic_year_id=str(academic_year.id),
            grade_id=str(grade.id),
            subject_id=str(subject.id),
            teacher_id=str(teacher.id),
            section_count=len(section_ids),
            user_id=str(request.user.id),
        )

        return CustomResponse.successResponse(
            description="Homework created successfully.",
            data={
                "id": str(homework.id),
                "title": homework.title,
            },
        )


class HomeworkListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "homework.view"

    def get(self, request):

        school = request.school

        application_logger.info(
            "homework_list_started",
            user_id=str(request.user.id),
            school_id=str(school.id) if school else None,
        )

        try:

            if school is None:

                application_logger.warning(
                    "homework_list_failed",
                    reason="school_not_found",
                    user_id=str(request.user.id),
                )

                return CustomResponse.errorResponse(
                    description="School not found."
                )

            homeworks = Homework.objects.select_related(
                "academic_year",
                "branch",
                "grade",
                "subject",
                "teacher",
            ).prefetch_related(
                "homework_sections__section",
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
                homeworks = homeworks.filter(
                    academic_year_id=academic_year_id,
                )

            if branch_id:
                homeworks = homeworks.filter(
                    branch_id=branch_id,
                )

            if grade_id:
                homeworks = homeworks.filter(
                    grade_id=grade_id,
                )

            if subject_id:
                homeworks = homeworks.filter(
                    subject_id=subject_id,
                )

            if teacher_id:
                homeworks = homeworks.filter(
                    teacher_id=teacher_id,
                )

            if section_id:
                homeworks = homeworks.filter(
                    homework_sections__section_id=section_id,
                )

            if status:
                homeworks = homeworks.filter(
                    status=status,
                )

            if assigned_date:
                homeworks = homeworks.filter(
                    assigned_date=assigned_date,
                )

            if due_date:
                homeworks = homeworks.filter(
                    due_date=due_date,
                )

            if search:
                homeworks = homeworks.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                )

            homeworks = homeworks.distinct().order_by(
                "-assigned_date",
                "-created_at",
            )

            data = []

            for homework in homeworks:

                data.append({
                    "id": str(homework.id),
                    "title": homework.title,
                    "description": homework.description,
                    "assigned_date": homework.assigned_date,
                    "due_date": homework.due_date,
                    "status": homework.status,
                    "academic_year": {
                        "id": str(homework.academic_year.id),
                        "name": homework.academic_year.name,
                    },
                    "branch": {
                        "id": str(homework.branch.id),
                        "name": homework.branch.name,
                    } if homework.branch else None,
                    "grade": {
                        "id": str(homework.grade.id),
                        "name": homework.grade.name,
                    },
                    "subject": {
                        "id": str(homework.subject.id),
                        "name": homework.subject.name,
                    },
                    "teacher": {
                        "id": str(homework.teacher.id),
                        "name": homework.teacher.name,
                    },
                    "sections": [
                        {
                            "id": str(item.section.id),
                            "name": item.section.name,
                        }
                        for item in homework.homework_sections.all()
                    ],
                })

            application_logger.info(
                "homework_list_fetched",
                school_id=str(school.id),
                user_id=str(request.user.id),
                total_count=len(data),
            )

            return CustomResponse.successResponse(
                description="Homeworks fetched successfully.",
                data=data,
                total_count=len(data),
            )

        except Exception:

            application_logger.exception(
                "homework_list_failed",
                school_id=str(school.id) if school else None,
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching homeworks."
            )



class HomeworkUpdateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "homework.update"

    def put(self, request, homework_id):

        school = request.school
        user = request.user

        application_logger.info(
            "homework_update_started",
            user_id=str(user.id),
            school_id=str(school.id) if school else None,
            homework_id=str(homework_id),
        )

        try:

            if school is None:

                application_logger.warning(
                    "homework_update_failed",
                    reason="school_not_found",
                    user_id=str(user.id),
                )

                return CustomResponse.errorResponse(
                    description="School not found."
                )

            homework = Homework.objects.filter(
                id=homework_id,
                school=school,
            ).first()

            if homework is None:

                application_logger.warning(
                    "homework_update_failed",
                    reason="homework_not_found",
                    homework_id=str(homework_id),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description="Homework not found."
                )

            academic_year = homework.academic_year

            if "academic_year_id" in request.data:

                academic_year = AcademicYear.objects.filter(
                    id=request.data.get("academic_year_id"),
                    school=school,
                ).first()

                if academic_year is None:

                    return CustomResponse.errorResponse(
                        description="Academic year not found."
                    )

            grade = homework.grade

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

            subject = homework.subject

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

            teacher = homework.teacher

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

            branch = homework.branch

            if "branch_id" in request.data:

                branch_id = request.data.get("branch_id")

                if branch_id:

                    branch = Branch.objects.filter(
                        id=branch_id,
                        school=school,
                    ).first()

                    if branch is None:

                        application_logger.warning(
                            "homework_update_failed",
                            reason="branch_not_found",
                            branch_id=branch_id,
                            homework_id=str(homework.id),
                        )

                        return CustomResponse.errorResponse(
                            description="Branch not found."
                        )

                else:

                    branch = None

            sections = None

            if "section_ids" in request.data:

                section_ids = request.data.get("section_ids")

                if not isinstance(section_ids, list):

                    application_logger.warning(
                        "homework_update_failed",
                        reason="invalid_section_ids",
                        homework_id=str(homework.id),
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
                        "homework_update_failed",
                        reason="invalid_sections",
                        homework_id=str(homework.id),
                    )

                    return CustomResponse.errorResponse(
                        description="One or more sections are invalid."
                    )

            status = request.data.get(
                "status",
                homework.status,
            )

            if status not in Homework.Status.values:

                return CustomResponse.errorResponse(
                    description="Invalid status."
                )

            assigned_date = request.data.get(
                "assigned_date",
                homework.assigned_date,
            )

            due_date = request.data.get(
                "due_date",
                homework.due_date,
            )

            if due_date < assigned_date:

                return CustomResponse.errorResponse(
                    description="Due date must be greater than or equal to assigned date."
                )
            with transaction.atomic():

                if "branch_id" in request.data:
                    homework.branch = branch

                if "academic_year_id" in request.data:
                    homework.academic_year = academic_year

                if "grade_id" in request.data:
                    homework.grade = grade

                if "subject_id" in request.data:
                    homework.subject = subject

                if "teacher_id" in request.data:
                    homework.teacher = teacher

                if "title" in request.data:
                    homework.title = request.data.get(
                        "title",
                    ).strip()

                if "description" in request.data:
                    homework.description = request.data.get(
                        "description",
                    ).strip()

                if "assigned_date" in request.data:
                    homework.assigned_date = assigned_date

                if "due_date" in request.data:
                    homework.due_date = due_date

                if "status" in request.data:
                    homework.status = status

                homework.save()

                if sections is not None:

                    HomeworkSection.objects.filter(
                        homework=homework,
                    ).delete()

                    HomeworkSection.objects.bulk_create(
                        [
                            HomeworkSection(
                                homework=homework,
                                section=section,
                            )
                            for section in sections
                        ]
                    )

            application_logger.info(
                "homework_updated",
                homework_id=str(homework.id),
                school_id=str(school.id),
                branch_id=str(homework.branch.id)
                if homework.branch
                else None,
                academic_year_id=str(homework.academic_year.id),
                grade_id=str(homework.grade.id),
                subject_id=str(homework.subject.id),
                teacher_id=str(homework.teacher.id),
                section_count=(
                    HomeworkSection.objects.filter(
                        homework=homework,
                    ).count()
                ),
                user_id=str(user.id),
            )

            return CustomResponse.successResponse(
                description="Homework updated successfully.",
                data={
                    "id": str(homework.id),
                    "title": homework.title,
                },
            )

        except Exception as e:

            application_logger.exception(
                "homework_update_failed",
                homework_id=str(homework_id),
                school_id=str(school.id) if school else None,
                user_id=str(user.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while updating homework."
            )





class TeacherHomeworkSubmissionListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "homework.submission.view"

    def get(self, request, homework_id):

        school = request.school

        application_logger.info(
            "teacher_homework_submission_list_started",
            user_id=str(request.user.id),
            school_id=str(school.id) if school else None,
            homework_id=str(homework_id),
        )

        try:

            if school is None:

                return CustomResponse.errorResponse(
                    description="School not found."
                )

            homework = Homework.objects.select_related(
                "grade",
                "subject",
                "teacher",
                "academic_year",
            ).prefetch_related(
                "homework_sections__section",
            ).filter(
                id=homework_id,
                school=school,
            ).first()

            if homework is None:

                application_logger.warning(
                    "teacher_homework_submission_list_failed",
                    reason="homework_not_found",
                    homework_id=str(homework_id),
                )

                return CustomResponse.errorResponse(
                    description="Homework not found."
                )

            students = Student.objects.select_related(
                "section",
            ).filter(
                grade=homework.grade,
                section__homework_sections__homework=homework,
                status=Student.Status.ACTIVE,
            ).distinct().order_by(
                "roll_number",
            )

            submissions = HomeworkSubmission.objects.prefetch_related(
                "attachments",
            ).filter(
                homework=homework,
            )

            submission_map = {
                submission.student_id: submission
                for submission in submissions
            }
            sections = [
                {
                    "id": str(homework_section.section.id),
                    "name": homework_section.section.name,
                }
                for homework_section in homework.homework_sections.all()
            ]

            data = []

            for student in students:

                submission = submission_map.get(
                    student.id,
                )

                data.append({

                    "student": {

                        "id": str(student.id),
                        "admission_number": student.admission_number,
                        "roll_number": student.roll_number,
                        "name": student.name,
                        "photo_url": student.photo_url,
                    },

                    "submission": {

                        "status": (
                            submission.status
                            if submission
                            else HomeworkSubmission.Status.PENDING
                        ),

                        "submitted_at": (
                            submission.submitted_at
                            if submission
                            else None
                        ),

                        "remarks": (
                            submission.remarks
                            if submission
                            else None
                        ),

                        "teacher_remarks": (
                            submission.teacher_remarks
                            if submission
                            else None
                        ),

                        "attachments": [

                            {
                                "id": str(file.id),
                                "file_name": file.file_name,
                                "file_url": file.file_url,
                            }

                            for file in (
                                submission.attachments.all()
                                if submission
                                else []
                            )

                        ],

                    },

                })

            application_logger.info(
                "teacher_homework_submission_list_fetched",
                user_id=str(request.user.id),
                homework_id=str(homework.id),
                total_count=len(data),
            )

            return CustomResponse.successResponse(
                description="Homework submissions fetched successfully.",
                data={
                    "homework": {
                        "id": str(homework.id),
                        "title": homework.title,
                        "subject": homework.subject.name,
                        "grade": homework.grade.name,
                        "academic_year": homework.academic_year.name,

                    },
                    "sections": sections,
                    "students": data,
                },
                total_count=len(data),
            )

        except Exception:

            application_logger.exception(
                "teacher_homework_submission_list_failed",
                user_id=str(request.user.id),
                homework_id=str(homework_id),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching homework submissions."
            )


class TeacherCheckHomeworkAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "homework.check"

    def put(self, request, submission_id):

        school = request.school

        application_logger.info(
            "teacher_homework_check_started",
            user_id=str(request.user.id),
            school_id=str(school.id) if school else None,
            submission_id=str(submission_id),
        )

        try:

            if school is None:

                return CustomResponse.errorResponse(
                    description="School not found."
                )

            teacher_remarks = request.data.get("teacher_remarks")

            status = request.data.get(
                "status",
                HomeworkSubmission.Status.CHECKED,
            )

            if status not in HomeworkSubmission.Status.values:

                return CustomResponse.errorResponse(
                    description="Invalid status."
                )

            submission = HomeworkSubmission.objects.select_related(
                "homework",
                "student",
                "homework__school",
            ).filter(
                id=submission_id,
                homework__school=school,
            ).first()

            if submission is None:

                application_logger.warning(
                    "teacher_homework_check_failed",
                    reason="submission_not_found",
                    submission_id=str(submission_id),
                )

                return CustomResponse.errorResponse(
                    description="Homework submission not found."
                )

            with transaction.atomic():

                submission.teacher_remarks = teacher_remarks
                submission.status = status

                submission.save(
                    update_fields=[
                        "teacher_remarks",
                        "status",
                        "updated_at",
                    ]
                )

            application_logger.info(
                "teacher_homework_checked",
                user_id=str(request.user.id),
                submission_id=str(submission.id),
                homework_id=str(submission.homework.id),
                student_id=str(submission.student.id),
            )

            return CustomResponse.successResponse(
                description="Homework checked successfully.",
                data={
                    "submission_id": str(submission.id),
                    "status": submission.status,
                    "teacher_remarks": submission.teacher_remarks,
                },
            )

        except Exception:

            application_logger.exception(
                "teacher_homework_check_failed",
                user_id=str(request.user.id),
                submission_id=str(submission_id),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while checking homework."
            )
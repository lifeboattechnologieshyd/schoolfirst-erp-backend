from django.db import transaction
from django.db.models import Q, Max, Avg, F
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from decimal import Decimal,InvalidOperation
from openpyxl import load_workbook
from apps.examination.models import ExaminationType, Examination, ExaminationGrade, ExaminationSchedule, \
    ExaminationResult, GradeConfiguration
from apps.school.models.school import Branch, AcademicYear, Grade, Subject, SubjectGrade, Student
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger
from django.db import transaction
from io import BytesIO
from rest_framework.parsers import MultiPartParser, FormParser

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

class ExaminationTypeCreateAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission]

    required_permission = "examination_type.create"


    def post(self, request):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        name = request.data.get("name")
        description = request.data.get("description")
        branch_id = request.data.get("branch_id")
        weightage = request.data.get("weightage", 0)
        max_marks = request.data.get("max_marks", 100)
        frequency = request.data.get("frequency", 1)
        duration = request.data.get("duration")
        status = request.data.get(
            "status",
            ExaminationType.Status.ACTIVE,
        )

        if not name:
            return CustomResponse.errorResponse(
                description="Examination type name is required."
            )

        if branch_id:
            branch = Branch.objects.filter(
                id=branch_id,
                school=school,
            ).first()

            if not branch:
                return CustomResponse.errorResponse(
                    description="Invalid branch."
                )
        else:
            branch = None

        if ExaminationType.objects.filter(
            school=school,
            name__iexact=name.strip(),
        ).exists():
            return CustomResponse.errorResponse(
                description="Examination type already exists."
            )

        try:
            weightage = float(weightage)
            max_marks = float(max_marks)
            frequency = int(frequency)

            if weightage < 0 or weightage > 100:
                return CustomResponse.errorResponse(
                    description="Weightage must be between 0 and 100."
                )

            if max_marks <= 0:
                return CustomResponse.errorResponse(
                    description="Maximum marks must be greater than 0."
                )

            if frequency <= 0:
                return CustomResponse.errorResponse(
                    description="Frequency must be greater than 0."
                )

            if duration is not None:
                duration = int(duration)

                if duration <= 0:
                    return CustomResponse.errorResponse(
                        description="Duration must be greater than 0."
                    )

            examination_type = ExaminationType.objects.create(
                school=school,
                branch=branch,
                name=name.strip(),
                description=description,
                weightage=weightage,
                max_marks=max_marks,
                frequency=frequency,
                duration=duration,
                status=status,
            )

            application_logger.info(
                "examination_type_created",
                examination_type_id=str(examination_type.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": examination_type.id,
                    "name": examination_type.name,
                    "description": examination_type.description,
                    "branch_id": examination_type.branch_id,
                    "weightage": examination_type.weightage,
                    "max_marks": examination_type.max_marks,
                    "frequency": examination_type.frequency,
                    "duration": examination_type.duration,
                    "status": examination_type.status,
                },
                description="Examination type created successfully.",
            )

        except ValueError:
            return CustomResponse.errorResponse(
                description="Invalid numeric value provided."
            )

        except Exception as e:
            application_logger.exception(
                "examination_type_create_failed",
                error=str(e),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to create examination type."
            )


class ExaminationTypeListAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "examination_type.view"

    def get(self, request):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            queryset = ExaminationType.objects.filter(
                school=school
            ).select_related("branch")

            search = request.query_params.get("search")
            status = request.query_params.get("status")
            branch_id = request.query_params.get("branch_id")

            if search:
                queryset = queryset.filter(
                    name__icontains=search.strip()
                )

            if status:
                queryset = queryset.filter(status=status)

            if branch_id:
                queryset = queryset.filter(
                    branch_id=branch_id
                )

            queryset = queryset.order_by("name")

            data = [
                {
                    "id": examination_type.id,
                    "name": examination_type.name,
                    "description": examination_type.description,
                    "branch_id": examination_type.branch_id,
                    "branch_name": (
                        examination_type.branch.name
                        if examination_type.branch
                        else None
                    ),
                    "weightage": examination_type.weightage,
                    "max_marks": examination_type.max_marks,
                    "frequency": examination_type.frequency,
                    "duration": examination_type.duration,
                    "status": examination_type.status,
                }
                for examination_type in queryset
            ]

            return CustomResponse.successResponse(
                data=data,
                description="Examination types fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "examination_type_list_failed",
                error=str(e),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch examination types."
            )


class ExaminationTypeUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "examination_type.update"

    def put(self, request, examination_type_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            examination_type = ExaminationType.objects.filter(
                id=examination_type_id,
                school=school,
            ).first()

            if not examination_type:
                return CustomResponse.errorResponse(
                    description="Examination type not found."
                )

            name = request.data.get("name")
            description = request.data.get("description")
            branch_id = request.data.get("branch_id")
            weightage = request.data.get("weightage")
            max_marks = request.data.get("max_marks")
            frequency = request.data.get("frequency")
            duration = request.data.get("duration")
            status = request.data.get("status")

            if name is not None:
                name = name.strip()

                if not name:
                    return CustomResponse.errorResponse(
                        description="Examination type name is required."
                    )

                if ExaminationType.objects.filter(
                    school=school,
                    name__iexact=name,
                ).exclude(
                    id=examination_type.id
                ).exists():
                    return CustomResponse.errorResponse(
                        description="Examination type already exists."
                    )

                examination_type.name = name

            if description is not None:
                examination_type.description = description

            if branch_id is not None:
                if branch_id:
                    branch = Branch.objects.filter(
                        id=branch_id,
                        school=school,
                    ).first()

                    if not branch:
                        return CustomResponse.errorResponse(
                            description="Invalid branch."
                        )

                    examination_type.branch = branch
                else:
                    examination_type.branch = None

            if weightage is not None:
                weightage = float(weightage)

                if weightage < 0 or weightage > 100:
                    return CustomResponse.errorResponse(
                        description="Weightage must be between 0 and 100."
                    )

                examination_type.weightage = weightage

            if max_marks is not None:
                max_marks = float(max_marks)

                if max_marks <= 0:
                    return CustomResponse.errorResponse(
                        description="Maximum marks must be greater than 0."
                    )

                examination_type.max_marks = max_marks

            if frequency is not None:
                frequency = int(frequency)

                if frequency <= 0:
                    return CustomResponse.errorResponse(
                        description="Frequency must be greater than 0."
                    )

                examination_type.frequency = frequency

            if duration is not None:
                duration = int(duration)

                if duration <= 0:
                    return CustomResponse.errorResponse(
                        description="Duration must be greater than 0."
                    )

                examination_type.duration = duration

            if status is not None:
                if status not in dict(ExaminationType.Status.choices):
                    return CustomResponse.errorResponse(
                        description="Invalid examination type status."
                    )

                examination_type.status = status

            examination_type.save()

            application_logger.info(
                "examination_type_updated",
                examination_type_id=str(examination_type.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": examination_type.id,

                },
                description="Examination type updated successfully.",
            )

        except ValueError:
            return CustomResponse.errorResponse(
                description="Invalid numeric value provided."
            )

        except Exception as e:
            application_logger.exception(
                "examination_type_update_failed",
                error=str(e),
                examination_type_id=str(examination_type_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update examination type."
            )


class GradeSubjectListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "subject.view"

    def get(self, request):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        academic_year_id = request.query_params.get(
            "academic_year_id"
        )

        if not academic_year_id:
            return CustomResponse.errorResponse(
                description="Academic year is required."
            )

        try:
            grades = (
                Grade.objects
                .filter(
                    school=school,
                    academic_year_id=academic_year_id,
                    status=Grade.Status.ACTIVE,
                )
                .prefetch_related(
                    "grade_subjects__subject"
                )
                .order_by("display_order", "name")
            )

            data = []

            for grade in grades:

                subjects = []

                for subject_grade in grade.grade_subjects.all():

                    subject = subject_grade.subject

                    if subject.status != Subject.Status.ACTIVE:
                        continue

                    subjects.append({
                        "id": subject.id,
                        "name": subject.name,
                    })

                data.append({
                    "id": grade.id,
                    "name": grade.name,
                    "subjects": subjects,
                })

            return CustomResponse.successResponse(
                data=data,
                total=len(data),
                description="Grade subjects fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "grade_subject_list_failed",
                error=str(e),
                school_id=str(school.id),
                academic_year_id=str(academic_year_id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch grade subjects."
            )


class ExaminationCreateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "examination.create"

    def post(self, request):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        name = request.data.get("name")
        examination_type_id = request.data.get("examination_type_id")
        academic_year_id = request.data.get("academic_year_id")
        branch_id = request.data.get("branch_id")

        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        result_date = request.data.get("result_date")
        reporting_date = request.data.get("reporting_date")

        description = request.data.get("description")
        grades_data = request.data.get("grades", [])

        # ---------------------------------
        # Required validations
        # ---------------------------------

        if not name:
            return CustomResponse.errorResponse(
                description="Examination name is required."
            )

        if not examination_type_id:
            return CustomResponse.errorResponse(
                description="Examination type is required."
            )

        if not academic_year_id:
            return CustomResponse.errorResponse(
                description="Academic year is required."
            )

        if not start_date:
            return CustomResponse.errorResponse(
                description="Start date is required."
            )

        if not end_date:
            return CustomResponse.errorResponse(
                description="End date is required."
            )

        if not grades_data:
            return CustomResponse.errorResponse(
                description="At least one grade is required."
            )

        # ---------------------------------
        # Validate dates
        # ---------------------------------

        if start_date > end_date:
            return CustomResponse.errorResponse(
                description="Start date cannot be after end date."
            )

        if result_date and result_date < end_date:
            return CustomResponse.errorResponse(
                description="Result date cannot be before examination end date."
            )

        try:
            # ---------------------------------
            # Validate examination type
            # ---------------------------------

            examination_type = ExaminationType.objects.filter(
                id=examination_type_id,
                school=school,
                status=ExaminationType.Status.ACTIVE,
            ).first()

            if not examination_type:
                return CustomResponse.errorResponse(
                    description="Invalid examination type."
                )

            # ---------------------------------
            # Validate academic year
            # ---------------------------------

            academic_year = AcademicYear.objects.filter(
                id=academic_year_id,
                school=school,
            ).first()

            if not academic_year:
                return CustomResponse.errorResponse(
                    description="Invalid academic year."
                )

            # ---------------------------------
            # Validate branch
            # ---------------------------------

            branch = None

            if branch_id:
                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school,
                ).first()

                if not branch:
                    return CustomResponse.errorResponse(
                        description="Invalid branch."
                    )

            # ---------------------------------
            # Duplicate examination
            # ---------------------------------

            if Examination.objects.filter(
                school=school,
                academic_year=academic_year,
                name__iexact=name.strip(),
            ).exists():
                return CustomResponse.errorResponse(
                    description="Examination with this name already exists."
                )

            with transaction.atomic():

                # ---------------------------------
                # Create examination
                # ---------------------------------

                examination = Examination.objects.create(
                    school=school,
                    branch=branch,
                    academic_year=academic_year,
                    examination_type=examination_type,
                    name=name.strip(),
                    start_date=start_date,
                    end_date=end_date,
                    result_date=result_date,
                    reporting_date = reporting_date,
                    status=Examination.Status.DRAFT,
                    description=description,
                )

                created_grades = []

                # ---------------------------------
                # Grades
                # ---------------------------------

                for grade_data in grades_data:

                    grade_id = grade_data.get("grade_id")
                    schedules_data = grade_data.get("schedules", [])

                    if not grade_id:
                        raise ValueError("Grade is required.")

                    if not schedules_data:
                        raise ValueError(
                            "At least one subject schedule is required."
                        )

                    # ---------------------------------
                    # Validate grade
                    # ---------------------------------

                    grade = Grade.objects.filter(
                        id=grade_id,
                        school=school,
                        academic_year=academic_year,
                        status=Grade.Status.ACTIVE,
                    ).first()

                    if not grade:
                        raise ValueError("Invalid grade.")

                    # ---------------------------------
                    # Duplicate grade
                    # ---------------------------------

                    if ExaminationGrade.objects.filter(
                        examination=examination,
                        grade=grade,
                    ).exists():
                        raise ValueError(
                            f"Grade {grade.name} is already assigned."
                        )

                    examination_grade = ExaminationGrade.objects.create(
                        examination=examination,
                        grade=grade,
                    )

                    created_schedules = []

                    # ---------------------------------
                    # Subjects / schedules
                    # ---------------------------------

                    for schedule_data in schedules_data:

                        subject_id = schedule_data.get("subject_id")
                        exam_date = schedule_data.get("exam_date")
                        start_time = schedule_data.get("start_time")
                        end_time = schedule_data.get("end_time")

                        room_number = schedule_data.get("room_number")

                        maximum_marks = schedule_data.get(
                            "maximum_marks"
                        )

                        passing_marks = schedule_data.get(
                            "passing_marks"
                        )

                        internal_percentage = schedule_data.get(
                            "internal_percentage",
                            0,
                        )

                        external_percentage = schedule_data.get(
                            "external_percentage",
                            0,
                        )

                        practical_percentage = schedule_data.get(
                            "practical_percentage",
                            0,
                        )

                        instructions = schedule_data.get(
                            "instructions"
                        )

                        # ---------------------------------
                        # Required fields
                        # ---------------------------------

                        if not subject_id:
                            raise ValueError(
                                "Subject is required."
                            )

                        if not exam_date:
                            raise ValueError(
                                "Exam date is required."
                            )

                        if not start_time:
                            raise ValueError(
                                "Start time is required."
                            )

                        if not end_time:
                            raise ValueError(
                                "End time is required."
                            )

                        if maximum_marks is None:
                            raise ValueError(
                                "Maximum marks is required."
                            )

                        if passing_marks is None:
                            raise ValueError(
                                "Passing marks is required."
                            )

                        # ---------------------------------
                        # Validate subject
                        # ---------------------------------

                        subject = Subject.objects.filter(
                            id=subject_id,
                            school=school,
                            status=Subject.Status.ACTIVE,
                        ).first()

                        if not subject:
                            raise ValueError(
                                "Invalid subject."
                            )

                        # ---------------------------------
                        # Subject must belong to grade
                        # ---------------------------------

                        if not SubjectGrade.objects.filter(
                            subject=subject,
                            grade=grade,
                        ).exists():
                            raise ValueError(
                                f"Subject {subject.name} "
                                f"is not assigned to grade {grade.name}."
                            )

                        # ---------------------------------
                        # Validate exam date
                        # ---------------------------------

                        if not (
                            examination.start_date
                            <= exam_date
                            <= examination.end_date
                        ):
                            raise ValueError(
                                "Exam date must be within the examination "
                                "start and end dates."
                            )

                        # ---------------------------------
                        # Validate time
                        # ---------------------------------

                        if start_time >= end_time:
                            raise ValueError(
                                "Start time must be before end time."
                            )

                        # ---------------------------------
                        # Convert marks
                        # ---------------------------------

                        maximum_marks = Decimal(
                            str(maximum_marks)
                        )

                        passing_marks = Decimal(
                            str(passing_marks)
                        )

                        if maximum_marks <= 0:
                            raise ValueError(
                                "Maximum marks must be greater than 0."
                            )

                        if passing_marks < 0:
                            raise ValueError(
                                "Passing marks cannot be negative."
                            )

                        if passing_marks > maximum_marks:
                            raise ValueError(
                                "Passing marks cannot exceed maximum marks."
                            )

                        # ---------------------------------
                        # Convert percentages
                        # ---------------------------------

                        internal_percentage = Decimal(
                            str(internal_percentage)
                        )

                        external_percentage = Decimal(
                            str(external_percentage)
                        )

                        practical_percentage = Decimal(
                            str(practical_percentage)
                        )

                        # ---------------------------------
                        # Validate percentages
                        # ---------------------------------

                        for percentage in [
                            internal_percentage,
                            external_percentage,
                            practical_percentage,
                        ]:
                            if percentage < 0 or percentage > 100:
                                raise ValueError(
                                    "Percentage must be between 0 and 100."
                                )

                        percentage_total = (
                            internal_percentage
                            + external_percentage
                            + practical_percentage
                        )

                        if percentage_total != Decimal("100"):
                            raise ValueError(
                                "Internal, external and practical "
                                "percentages must total 100%."
                            )

                        # ---------------------------------
                        # Duplicate subject
                        # ---------------------------------

                        if ExaminationSchedule.objects.filter(
                            examination=examination,
                            grade=grade,
                            subject=subject,
                        ).exists():
                            raise ValueError(
                                f"{subject.name} is already scheduled "
                                f"for this examination."
                            )

                        # ---------------------------------
                        # Overlapping schedule
                        # ---------------------------------

                        overlapping_schedule = (
                            ExaminationSchedule.objects
                            .filter(
                                examination=examination,
                                grade=grade,
                                exam_date=exam_date,
                            )
                            .filter(
                                start_time__lt=end_time,
                                end_time__gt=start_time,
                            )
                            .exists()
                        )

                        if overlapping_schedule:
                            raise ValueError(
                                "Another subject is already scheduled "
                                "during this time for this grade."
                            )

                        # ---------------------------------
                        # Create schedule
                        # ---------------------------------

                        schedule = ExaminationSchedule.objects.create(
                            examination=examination,
                            grade=grade,
                            subject=subject,
                            exam_date=exam_date,
                            start_time=start_time,
                            end_time=end_time,
                            room_number=room_number,
                            maximum_marks=maximum_marks,
                            passing_marks=passing_marks,
                            internal_percentage=internal_percentage,
                            external_percentage=external_percentage,
                            practical_percentage=practical_percentage,
                            instructions=instructions,
                        )

                        created_schedules.append({
                            "id": schedule.id,
                            "subject_id": subject.id,
                            "subject_name": subject.name,
                            "exam_date": schedule.exam_date,
                            "start_time": schedule.start_time,
                            "end_time": schedule.end_time,
                            "room_number": schedule.room_number,
                            "maximum_marks": schedule.maximum_marks,
                            "passing_marks": schedule.passing_marks,
                            "internal_percentage": (
                                schedule.internal_percentage
                            ),
                            "external_percentage": (
                                schedule.external_percentage
                            ),
                            "practical_percentage": (
                                schedule.practical_percentage
                            ),
                            "instructions": schedule.instructions,
                        })

                    created_grades.append({
                        "id": examination_grade.id,
                        "grade_id": grade.id,
                        "grade_name": grade.name,
                        "schedules": created_schedules,
                    })

                # ---------------------------------
                # Log
                # ---------------------------------

                application_logger.info(
                    "examination_created",
                    examination_id=str(examination.id),
                    school_id=str(school.id),
                )

                return CustomResponse.successResponse(
                    data={
                        "id": examination.id,
                        "name": examination.name,
                        "academic_year_id": examination.academic_year_id,
                        "examination_type_id": examination.examination_type_id,
                        "branch_id": examination.branch_id,
                        "start_date": examination.start_date,
                        "end_date": examination.end_date,
                        "result_date": examination.result_date,
                        "status": examination.status,
                        "grades": created_grades,
                    },
                    description="Examination created successfully.",
                )

        except ValueError as e:

            return CustomResponse.errorResponse(
                description=str(e)
            )

        except Exception as e:

            application_logger.exception(
                "examination_create_failed",
                error=str(e),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to create examination."
            )


class ExaminationListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "examination.view"

    def get(self, request):

        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            queryset = (
                Examination.objects
                .filter(
                    school=school
                )
                .select_related(
                    "examination_type",
                    "academic_year",
                    "branch",
                )
                .prefetch_related(
                    "examination_grades__grade",
                    "schedules__subject",
                )
            )

            search = request.query_params.get("search")
            status = request.query_params.get("status")
            academic_year_id = request.query_params.get(
                "academic_year_id"
            )
            branch_id = request.query_params.get(
                "branch_id"
            )

            if search:
                queryset = queryset.filter(
                    name__icontains=search.strip()
                )

            if status:
                queryset = queryset.filter(
                    status=status
                )

            if academic_year_id:
                queryset = queryset.filter(
                    academic_year_id=academic_year_id
                )

            if branch_id:
                queryset = queryset.filter(
                    branch_id=branch_id
                )

            queryset = queryset.order_by("-start_date")

            data = []

            for examination in queryset:

                # -------------------------
                # Grades
                # -------------------------

                grades = []

                for examination_grade in examination.examination_grades.all():
                    grade = examination_grade.grade

                    subjects = [
                        {
                            "subject_id": str(schedule.subject_id),
                            "subject_name": schedule.subject.name,

                            "exam_date": schedule.exam_date,
                            "start_time": schedule.start_time,
                            "end_time": schedule.end_time,

                            "room_number": schedule.room_number,

                            "maximum_marks": schedule.maximum_marks,
                            "passing_marks": schedule.passing_marks,

                            "internal_percentage": schedule.internal_percentage,
                            "external_percentage": schedule.external_percentage,
                            "practical_percentage": schedule.practical_percentage,

                            "instructions": schedule.instructions,
                        }
                        for schedule in examination.schedules.all()
                        if schedule.grade_id == grade.id
                    ]

                    grades.append({
                        "id": str(grade.id),
                        "name": grade.name,
                        "subjects": subjects,
                    })



                data.append({
                    "id": str(examination.id),
                    "name": examination.name,

                    "examination_type_id": str(
                        examination.examination_type_id
                    ),
                    "examination_type_name": (
                        examination.examination_type.name
                    ),

                    "academic_year_id": str(
                        examination.academic_year_id
                    ),
                    "academic_year_name": (
                        examination.academic_year.name
                    ),

                    "branch_id": (
                        str(examination.branch_id)
                        if examination.branch_id
                        else None
                    ),
                    "branch_name": (
                        examination.branch.name
                        if examination.branch
                        else None
                    ),

                    "start_date": examination.start_date,
                    "end_date": examination.end_date,
                    "reporting_date": examination.reporting_date,
                    "result_date": examination.result_date,

                    "description": examination.description,
                    "status": examination.status,

                    "grades": grades,
                })

            return CustomResponse.successResponse(
                total=len(data),
                data=data,
                description="Examinations fetched successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "examination_list_failed",
                error=str(e),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch examinations."
            )




class ExaminationUpdateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "examination.update"

    def put(self, request, examination_id):

        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            with transaction.atomic():

                examination = (
                    Examination.objects
                    .select_for_update()
                    .filter(
                        id=examination_id,
                        school=school,
                    )
                    .first()
                )

                if not examination:
                    return CustomResponse.errorResponse(
                        description="Examination not found."
                    )

                name = request.data.get("name")
                examination_type_id = request.data.get(
                    "examination_type_id"
                )
                academic_year_id = request.data.get(
                    "academic_year_id"
                )
                branch_id = request.data.get("branch_id")
                start_date = request.data.get("start_date")
                end_date = request.data.get("end_date")
                result_date = request.data.get("result_date")
                reporting_date = request.data.get("reporting_date")
                description = request.data.get("description")
                status = request.data.get("status")

                # --------------------------------
                # Name
                # --------------------------------

                if name is not None:

                    name = name.strip()

                    if not name:
                        return CustomResponse.errorResponse(
                            description="Examination name is required."
                        )

                    examination.name = name

                # --------------------------------
                # Examination Type
                # --------------------------------

                if examination_type_id is not None:

                    examination_type = (
                        ExaminationType.objects
                        .filter(
                            id=examination_type_id,
                            school=school,
                        )
                        .first()
                    )

                    if not examination_type:
                        return CustomResponse.errorResponse(
                            description="Invalid examination type."
                        )

                    examination.examination_type = examination_type

                # --------------------------------
                # Academic Year
                # --------------------------------

                if academic_year_id is not None:

                    academic_year = (
                        AcademicYear.objects
                        .filter(
                            id=academic_year_id,
                            school=school,
                        )
                        .first()
                    )

                    if not academic_year:
                        return CustomResponse.errorResponse(
                            description="Invalid academic year."
                        )

                    examination.academic_year = academic_year

                # --------------------------------
                # Branch
                # --------------------------------

                if branch_id is not None:

                    if branch_id:

                        branch = (
                            Branch.objects
                            .filter(
                                id=branch_id,
                                school=school,
                            )
                            .first()
                        )

                        if not branch:
                            return CustomResponse.errorResponse(
                                description="Invalid branch."
                            )

                        examination.branch = branch

                    else:
                        examination.branch = None

                # --------------------------------
                # Dates
                # --------------------------------

                if start_date is not None:
                    examination.start_date = start_date

                if end_date is not None:
                    examination.end_date = end_date

                if result_date is not None:
                    examination.result_date = result_date
                if reporting_date is not None:
                    examination.reporting_date = reporting_date


                if examination.start_date > examination.end_date:
                    return CustomResponse.errorResponse(
                        description="Start date cannot be after end date."
                    )

                if result_date is not None:
                    if examination.result_date < examination.end_date:
                        return CustomResponse.errorResponse(
                            description="Result date cannot be before examination end date."
                        )

                if status is not None:
                    examination.status = status

                # --------------------------------
                # Description
                # --------------------------------

                if description is not None:
                    examination.description = description

                # --------------------------------
                # Grades
                # --------------------------------

                grade_ids = request.data.get("grade_ids")

                if grade_ids is not None:

                    if not isinstance(grade_ids, list):
                        return CustomResponse.errorResponse(
                            description="grade_ids must be an array."
                        )

                    grade_ids = list(set(grade_ids))

                    if not grade_ids:
                        return CustomResponse.errorResponse(
                            description="At least one grade is required."
                        )

                    grades = Grade.objects.filter(
                        id__in=grade_ids,
                        school=school,
                        academic_year=examination.academic_year,
                        status=Grade.Status.ACTIVE,
                    )

                    if grades.count() != len(grade_ids):
                        return CustomResponse.errorResponse(
                            description="One or more grades are invalid."
                        )

                    # Replace existing grade mappings
                    ExaminationGrade.objects.filter(
                        examination=examination
                    ).delete()

                    ExaminationGrade.objects.bulk_create(
                        [
                            ExaminationGrade(
                                examination=examination,
                                grade=grade,
                            )
                            for grade in grades
                        ]
                    )

                # --------------------------------
                # Save Examination
                # --------------------------------

                examination.save()

            application_logger.info(
                "examination_updated",
                examination_id=str(examination.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": examination.id,
                },
                description="Examination updated successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "examination_update_failed",
                error=str(e),
                examination_id=str(examination_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update examination."
            )



class ExaminationGradeCreateAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "examination_grade.create"

    def post(self, request, examination_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        grade_id = request.data.get("grade_id")

        if not grade_id:
            return CustomResponse.errorResponse(
                description="Grade is required."
            )

        try:
            examination = Examination.objects.filter(
                id=examination_id,
                school=school,
            ).first()

            if not examination:
                return CustomResponse.errorResponse(
                    description="Examination not found."
                )

            if examination.status != Examination.Status.DRAFT:
                return CustomResponse.errorResponse(
                    description="Grades can only be added to a draft examination."
                )

            grade = Grade.objects.filter(
                id=grade_id,
                school=school,
                academic_year=examination.academic_year,
                status=Grade.Status.ACTIVE,
            ).first()

            if not grade:
                return CustomResponse.errorResponse(
                    description="Invalid grade."
                )

            if ExaminationGrade.objects.filter(
                examination=examination,
                grade=grade,
            ).exists():
                return CustomResponse.errorResponse(
                    description="Grade is already assigned to this examination."
                )

            examination_grade = ExaminationGrade.objects.create(
                examination=examination,
                grade=grade,
            )

            application_logger.info(
                "examination_grade_created",
                examination_grade_id=str(examination_grade.id),
                examination_id=str(examination.id),
                grade_id=str(grade.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": examination_grade.id,
                    "examination_id": examination.id,
                    "grade_id": grade.id,
                    "grade_name": grade.name,
                },
                description="Grade added to examination successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "examination_grade_create_failed",
                error=str(e),
                examination_id=str(examination_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to add grade to examination."
            )

class ExaminationGradeListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission,]

    required_permission = "examination_grade.view"


    def get(self, request, examination_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            examination = Examination.objects.filter(
                id=examination_id,
                school=school,
            ).first()

            if not examination:
                return CustomResponse.errorResponse(
                    description="Examination not found."
                )

            queryset = (
                ExaminationGrade.objects
                .filter(
                    examination=examination,
                    grade__school=school,
                )
                .select_related("grade")
                .order_by("grade__display_order")
            )

            # -------------------------
            # Search
            # -------------------------

            search = request.query_params.get("search")

            if search:
                queryset = queryset.filter(
                    grade__name__icontains=search.strip()
                )

            # -------------------------
            # Pagination
            # -------------------------

            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))

            page_size = min(page_size, 100)

            total_count = queryset.count()

            start = (page - 1) * page_size
            end = start + page_size

            queryset = queryset[start:end]

            data = [
                {
                    "id": examination_grade.id,
                    "examination_id": examination_grade.examination_id,
                    "grade_id": examination_grade.grade_id,
                    "grade_name": examination_grade.grade.name,
                    "display_order": examination_grade.grade.display_order,
                }
                for examination_grade in queryset
            ]



            return CustomResponse.successResponse(
                total=total_count,
                data=data,
                description="Examination grades fetched successfully.",
            )

        except ValueError:
            return CustomResponse.errorResponse(
                description="Invalid pagination parameters."
            )

        except Exception as e:
            application_logger.exception(
                "examination_grade_list_failed",
                error=str(e),
                examination_id=str(examination_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch examination grades."
            )


class ExaminationGradeUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission,]

    required_permission = "examination_grade.update"

    def put(self, request, examination_id, examination_grade_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        grade_id = request.data.get("grade_id")

        if not grade_id:
            return CustomResponse.errorResponse(
                description="Grade is required."
            )

        try:
            examination = Examination.objects.filter(
                id=examination_id,
                school=school,
            ).first()

            if not examination:
                return CustomResponse.errorResponse(
                    description="Examination not found."
                )

            if examination.status != Examination.Status.DRAFT:
                return CustomResponse.errorResponse(
                    description="Grades can only be updated for a draft examination."
                )

            examination_grade = ExaminationGrade.objects.filter(
                id=examination_grade_id,
                examination=examination,
            ).first()

            if not examination_grade:
                return CustomResponse.errorResponse(
                    description="Examination grade not found."
                )

            grade = Grade.objects.filter(
                id=grade_id,
                school=school,
                academic_year=examination.academic_year,
                status=Grade.Status.ACTIVE,
            ).first()

            if not grade:
                return CustomResponse.errorResponse(
                    description="Invalid grade."
                )

            if ExaminationGrade.objects.filter(
                examination=examination,
                grade=grade,
            ).exclude(
                id=examination_grade.id
            ).exists():
                return CustomResponse.errorResponse(
                    description="Grade is already assigned to this examination."
                )

            examination_grade.grade = grade
            examination_grade.save(
                update_fields=["grade"]
            )

            application_logger.info(
                "examination_grade_updated",
                examination_grade_id=str(examination_grade.id),
                examination_id=str(examination.id),
                grade_id=str(grade.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": examination_grade.id,
                    "examination_id": examination.id,
                    "grade_id": grade.id,
                    "grade_name": grade.name,
                },
                description="Examination grade updated successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "examination_grade_update_failed",
                error=str(e),
                examination_id=str(examination_id),
                examination_grade_id=str(examination_grade_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update examination grade."
            )

class ExaminationGradeSubjectListAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "examination_subject.view"

    def get(self, request, examination_id, grade_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            examination = Examination.objects.filter(
                id=examination_id,
                school=school,
            ).first()

            if not examination:
                return CustomResponse.errorResponse(
                    description="Examination not found."
                )

            grade = Grade.objects.filter(
                id=grade_id,
                school=school,
                academic_year=examination.academic_year,
                status=Grade.Status.ACTIVE,
            ).first()

            if not grade:
                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

            examination_grade_exists = ExaminationGrade.objects.filter(
                examination=examination,
                grade=grade,
            ).exists()

            if not examination_grade_exists:
                return CustomResponse.errorResponse(
                    description="Grade is not assigned to this examination."
                )

            subject_grades = (
                SubjectGrade.objects
                .filter(
                    grade=grade,
                    subject__school=school,
                    subject__status=Subject.Status.ACTIVE,
                )
                .select_related("subject")
                .order_by("subject__name")
            )

            schedules = ExaminationSchedule.objects.filter(
                examination=examination,
                grade=grade,
            ).values_list(
                "subject_id",
                flat=True,
            )

            scheduled_subject_ids = set(schedules)

            data = [
                {
                    "subject_id": subject_grade.subject.id,
                    "subject_name": subject_grade.subject.name,
                    "has_exam": subject_grade.subject.id
                    in scheduled_subject_ids,
                }
                for subject_grade in subject_grades
            ]

            return CustomResponse.successResponse(
                data=data,
                description="Subjects fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "examination_grade_subject_list_failed",
                error=str(e),
                examination_id=str(examination_id),
                grade_id=str(grade_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch subjects."
            )


class ExaminationScheduleCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission,]

    required_permission = "examination_schedule.create"

    def post(self, request, examination_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        grade_id = request.data.get("grade_id")
        subject_id = request.data.get("subject_id")
        exam_date = request.data.get("exam_date")
        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")
        room_number = request.data.get("room_number")
        maximum_marks = request.data.get("maximum_marks")
        passing_marks = request.data.get("passing_marks")
        instructions = request.data.get("instructions")

        if not grade_id:
            return CustomResponse.errorResponse(
                description="Grade is required."
            )

        if not subject_id:
            return CustomResponse.errorResponse(
                description="Subject is required."
            )

        if not exam_date:
            return CustomResponse.errorResponse(
                description="Exam date is required."
            )

        if not start_time:
            return CustomResponse.errorResponse(
                description="Start time is required."
            )

        if not end_time:
            return CustomResponse.errorResponse(
                description="End time is required."
            )

        if maximum_marks is None:
            return CustomResponse.errorResponse(
                description="Maximum marks is required."
            )

        if passing_marks is None:
            return CustomResponse.errorResponse(
                description="Passing marks is required."
            )

        try:
            examination = Examination.objects.filter(
                id=examination_id,
                school=school,
            ).first()

            if not examination:
                return CustomResponse.errorResponse(
                    description="Examination not found."
                )

            if examination.status != Examination.Status.DRAFT:
                return CustomResponse.errorResponse(
                    description="Schedule can only be created for a draft examination."
                )

            # -------------------------
            # Validate grade
            # -------------------------

            grade = Grade.objects.filter(
                id=grade_id,
                school=school,
                academic_year=examination.academic_year,
                status=Grade.Status.ACTIVE,
            ).first()

            if not grade:
                return CustomResponse.errorResponse(
                    description="Invalid grade."
                )

            # -------------------------
            # Grade must belong to exam
            # -------------------------

            if not ExaminationGrade.objects.filter(
                examination=examination,
                grade=grade,
            ).exists():
                return CustomResponse.errorResponse(
                    description="Grade is not assigned to this examination."
                )

            # -------------------------
            # Validate subject
            # -------------------------

            subject = Subject.objects.filter(
                id=subject_id,
                school=school,
                status=Subject.Status.ACTIVE,
            ).first()

            if not subject:
                return CustomResponse.errorResponse(
                    description="Invalid subject."
                )

            # -------------------------
            # Subject must belong to grade
            # -------------------------

            if not SubjectGrade.objects.filter(
                subject=subject,
                grade=grade,
            ).exists():
                return CustomResponse.errorResponse(
                    description="Subject is not assigned to this grade."
                )

            # -------------------------
            # Duplicate schedule
            # -------------------------

            if ExaminationSchedule.objects.filter(
                examination=examination,
                grade=grade,
                subject=subject,
            ).exists():
                return CustomResponse.errorResponse(
                    description="This subject is already scheduled for the examination."
                )

            # -------------------------
            # Validate date
            # -------------------------

            if not (
                examination.start_date
                <= exam_date
                <= examination.end_date
            ):
                return CustomResponse.errorResponse(
                    description=(
                        "Exam date must be within the examination "
                        "start and end dates."
                    )
                )

            # -------------------------
            # Validate time
            # -------------------------

            if start_time >= end_time:
                return CustomResponse.errorResponse(
                    description="Start time must be before end time."
                )

            # -------------------------
            # Validate marks
            # -------------------------

            maximum_marks = float(maximum_marks)
            passing_marks = float(passing_marks)

            if maximum_marks <= 0:
                return CustomResponse.errorResponse(
                    description="Maximum marks must be greater than 0."
                )

            if passing_marks < 0:
                return CustomResponse.errorResponse(
                    description="Passing marks cannot be negative."
                )

            if passing_marks > maximum_marks:
                return CustomResponse.errorResponse(
                    description="Passing marks cannot exceed maximum marks."
                )

            # -------------------------
            # Prevent overlapping exams
            # for same grade/date
            # -------------------------

            overlapping_schedule = (
                ExaminationSchedule.objects
                .filter(
                    examination=examination,
                    grade=grade,
                    exam_date=exam_date,
                )
                .filter(
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                )
                .exists()
            )

            if overlapping_schedule:
                return CustomResponse.errorResponse(
                    description=(
                        "Another subject is already scheduled "
                        "during this time for this grade."
                    )
                )

            # -------------------------
            # Create schedule
            # -------------------------

            schedule = ExaminationSchedule.objects.create(
                examination=examination,
                grade=grade,
                subject=subject,
                exam_date=exam_date,
                start_time=start_time,
                end_time=end_time,
                room_number=room_number,
                maximum_marks=maximum_marks,
                passing_marks=passing_marks,
                instructions=instructions,
            )

            application_logger.info(
                "examination_schedule_created",
                schedule_id=str(schedule.id),
                examination_id=str(examination.id),
                grade_id=str(grade.id),
                subject_id=str(subject.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": schedule.id,
                    "examination_id": examination.id,
                    "grade_id": grade.id,
                    "grade_name": grade.name,
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "exam_date": schedule.exam_date,
                    "start_time": schedule.start_time,
                    "end_time": schedule.end_time,
                    "room_number": schedule.room_number,
                    "maximum_marks": schedule.maximum_marks,
                    "passing_marks": schedule.passing_marks,
                    "instructions": schedule.instructions,
                },
                description="Examination schedule created successfully.",
            )

        except ValueError:
            return CustomResponse.errorResponse(
                description="Invalid marks value."
            )

        except Exception as e:
            application_logger.exception(
                "examination_schedule_create_failed",
                error=str(e),
                examination_id=str(examination_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to create examination schedule."
            )





class ExaminationScheduleListAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "examination_schedule.view"

    def get(self, request, examination_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            examination = Examination.objects.filter(
                id=examination_id,
                school=school,
            ).first()

            if not examination:
                return CustomResponse.errorResponse(
                    description="Examination not found."
                )

            queryset = (
                ExaminationSchedule.objects
                .filter(
                    examination=examination,
                    grade__school=school,
                    subject__school=school,
                )
                .select_related(
                    "grade",
                    "subject",
                )
                .order_by(
                    "exam_date",
                    "start_time",
                    "grade__display_order",
                    "subject__name",
                )
            )

            # -------------------------
            # Filters
            # -------------------------

            grade_id = request.query_params.get("grade_id")
            subject_id = request.query_params.get("subject_id")
            exam_date = request.query_params.get("exam_date")
            search = request.query_params.get("search")

            if grade_id:
                queryset = queryset.filter(
                    grade_id=grade_id
                )

            if subject_id:
                queryset = queryset.filter(
                    subject_id=subject_id
                )

            if exam_date:
                queryset = queryset.filter(
                    exam_date=exam_date
                )

            if search:
                queryset = queryset.filter(
                    subject__name__icontains=search.strip()
                )

            # -------------------------
            # Pagination
            # -------------------------

            try:
                page = max(
                    int(request.query_params.get("page", 1)),
                    1,
                )

                page_size = max(
                    int(request.query_params.get("page_size", 20)),
                    1,
                )

            except ValueError:
                return CustomResponse.errorResponse(
                    description="Invalid pagination parameters."
                )

            page_size = min(page_size, 100)

            total_count = queryset.count()



            start = (page - 1) * page_size
            end = start + page_size

            schedules = queryset[start:end]

            # -------------------------
            # Response data
            # -------------------------

            data = [
                {
                    "id": schedule.id,
                    "examination_id": schedule.examination_id,

                    "grade_id": schedule.grade_id,
                    "grade_name": schedule.grade.name,

                    "subject_id": schedule.subject_id,
                    "subject_name": schedule.subject.name,

                    "exam_date": schedule.exam_date,
                    "start_time": schedule.start_time,
                    "end_time": schedule.end_time,

                    "room_number": schedule.room_number,

                    "maximum_marks": schedule.maximum_marks,
                    "passing_marks": schedule.passing_marks,

                    "internal_percentage":schedule.internal_percentage,


                    "instructions": schedule.instructions,
                }
                for schedule in schedules
            ]

            return CustomResponse.successResponse(
                total=total_count,

                data=data,
                description="Examination schedules fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "examination_schedule_list_failed",
                error=str(e),
                examination_id=str(examination_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch examination schedules."
            )


class ExaminationScheduleUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "examination_schedule.update"

    def put(self, request, schedule_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            schedule = (
                ExaminationSchedule.objects
                .select_related(
                    "examination",
                    "grade",
                    "subject",
                )
                .filter(
                    id=schedule_id,
                    examination__school=school,
                )
                .first()
            )

            if not schedule:
                return CustomResponse.errorResponse(
                    description="Examination schedule not found."
                )

            examination = schedule.examination

            if examination.status != Examination.Status.DRAFT:
                return CustomResponse.errorResponse(
                    description=(
                        "Schedule can only be updated "
                        "for a draft examination."
                    )
                )

            exam_date = request.data.get(
                "exam_date",
                schedule.exam_date,
            )

            start_time = request.data.get(
                "start_time",
                schedule.start_time,
            )

            end_time = request.data.get(
                "end_time",
                schedule.end_time,
            )

            room_number = request.data.get(
                "room_number",
                schedule.room_number,
            )

            maximum_marks = request.data.get(
                "maximum_marks",
                schedule.maximum_marks,
            )

            passing_marks = request.data.get(
                "passing_marks",
                schedule.passing_marks,
            )

            instructions = request.data.get(
                "instructions",
                schedule.instructions,
            )

            # -------------------------
            # Validate exam date
            # -------------------------

            if not (
                examination.start_date
                <= exam_date
                <= examination.end_date
            ):
                return CustomResponse.errorResponse(
                    description=(
                        "Exam date must be within the "
                        "examination start and end dates."
                    )
                )

            # -------------------------
            # Validate time
            # -------------------------

            if start_time >= end_time:
                return CustomResponse.errorResponse(
                    description="Start time must be before end time."
                )

            # -------------------------
            # Validate marks
            # -------------------------

            try:
                maximum_marks = float(maximum_marks)
                passing_marks = float(passing_marks)

            except (TypeError, ValueError):
                return CustomResponse.errorResponse(
                    description="Invalid marks value."
                )

            if maximum_marks <= 0:
                return CustomResponse.errorResponse(
                    description="Maximum marks must be greater than 0."
                )

            if passing_marks < 0:
                return CustomResponse.errorResponse(
                    description="Passing marks cannot be negative."
                )

            if passing_marks > maximum_marks:
                return CustomResponse.errorResponse(
                    description="Passing marks cannot exceed maximum marks."
                )

            # -------------------------
            # Check overlapping schedule
            # -------------------------

            overlapping_schedule = (
                ExaminationSchedule.objects
                .filter(
                    examination=examination,
                    grade=schedule.grade,
                    exam_date=exam_date,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                )
                .exclude(
                    id=schedule.id
                )
                .exists()
            )

            if overlapping_schedule:
                return CustomResponse.errorResponse(
                    description=(
                        "Another subject is already scheduled "
                        "during this time for this grade."
                    )
                )

            # -------------------------
            # Update
            # -------------------------

            schedule.exam_date = exam_date
            schedule.start_time = start_time
            schedule.end_time = end_time
            schedule.room_number = room_number
            schedule.maximum_marks = maximum_marks
            schedule.passing_marks = passing_marks
            schedule.instructions = instructions

            schedule.save()

            application_logger.info(
                "examination_schedule_updated",
                schedule_id=str(schedule.id),
                examination_id=str(examination.id),
                grade_id=str(schedule.grade_id),
                subject_id=str(schedule.subject_id),
                school_id=str(school.id),
            )

            data = {
                "id": schedule.id,


            }

            return CustomResponse.successResponse(

                data=data,
                description="Examination schedule updated successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "examination_schedule_update_failed",
                error=str(e),
                schedule_id=str(schedule_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update examination schedule."
            )


class ExaminationStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated,HasPermission,]


    def patch(self, request, examination_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        status = request.data.get("status")

        if not status:
            return CustomResponse.errorResponse(
                description="Status is required."
            )

        try:
            examination = Examination.objects.filter(
                id=examination_id,
                school=school,
            ).first()

            if not examination:
                return CustomResponse.errorResponse(
                    description="Examination not found."
                )

            if status not in dict(Examination.Status.choices):
                return CustomResponse.errorResponse(
                    description="Invalid examination status."
                )

            # --------------------------------
            # DRAFT → SCHEDULED
            # --------------------------------

            if status == Examination.Status.SCHEDULED:

                if examination.status != Examination.Status.DRAFT:
                    return CustomResponse.errorResponse(
                        description=(
                            "Only draft examinations can be "
                            "marked as scheduled."
                        )
                    )

                # -------------------------
                # Check grades
                # -------------------------

                has_grades = ExaminationGrade.objects.filter(
                    examination=examination
                ).exists()

                if not has_grades:
                    return CustomResponse.errorResponse(
                        description=(
                            "At least one grade must be assigned "
                            "before scheduling the examination."
                        )
                    )

                # -------------------------
                # Check schedules
                # -------------------------

                has_schedules = ExaminationSchedule.objects.filter(
                    examination=examination
                ).exists()

                if not has_schedules:
                    return CustomResponse.errorResponse(
                        description=(
                            "At least one subject must be scheduled "
                            "before scheduling the examination."
                        )
                    )

            # --------------------------------
            # COMPLETED
            # --------------------------------

            if status == Examination.Status.COMPLETED:

                if examination.status != Examination.Status.SCHEDULED:
                    return CustomResponse.errorResponse(
                        description=(
                            "Only scheduled examinations can "
                            "be marked as completed."
                        )
                    )

            # --------------------------------
            # CANCELLED
            # --------------------------------

            if status == Examination.Status.CANCELLED:

                if examination.status == Examination.Status.COMPLETED:
                    return CustomResponse.errorResponse(
                        description=(
                            "A completed examination cannot "
                            "be cancelled."
                        )
                    )

            examination.status = status
            examination.save(update_fields=["status"])

            application_logger.info(
                "examination_status_updated",
                examination_id=str(examination.id),
                old_status=examination.status,
                new_status=status,
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                total=1,
                data={
                    "id": examination.id,
                    "name": examination.name,
                    "status": examination.status,
                },
                description="Examination status updated successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "examination_status_update_failed",
                error=str(e),
                examination_id=str(examination_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update examination status."
            )
class ExaminationMarksTemplateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "examination_result.create"

    def get(self, request, schedule_id):

        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            # --------------------------------
            # Get examination schedule
            # --------------------------------

            schedule = (
                ExaminationSchedule.objects
                .select_related(
                    "examination",
                    "grade",
                    "subject",
                )
                .filter(
                    id=schedule_id,
                    examination__school=school,
                )
                .first()
            )

            if not schedule:
                return CustomResponse.errorResponse(
                    description="Examination schedule not found."
                )

            examination = schedule.examination

            if examination.status != Examination.Status.SCHEDULED:
                return CustomResponse.errorResponse(
                    description=(
                        "Marks template can only be generated "
                        "for a scheduled examination."
                    )
                )

            # --------------------------------
            # Get students
            # --------------------------------

            students = (
                Student.objects
                .filter(
                    school=school,
                    grade=schedule.grade,
                )
                .order_by("admission_number")
            )

            # --------------------------------
            # Create workbook
            # --------------------------------

            workbook = Workbook()

            worksheet = workbook.active
            worksheet.title = "Marks"

            # --------------------------------
            # Headers
            # --------------------------------

            headers = [
                "Admission No",
                "Student Name",
                "Marks Obtained",
            ]

            worksheet.append(headers)

            # Header styling
            header_fill = PatternFill(
                fill_type="solid",
                fgColor="1F4E78",
            )

            header_font = Font(
                bold=True,
                color="FFFFFF",
            )

            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(
                    horizontal="center"
                )

            # --------------------------------
            # Student rows
            # --------------------------------

            for student in students:

                worksheet.append([
                    student.admission_number,
                    student.name,
                    None,
                ])

            # --------------------------------
            # Column widths
            # --------------------------------

            column_widths = {
                "A": 20,
                "B": 30,
                "C": 20,
            }

            for column, width in column_widths.items():
                worksheet.column_dimensions[
                    column
                ].width = width

            # --------------------------------
            # Marks validation
            # --------------------------------

            if students.exists():

                from openpyxl.worksheet.datavalidation import (
                    DataValidation,
                )

                max_marks = schedule.maximum_marks

                validation = DataValidation(
                    type="decimal",
                    operator="between",
                    formula1="0",
                    formula2=str(max_marks),
                    allow_blank=True,
                )

                validation.error = (
                    f"Marks must be between 0 and {max_marks}."
                )

                validation.errorTitle = "Invalid Marks"

                validation.prompt = (
                    f"Enter marks between 0 and {max_marks}."
                )

                validation.promptTitle = "Marks"

                worksheet.add_data_validation(
                    validation
                )

                validation.add(
                    f"C2:C{students.count() + 1}"
                )

            # --------------------------------
            # Freeze header
            # --------------------------------

            worksheet.freeze_panes = "A2"

            # --------------------------------
            # Add instructions sheet
            # --------------------------------

            instructions = workbook.create_sheet(
                "Instructions"
            )

            instructions_data = [
                ["Examination", examination.name],
                ["Grade", schedule.grade.name],
                ["Subject", schedule.subject.name],
                ["Maximum Marks", schedule.maximum_marks],
                ["Exam Date", schedule.exam_date],
                [],
                ["Instructions"],
                [
                    "Do not modify Admission No."
                ],
                [
                    "Enter marks only in Marks Obtained column."
                ],
                [
                    f"Marks must be between 0 and "
                    f"{schedule.maximum_marks}."
                ],
                [
                    "Do not change the column names in the Marks sheet."
                ],
            ]

            for row in instructions_data:
                instructions.append(row)

            instructions.column_dimensions["A"].width = 35
            instructions.column_dimensions["B"].width = 40

            for cell in instructions["A"]:
                cell.font = Font(bold=True)

            # --------------------------------
            # Generate Excel file
            # --------------------------------

            output = BytesIO()

            workbook.save(output)

            output.seek(0)

            filename = (
                f"{examination.name}_"
                f"{schedule.grade.name}_"
                f"{schedule.subject.name}_marks.xlsx"
            )

            # Remove unsafe filename characters
            filename = (
                filename
                .replace("/", "_")
                .replace("\\", "_")
                .replace(" ", "_")
            )

            response = HttpResponse(
                output.getvalue(),
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            )

            response[
                "Content-Disposition"
            ] = f'attachment; filename="{filename}"'

            application_logger.info(
                "examination_marks_template_generated",
                school_id=str(school.id),
                examination_id=str(examination.id),
                schedule_id=str(schedule.id),
                grade_id=str(schedule.grade_id),
                subject_id=str(schedule.subject_id),
            )

            return response

        except Exception as e:

            application_logger.exception(
                "examination_marks_template_generation_failed",
                error=str(e),
                schedule_id=str(schedule_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to generate marks template."
            )

class GradeConfigurationCreateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "grade_configuration.create"

    def post(self, request):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            academic_year_id = request.data.get(
                "academic_year_id"
            )
            branch_id = request.data.get(
                "branch_id"
            )
            grade = request.data.get("grade")
            min_percentage = request.data.get(
                "min_percentage"
            )
            max_percentage = request.data.get(
                "max_percentage"
            )
            grade_point = request.data.get(
                "grade_point"
            )
            description = request.data.get(
                "description"
            )
            color = request.data.get("color")

            # -----------------------------------------
            # Required Fields
            # -----------------------------------------

            if not academic_year_id:
                return CustomResponse.errorResponse(
                    description="Academic year is required."
                )

            if not grade:
                return CustomResponse.errorResponse(
                    description="Grade is required."
                )

            if min_percentage is None:
                return CustomResponse.errorResponse(
                    description="Minimum percentage is required."
                )

            if max_percentage is None:
                return CustomResponse.errorResponse(
                    description="Maximum percentage is required."
                )

            if grade_point is None:
                return CustomResponse.errorResponse(
                    description="Grade point is required."
                )

            grade = str(grade).strip().upper()

            # -----------------------------------------
            # Decimal Validation
            # -----------------------------------------

            try:
                min_percentage = Decimal(
                    str(min_percentage)
                )
                max_percentage = Decimal(
                    str(max_percentage)
                )
                grade_point = Decimal(
                    str(grade_point)
                )
            except (InvalidOperation, ValueError):
                return CustomResponse.errorResponse(
                    description=(
                        "Minimum percentage, maximum percentage "
                        "and grade point must be valid numbers."
                    )
                )

            # -----------------------------------------
            # Percentage Validation
            # -----------------------------------------

            if (
                min_percentage < Decimal("0")
                or min_percentage > Decimal("100")
            ):
                return CustomResponse.errorResponse(
                    description=(
                        "Minimum percentage must be "
                        "between 0 and 100."
                    )
                )

            if (
                max_percentage < Decimal("0")
                or max_percentage > Decimal("100")
            ):
                return CustomResponse.errorResponse(
                    description=(
                        "Maximum percentage must be "
                        "between 0 and 100."
                    )
                )

            if min_percentage > max_percentage:
                return CustomResponse.errorResponse(
                    description=(
                        "Minimum percentage cannot be "
                        "greater than maximum percentage."
                    )
                )

            if grade_point < Decimal("0"):
                return CustomResponse.errorResponse(
                    description="Grade point cannot be negative."
                )

            # -----------------------------------------
            # Academic Year
            # -----------------------------------------

            academic_year = (
                AcademicYear.objects
                .filter(
                    id=academic_year_id,
                    school=school,
                )
                .first()
            )

            if not academic_year:
                return CustomResponse.errorResponse(
                    description="Academic year not found."
                )

            # -----------------------------------------
            # Branch
            # -----------------------------------------

            branch = None

            if branch_id:
                branch = (
                    Branch.objects
                    .filter(
                        id=branch_id,
                        school=school,
                    )
                    .first()
                )

                if not branch:
                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

            # -----------------------------------------
            # Duplicate Grade
            # -----------------------------------------

            if GradeConfiguration.objects.filter(
                school=school,
                academic_year=academic_year,
                grade=grade,
            ).exists():
                return CustomResponse.errorResponse(
                    description=(
                        f"Grade configuration '{grade}' "
                        "already exists for this academic year."
                    )
                )

            # -----------------------------------------
            # Overlapping Percentage Range
            # -----------------------------------------

            overlapping = (
                GradeConfiguration.objects
                .filter(
                    school=school,
                    academic_year=academic_year,
                    min_percentage__lte=max_percentage,
                    max_percentage__gte=min_percentage,
                )
                .exists()
            )

            if overlapping:
                return CustomResponse.errorResponse(
                    description=(
                        "Percentage range overlaps with "
                        "an existing grade configuration."
                    )
                )

            # -----------------------------------------
            # Create
            # -----------------------------------------

            grade_configuration = (
                GradeConfiguration.objects.create(
                    school=school,
                    branch=branch,
                    academic_year=academic_year,
                    grade=grade,
                    min_percentage=min_percentage,
                    max_percentage=max_percentage,
                    grade_point=grade_point,
                    description=description,
                    color = color,
                )
            )

            application_logger.info(
                "grade_configuration_created",
                grade_configuration_id=str(
                    grade_configuration.id
                ),
                school_id=str(school.id),
                academic_year_id=str(
                    academic_year.id
                ),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(
                        grade_configuration.id)

                },
                description=(
                    "Grade configuration created successfully."
                ),
            )

        except Exception as e:
            application_logger.exception(
                "grade_configuration_create_failed",
                error=str(e),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to create grade configuration."
                )
            )


class GradeConfigurationListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "grade_configuration.view"

    def get(self, request):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            queryset = (
                GradeConfiguration.objects
                .filter(
                    school=school,
                )
                .select_related(
                    "academic_year",
                    "branch",
                )
            )

            # -----------------------------------------
            # Filters
            # -----------------------------------------

            academic_year_id = request.query_params.get(
                "academic_year_id"
            )

            branch_id = request.query_params.get(
                "branch_id"
            )

            search = request.query_params.get(
                "search"
            )

            if academic_year_id:
                queryset = queryset.filter(
                    academic_year_id=academic_year_id
                )

            if branch_id:
                queryset = queryset.filter(
                    branch_id=branch_id
                )

            if search:
                search = search.strip()

                if search:
                    queryset = queryset.filter(
                        grade__icontains=search
                    )

            queryset = queryset.order_by(
                "min_percentage"
            )

            # -----------------------------------------
            # Pagination
            # -----------------------------------------

            try:
                page = max(
                    int(
                        request.query_params.get(
                            "page",
                            1,
                        )
                    ),
                    1,
                )

                page_size = max(
                    int(
                        request.query_params.get(
                            "page_size",
                            20,
                        )
                    ),
                    1,
                )

            except (TypeError, ValueError):
                return CustomResponse.errorResponse(
                    description=(
                        "Page and page_size must be valid integers."
                    )
                )

            page_size = min(
                page_size,
                100,
            )

            total_count = queryset.count()

            start = (
                page - 1
            ) * page_size

            end = start + page_size

            queryset = queryset[start:end]

            # -----------------------------------------
            # Response Data
            # -----------------------------------------

            data = []

            for configuration in queryset:
                data.append({
                    "id": str(
                        configuration.id
                    ),

                    "academic_year_id": str(
                        configuration.academic_year_id
                    ),

                    "academic_year_name": (
                        configuration
                        .academic_year
                        .name
                    ),

                    "branch_id": (
                        str(configuration.branch_id)
                        if configuration.branch_id
                        else None
                    ),

                    "branch_name": (
                        configuration.branch.name
                        if configuration.branch
                        else None
                    ),

                    "grade": configuration.grade,

                    "min_percentage": (
                        configuration.min_percentage
                    ),

                    "max_percentage": (
                        configuration.max_percentage
                    ),

                    "grade_point": (
                        configuration.grade_point
                    ),

                    "description": (
                        configuration.description
                    ),
                    "color":configuration.color,
                })

            application_logger.info(
                "grade_configurations_fetched",
                school_id=str(school.id),
                academic_year_id=academic_year_id,
                branch_id=branch_id,
                total_count=total_count,
            )

            return CustomResponse.successResponse(
                total=total_count,
                data=data,
                description=(
                    "Grade configurations fetched successfully."
                ),
            )

        except Exception as e:
            application_logger.exception(
                "grade_configuration_list_failed",
                error=str(e),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to fetch grade configurations."
                )
            )

class GradeConfigurationUpdateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "grade_configuration.update"

    def put(self, request, configuration_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            configuration = (
                GradeConfiguration.objects
                .filter(
                    id=configuration_id,
                    school=school,
                )
                .first()
            )

            if not configuration:
                return CustomResponse.errorResponse(
                    description=(
                        "Grade configuration not found."
                    )
                )

            # -----------------------------------------
            # Get Values
            # -----------------------------------------

            academic_year_id = request.data.get(
                "academic_year_id",
                configuration.academic_year_id,
            )

            branch_id = request.data.get(
                "branch_id",
                configuration.branch_id,
            )

            grade = request.data.get(
                "grade",
                configuration.grade,
            )

            min_percentage = request.data.get(
                "min_percentage",
                configuration.min_percentage,
            )

            max_percentage = request.data.get(
                "max_percentage",
                configuration.max_percentage,
            )

            grade_point = request.data.get(
                "grade_point",
                configuration.grade_point,
            )

            description = request.data.get(
                "description",
                configuration.description,
            )
            color = request.data.get("color", configuration.color)

            # -----------------------------------------
            # Normalize
            # -----------------------------------------

            grade = str(
                grade
            ).strip().upper()

            # -----------------------------------------
            # Decimal Validation
            # -----------------------------------------

            try:
                min_percentage = Decimal(
                    str(min_percentage)
                )

                max_percentage = Decimal(
                    str(max_percentage)
                )

                grade_point = Decimal(
                    str(grade_point)
                )

            except (InvalidOperation, ValueError):
                return CustomResponse.errorResponse(
                    description=(
                        "Minimum percentage, maximum percentage "
                        "and grade point must be valid numbers."
                    )
                )

            # -----------------------------------------
            # Percentage Validation
            # -----------------------------------------

            if (
                min_percentage < Decimal("0")
                or min_percentage > Decimal("100")
            ):
                return CustomResponse.errorResponse(
                    description=(
                        "Minimum percentage must be "
                        "between 0 and 100."
                    )
                )

            if (
                max_percentage < Decimal("0")
                or max_percentage > Decimal("100")
            ):
                return CustomResponse.errorResponse(
                    description=(
                        "Maximum percentage must be "
                        "between 0 and 100."
                    )
                )

            if min_percentage > max_percentage:
                return CustomResponse.errorResponse(
                    description=(
                        "Minimum percentage cannot be "
                        "greater than maximum percentage."
                    )
                )

            if grade_point < Decimal("0"):
                return CustomResponse.errorResponse(
                    description=(
                        "Grade point cannot be negative."
                    )
                )

            # -----------------------------------------
            # Academic Year
            # -----------------------------------------

            academic_year = (
                AcademicYear.objects
                .filter(
                    id=academic_year_id,
                    school=school,
                )
                .first()
            )

            if not academic_year:
                return CustomResponse.errorResponse(
                    description="Academic year not found."
                )

            # -----------------------------------------
            # Branch
            # -----------------------------------------

            branch = None

            if branch_id:
                branch = (
                    Branch.objects
                    .filter(
                        id=branch_id,
                        school=school,
                    )
                    .first()
                )

                if not branch:
                    return CustomResponse.errorResponse(
                        description="Branch not found."
                    )

            # -----------------------------------------
            # Duplicate Grade
            # -----------------------------------------

            duplicate_grade = (
                GradeConfiguration.objects
                .filter(
                    school=school,
                    academic_year=academic_year,
                    grade=grade,
                )
                .exclude(
                    id=configuration.id
                )
                .exists()
            )

            if duplicate_grade:
                return CustomResponse.errorResponse(
                    description=(
                        f"Grade configuration '{grade}' "
                        "already exists for this academic year."
                    )
                )

            # -----------------------------------------
            # Overlapping Range
            # -----------------------------------------

            overlapping = (
                GradeConfiguration.objects
                .filter(
                    school=school,
                    academic_year=academic_year,
                    min_percentage__lte=max_percentage,
                    max_percentage__gte=min_percentage,
                )
                .exclude(
                    id=configuration.id
                )
                .exists()
            )

            if overlapping:
                return CustomResponse.errorResponse(
                    description=(
                        "Percentage range overlaps with "
                        "an existing grade configuration."
                    )
                )

            # -----------------------------------------
            # Update
            # -----------------------------------------

            configuration.academic_year = (
                academic_year
            )

            configuration.branch = branch

            configuration.grade = grade

            configuration.min_percentage = (
                min_percentage
            )

            configuration.max_percentage = (
                max_percentage
            )

            configuration.grade_point = (
                grade_point
            )

            configuration.description = (
                description
            )
            configuration.color = (color)

            configuration.save()

            application_logger.info(
                "grade_configuration_updated",
                grade_configuration_id=str(
                    configuration.id
                ),
                school_id=str(school.id),
                academic_year_id=str(
                    academic_year.id
                ),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(
                        configuration.id
                    ),


                },
                description=(
                    "Grade configuration updated successfully."
                ),
            )

        except Exception as e:
            application_logger.exception(
                "grade_configuration_update_failed",
                error=str(e),
                grade_configuration_id=str(
                    configuration_id
                ),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to update grade configuration."
                )
            )

class ExaminationMarksUploadAPIView(APIView):
    parser_classes = [
        MultiPartParser,
        FormParser,
    ]
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "examination_result.create"

    def post(
        self,
        request,
        examination_id,
        grade_id,
        subject_id,
    ):
        school = request.school

        if not school:
            application_logger.warning(
                "examination_marks_upload_school_missing",
                examination_id=str(examination_id),
                grade_id=str(grade_id),
                subject_id=str(subject_id),
            )

            return CustomResponse.errorResponse(
                description="School is required."
            )

        file = request.FILES.get("file")

        if not file:
            application_logger.warning(
                "examination_marks_upload_file_missing",
                examination_id=str(examination_id),
                grade_id=str(grade_id),
                subject_id=str(subject_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Excel file is required."
            )

        if not file.name.lower().endswith((".xlsx", ".xls")):
            application_logger.warning(
                "examination_marks_upload_invalid_file",
                file_name=file.name,
                examination_id=str(examination_id),
                grade_id=str(grade_id),
                subject_id=str(subject_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Only Excel files are allowed."
            )

        application_logger.info(
            "examination_marks_upload_started",
            examination_id=str(examination_id),
            grade_id=str(grade_id),
            subject_id=str(subject_id),
            file_name=file.name,
            school_id=str(school.id),
        )

        workbook = None

        try:
            # -----------------------------------------
            # Get Examination Schedule
            # -----------------------------------------

            schedule = (
                ExaminationSchedule.objects
                .select_related(
                    "examination",
                    "grade",
                    "subject",
                )
                .filter(
                    examination_id=examination_id,
                    grade_id=grade_id,
                    subject_id=subject_id,
                    examination__school=school,
                )
                .first()
            )

            if not schedule:
                application_logger.warning(
                    "examination_marks_upload_schedule_not_found",
                    examination_id=str(examination_id),
                    grade_id=str(grade_id),
                    subject_id=str(subject_id),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description="Examination schedule not found."
                )

            examination = schedule.examination

            # -----------------------------------------
            # Validate Examination Status
            # -----------------------------------------

            if examination.status != Examination.Status.SCHEDULED:
                application_logger.warning(
                    "examination_marks_upload_invalid_status",
                    examination_id=str(examination.id),
                    schedule_id=str(schedule.id),
                    status=examination.status,
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description=(
                        "Marks can only be uploaded for "
                        "a scheduled examination."
                    )
                )

            # -----------------------------------------
            # Validate Percentage Configuration
            # -----------------------------------------

            total_percentage = (
                schedule.internal_percentage
                + schedule.external_percentage
                + schedule.practical_percentage
            )

            if total_percentage != Decimal("100"):
                application_logger.error(
                    "examination_marks_upload_invalid_percentages",
                    examination_id=str(examination.id),
                    schedule_id=str(schedule.id),
                    internal_percentage=(
                        schedule.internal_percentage
                    ),
                    external_percentage=(
                        schedule.external_percentage
                    ),
                    practical_percentage=(
                        schedule.practical_percentage
                    ),
                    total_percentage=total_percentage,
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description=(
                        "Internal, external, and practical "
                        "percentages must total 100."
                    )
                )

            # -----------------------------------------
            # Component Maximum Marks
            # -----------------------------------------

            internal_max = (
                schedule.maximum_marks
                * schedule.internal_percentage
                / Decimal("100")
            )

            external_max = (
                schedule.maximum_marks
                * schedule.external_percentage
                / Decimal("100")
            )

            practical_max = (
                schedule.maximum_marks
                * schedule.practical_percentage
                / Decimal("100")
            )

            # -----------------------------------------
            # Grade Configurations
            # -----------------------------------------

            grade_configurations = list(
                GradeConfiguration.objects.filter(
                    school=school,
                    academic_year=examination.academic_year,
                ).order_by(
                    "min_percentage"
                )
            )

            if not grade_configurations:
                application_logger.warning(
                    "examination_marks_upload_grade_configuration_missing",
                    examination_id=str(examination.id),
                    academic_year_id=str(
                        examination.academic_year_id
                    ),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description=(
                        "Grade configuration is not available "
                        "for this academic year."
                    )
                )

            # -----------------------------------------
            # Read Excel
            # -----------------------------------------

            workbook = load_workbook(
                file,
                read_only=True,
                data_only=True,
            )

            worksheet = workbook.active

            rows = worksheet.iter_rows(
                values_only=True
            )

            headers = next(rows, None)

            if not headers:
                return CustomResponse.errorResponse(
                    description="Excel file is empty."
                )

            headers = [
                str(header).strip().lower()
                if header is not None
                else ""
                for header in headers
            ]

            # -----------------------------------------
            # Required Headers
            # -----------------------------------------

            required_headers = {
                "admission no",
            }

            if schedule.internal_percentage > 0:
                required_headers.add(
                    "internal marks"
                )

            if schedule.external_percentage > 0:
                required_headers.add(
                    "external marks"
                )

            if schedule.practical_percentage > 0:
                required_headers.add(
                    "practical marks"
                )

            missing_headers = (
                required_headers - set(headers)
            )

            if missing_headers:
                application_logger.warning(
                    "examination_marks_upload_missing_headers",
                    examination_id=str(examination.id),
                    schedule_id=str(schedule.id),
                    missing_headers=sorted(
                        missing_headers
                    ),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    description=(
                        "Missing columns: "
                        f"{', '.join(sorted(missing_headers))}"
                    )
                )

            admission_no_index = headers.index(
                "admission no"
            )

            internal_marks_index = (
                headers.index("internal marks")
                if "internal marks" in headers
                else None
            )

            external_marks_index = (
                headers.index("external marks")
                if "external marks" in headers
                else None
            )

            practical_marks_index = (
                headers.index("practical marks")
                if "practical marks" in headers
                else None
            )

            # -----------------------------------------
            # Validate Excel Rows
            # -----------------------------------------

            validated_rows = []
            errors = []
            seen_admission_numbers = set()

            row_number = 1

            for row in rows:
                row_number += 1

                if not row:
                    continue

                # -------------------------------------
                # Admission Number
                # -------------------------------------

                admission_no = row[
                    admission_no_index
                ]

                if admission_no is None:
                    errors.append({
                        "row": row_number,
                        "error": (
                            "Admission number is required."
                        ),
                    })
                    continue

                admission_no = str(
                    admission_no
                ).strip()

                if not admission_no:
                    errors.append({
                        "row": row_number,
                        "error": (
                            "Admission number is required."
                        ),
                    })
                    continue

                if (
                    admission_no
                    in seen_admission_numbers
                ):
                    errors.append({
                        "row": row_number,
                        "admission_no": admission_no,
                        "error": (
                            "Duplicate admission "
                            "number in Excel."
                        ),
                    })
                    continue

                seen_admission_numbers.add(
                    admission_no
                )

                # -------------------------------------
                # Default Component Marks
                # -------------------------------------

                internal_marks = Decimal("0")
                external_marks = Decimal("0")
                practical_marks = Decimal("0")

                # -------------------------------------
                # Internal Marks
                # -------------------------------------

                if schedule.internal_percentage > 0:
                    value = row[
                        internal_marks_index
                    ]

                    if value is None:
                        errors.append({
                            "row": row_number,
                            "admission_no": admission_no,
                            "error": (
                                "Internal marks are required."
                            ),
                        })
                        continue

                    try:
                        internal_marks = Decimal(
                            str(value)
                        )
                    except (
                        InvalidOperation,
                        ValueError,
                    ):
                        errors.append({
                            "row": row_number,
                            "admission_no": admission_no,
                            "error": (
                                "Invalid internal marks."
                            ),
                        })
                        continue

                # -------------------------------------
                # External Marks
                # -------------------------------------

                if schedule.external_percentage > 0:
                    value = row[
                        external_marks_index
                    ]

                    if value is None:
                        errors.append({
                            "row": row_number,
                            "admission_no": admission_no,
                            "error": (
                                "External marks are required."
                            ),
                        })
                        continue

                    try:
                        external_marks = Decimal(
                            str(value)
                        )
                    except (
                        InvalidOperation,
                        ValueError,
                    ):
                        errors.append({
                            "row": row_number,
                            "admission_no": admission_no,
                            "error": (
                                "Invalid external marks."
                            ),
                        })
                        continue

                # -------------------------------------
                # Practical Marks
                # -------------------------------------

                if schedule.practical_percentage > 0:
                    value = row[
                        practical_marks_index
                    ]

                    if value is None:
                        errors.append({
                            "row": row_number,
                            "admission_no": admission_no,
                            "error": (
                                "Practical marks are required."
                            ),
                        })
                        continue

                    try:
                        practical_marks = Decimal(
                            str(value)
                        )
                    except (
                        InvalidOperation,
                        ValueError,
                    ):
                        errors.append({
                            "row": row_number,
                            "admission_no": admission_no,
                            "error": (
                                "Invalid practical marks."
                            ),
                        })
                        continue

                # -------------------------------------
                # Validate Negative Marks
                # -------------------------------------

                if (
                    internal_marks < 0
                    or external_marks < 0
                    or practical_marks < 0
                ):
                    errors.append({
                        "row": row_number,
                        "admission_no": admission_no,
                        "error": (
                            "Marks cannot be negative."
                        ),
                    })
                    continue

                # -------------------------------------
                # Validate Component Limits
                # -------------------------------------

                if internal_marks > internal_max:
                    errors.append({
                        "row": row_number,
                        "admission_no": admission_no,
                        "error": (
                            f"Internal marks cannot "
                            f"exceed {internal_max}."
                        ),
                    })
                    continue

                if external_marks > external_max:
                    errors.append({
                        "row": row_number,
                        "admission_no": admission_no,
                        "error": (
                            f"External marks cannot "
                            f"exceed {external_max}."
                        ),
                    })
                    continue

                if practical_marks > practical_max:
                    errors.append({
                        "row": row_number,
                        "admission_no": admission_no,
                        "error": (
                            f"Practical marks cannot "
                            f"exceed {practical_max}."
                        ),
                    })
                    continue

                # -------------------------------------
                # Calculate Total Marks
                # -------------------------------------

                marks_obtained = (
                    internal_marks
                    + external_marks
                    + practical_marks
                )

                if (
                    marks_obtained
                    > schedule.maximum_marks
                ):
                    errors.append({
                        "row": row_number,
                        "admission_no": admission_no,
                        "error": (
                            f"Total marks cannot "
                            f"exceed "
                            f"{schedule.maximum_marks}."
                        ),
                    })
                    continue

                # -------------------------------------
                # Calculate Percentage
                # -------------------------------------

                percentage = (
                    marks_obtained
                    / schedule.maximum_marks
                ) * Decimal("100")

                percentage = percentage.quantize(
                    Decimal("0.01")
                )

                # -------------------------------------
                # Find Grade Configuration
                # -------------------------------------

                grade_configuration = next(
                    (
                        config
                        for config
                        in grade_configurations
                        if (
                            config.min_percentage
                            <= percentage
                            <= config.max_percentage
                        )
                    ),
                    None,
                )

                if not grade_configuration:
                    errors.append({
                        "row": row_number,
                        "admission_no": admission_no,
                        "error": (
                            "No grade configuration "
                            f"found for percentage "
                            f"{percentage}."
                        ),
                    })
                    continue

                grade = (
                    grade_configuration.grade
                )

                grade_point = (
                    grade_configuration.grade_point
                )

                # -------------------------------------
                # Result Status
                # -------------------------------------

                result_status = (
                    "PASS"
                    if marks_obtained
                    >= schedule.passing_marks
                    else "FAIL"
                )

                validated_rows.append({
                    "row": row_number,
                    "admission_no": admission_no,
                    "internal_marks": internal_marks,
                    "external_marks": external_marks,
                    "practical_marks": practical_marks,
                    "marks_obtained": marks_obtained,
                    "percentage": percentage,
                    "grade": grade,
                    "grade_point": grade_point,
                    "result_status": result_status,
                })

            # -----------------------------------------
            # Validation Errors
            # -----------------------------------------

            if errors:
                application_logger.warning(
                    "examination_marks_upload_validation_failed",
                    examination_id=str(examination.id),
                    schedule_id=str(schedule.id),
                    total_errors=len(errors),
                    valid_rows=len(validated_rows),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    data={
                        "errors": errors,
                    },
                    description=(
                        "Excel contains invalid data. "
                        "No marks were uploaded."
                    ),
                )

            if not validated_rows:
                return CustomResponse.errorResponse(
                    description=(
                        "No valid student records "
                        "found in Excel."
                    )
                )

            # -----------------------------------------
            # Get Students
            # -----------------------------------------

            admission_numbers = [
                row["admission_no"]
                for row in validated_rows
            ]

            students = (
                Student.objects
                .filter(
                    school=school,
                    admission_number__in=(
                        admission_numbers
                    ),
                    grade_id=grade_id,
                )
            )

            student_map = {
                student.admission_number: student
                for student in students
            }

            student_errors = []

            for row in validated_rows:
                admission_no = row[
                    "admission_no"
                ]

                if admission_no not in student_map:
                    student_errors.append({
                        "row": row["row"],
                        "admission_no": admission_no,
                        "error": (
                            "Student not found or "
                            "student does not belong "
                            "to this grade."
                        ),
                    })

            if student_errors:
                application_logger.warning(
                    "examination_marks_upload_student_validation_failed",
                    examination_id=str(examination.id),
                    schedule_id=str(schedule.id),
                    total_errors=len(student_errors),
                    school_id=str(school.id),
                )

                return CustomResponse.errorResponse(
                    data={
                        "errors": student_errors,
                    },
                    description=(
                        "Some students could not be "
                        "matched. No marks were uploaded."
                    ),
                )

            # -----------------------------------------
            # Save Results
            # -----------------------------------------

            created_count = 0
            updated_count = 0

            with transaction.atomic():

                for row in validated_rows:

                    student = student_map[
                        row["admission_no"]
                    ]

                    result, created = (
                        ExaminationResult.objects
                        .update_or_create(
                            examination_schedule=schedule,
                            student=student,
                            defaults={
                                "examination": examination,

                                "internal_marks": (
                                    row["internal_marks"]
                                ),
                                "external_marks": (
                                    row["external_marks"]
                                ),
                                "practical_marks": (
                                    row["practical_marks"]
                                ),
                                "marks_obtained": (
                                    row["marks_obtained"]
                                ),

                                "grade": row["grade"],
                                "grade_point": (
                                    row["grade_point"]
                                ),

                                "status": (
                                    ExaminationResult
                                    .Status
                                    .DRAFT
                                ),
                            },
                        )
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

            # -----------------------------------------
            # Success Log
            # -----------------------------------------

            application_logger.info(
                "examination_marks_uploaded",
                examination_id=str(examination.id),
                schedule_id=str(schedule.id),
                grade_id=str(schedule.grade_id),
                subject_id=str(schedule.subject_id),
                created_count=created_count,
                updated_count=updated_count,
                total_processed=(
                    created_count
                    + updated_count
                ),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                total=(
                    created_count
                    + updated_count
                ),
                data={
                    "examination_id": str(
                        examination.id
                    ),
                    "schedule_id": str(
                        schedule.id
                    ),
                    "grade_id": str(
                        schedule.grade_id
                    ),
                    "subject_id": str(
                        schedule.subject_id
                    ),
                    "subject_name": (
                        schedule.subject.name
                    ),
                    # "maximum_marks": (
                    #     schedule.maximum_marks
                    # ),
                    # "internal_max_marks": (
                    #     internal_max
                    # ),
                    # "external_max_marks": (
                    #     external_max
                    # ),
                    # "practical_max_marks": (
                    #     practical_max
                    # ),
                    "created_count": created_count,
                    "updated_count": updated_count,
                    "total_processed": (
                        created_count
                        + updated_count
                    ),
                },
                description=(
                    "Marks uploaded successfully."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "examination_marks_upload_failed",
                error=str(e),
                examination_id=str(
                    examination_id
                ),
                grade_id=str(grade_id),
                subject_id=str(subject_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to upload "
                    "examination marks."
                )
            )

        finally:

            if workbook:
                workbook.close()



class ExaminationResultListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "examination_result.view"

    def get(self, request, examination_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            # -----------------------------------------
            # Get Examination
            # -----------------------------------------

            examination = (
                Examination.objects
                .filter(
                    id=examination_id,
                    school=school,
                )
                .first()
            )

            if not examination:
                return CustomResponse.errorResponse(
                    description="Examination not found."
                )

            # -----------------------------------------
            # Get Results
            # -----------------------------------------

            queryset = (
                ExaminationResult.objects
                .filter(
                    examination=examination,
                    examination_schedule__examination__school=school,
                )
                .select_related(
                    "student",
                    "examination_schedule",
                    "examination_schedule__grade",
                    "examination_schedule__subject",
                )
                .order_by(
                    "examination_schedule__exam_date",
                    "examination_schedule__grade__display_order",
                    "student__name",
                )
            )

            # -----------------------------------------
            # Filters
            # -----------------------------------------

            grade_id = request.query_params.get(
                "grade_id"
            )

            subject_id = request.query_params.get(
                "subject_id"
            )

            student_id = request.query_params.get(
                "student_id"
            )

            search = request.query_params.get(
                "search"
            )

            if grade_id:
                queryset = queryset.filter(
                    examination_schedule__grade_id=grade_id
                )

            if subject_id:
                queryset = queryset.filter(
                    examination_schedule__subject_id=subject_id
                )

            if student_id:
                queryset = queryset.filter(
                    student_id=student_id
                )

            if search:
                search = search.strip()

                if search:
                    queryset = queryset.filter(
                        Q(
                            student__name__icontains=search
                        )
                        | Q(
                            student__admission_number__icontains=search
                        )
                    )

            # -----------------------------------------
            # Pagination
            # -----------------------------------------

            try:
                page = max(
                    int(
                        request.query_params.get(
                            "page",
                            1,
                        )
                    ),
                    1,
                )

                page_size = max(
                    int(
                        request.query_params.get(
                            "page_size",
                            20,
                        )
                    ),
                    1,
                )

            except (TypeError, ValueError):
                return CustomResponse.errorResponse(
                    description=(
                        "Page and page_size must be valid integers."
                    )
                )

            page_size = min(
                page_size,
                100,
            )

            total_count = queryset.count()

            start = (
                page - 1
            ) * page_size

            end = start + page_size

            queryset = queryset[start:end]

            # -----------------------------------------
            # Result Data
            # -----------------------------------------

            data = []

            for result in queryset:

                schedule = result.examination_schedule

                maximum_marks = schedule.maximum_marks

                # -------------------------------------
                # Calculate Percentage
                # -------------------------------------

                if (
                    maximum_marks
                    and maximum_marks > 0
                ):
                    percentage = (
                        result.marks_obtained
                        / maximum_marks
                    ) * Decimal("100")

                    percentage = percentage.quantize(
                        Decimal("0.01")
                    )
                else:
                    percentage = Decimal("0.00")

                # -------------------------------------
                # Result Data
                # -------------------------------------

                data.append({
                    "id": str(
                        result.id
                    ),

                    "examination_id": str(
                        result.examination_id
                    ),

                    "schedule_id": str(
                        result.examination_schedule_id
                    ),

                    "student_id": str(
                        result.student_id
                    ),

                    "student_name": (
                        result.student.name
                    ),

                    "admission_number": (
                        result.student.admission_number
                    ),

                    # -----------------------------
                    # Grade
                    # -----------------------------

                    "grade_id": str(
                        schedule.grade_id
                    ),

                    "grade_name": (
                        schedule.grade.name
                    ),

                    # -----------------------------
                    # Subject
                    # -----------------------------

                    "subject_id": str(
                        schedule.subject_id
                    ),

                    "subject_name": (
                        schedule.subject.name
                    ),

                    "exam_date": (
                        schedule.exam_date
                    ),

                    # -----------------------------
                    # Marks
                    # -----------------------------

                    "maximum_marks": (
                        maximum_marks
                    ),

                    "passing_marks": (
                        schedule.passing_marks
                    ),

                    "internal_marks": (
                        result.internal_marks
                    ),

                    "external_marks": (
                        result.external_marks
                    ),

                    "practical_marks": (
                        result.practical_marks
                    ),

                    "marks_obtained": (
                        result.marks_obtained
                    ),

                    # -----------------------------
                    # Result
                    # -----------------------------

                    "percentage": percentage,

                    "grade": result.grade,

                    "grade_point": (
                        result.grade_point
                    ),

                    "result_status": (
                        "PASS"
                        if result.marks_obtained >= schedule.passing_marks
                        else "FAIL"
                    ),
                    "color":result.color,

                    "remarks": (
                        result.remarks
                    ),

                    # DRAFT / PUBLISHED
                    "status": (
                        result.status
                    ),
                })

            # -----------------------------------------
            # Log
            # -----------------------------------------

            application_logger.info(
                "examination_results_fetched",
                examination_id=str(
                    examination.id
                ),
                school_id=str(
                    school.id
                ),
                grade_id=grade_id,
                subject_id=subject_id,
                student_id=student_id,
                total_count=total_count,
            )

            # -----------------------------------------
            # Response
            # -----------------------------------------

            return CustomResponse.successResponse(
                total=total_count,
                data=data,
                description=(
                    "Examination results fetched successfully."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "examination_results_fetch_failed",
                examination_id=str(
                    examination_id
                ),
                school_id=str(
                    school.id
                ),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Internal server error."
            )
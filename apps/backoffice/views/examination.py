from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.examination.models import ExaminationType
from apps.school.models.school import Branch
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


class ExaminationTypeCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
                    "name": examination_type.name,
                    "description": examination_type.description,
                    "branch_id": examination_type.branch_id,
                    "weightage": examination_type.weightage,
                    "max_marks": examination_type.max_marks,
                    "frequency": examination_type.frequency,
                    "duration": examination_type.duration,
                    "status": examination_type.status,
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
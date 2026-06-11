from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.models import Roles, UserMaster, UserRoles
from apps.school.models import School
from apps.school.models.school import AcademicYear, Grade, Section, Student
from shared.enums.roles import RolesEnum
from shared.helpers.rbac import check_permission
from shared.helpers.student import get_or_create_parent
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from openpyxl import load_workbook

from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db import transaction
from apps.core.models import (
    Roles,
    UserRoles,
)
from shared.permissions.rbac import HasPermission
from shared.enums.roles import RolesEnum

class CreateAcademicYearAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "academic_year.create"

    def post(self, request):

        school = School.objects.filter(
            id=request.data.get("school_id"),
        ).first()

        if not school:
            return CustomResponse.errorResponse(
                description="School not found",
            )

        check_permission(
            request,
            "academic_year.create",
            school.id,
        )

        if request.data.get("status") == "ACTIVE":
            AcademicYear.objects.filter(
                school=school,
                status="ACTIVE",
            ).update(
                status="INACTIVE",
            )

        academic_year = AcademicYear.objects.create(
            school=school,
            name=request.data.get("name"),
            start_date=request.data.get("start_date"),
            end_date=request.data.get("end_date"),
            status=request.data.get(
                "status",
                "ACTIVE",
            ),
        )

        return CustomResponse.successResponse(
            description="Academic year created successfully",
            data={
                "id": academic_year.id,
            },
        )


class AcademicYearListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "academic_year.view"

    def get(self, request):

        school_id = request.GET.get("school_id")

        check_permission(
            request,
            "academic_year.view",
            school_id,
        )

        queryset = AcademicYear.objects.filter(
            school_id=school_id,
        )

        data = []

        for obj in queryset:

            data.append({
                "id": obj.id,
                "name": obj.name,
                "start_date": obj.start_date,
                "end_date": obj.end_date,
                "status": obj.status,
            })

        return CustomResponse.successResponse(
            data=data,
        )

class UpdateAcademicYearAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "academic_year.update"

    def put(
        self,
        request,
        academic_year_id,
    ):

        academic_year = AcademicYear.objects.filter(
            id=academic_year_id,
        ).first()

        if not academic_year:
            return CustomResponse.errorResponse(
                description="Academic year not found",
            )

        check_permission(
            request,
            "academic_year.update",
            academic_year.school_id,
        )

        if request.data.get("status") == "ACTIVE":
            AcademicYear.objects.filter(
                school=academic_year.school,
            ).exclude(
                id=academic_year.id,
            ).update(
                status="INACTIVE",
            )

        academic_year.name = request.data.get(
            "name",
            academic_year.name,
        )

        academic_year.start_date = request.data.get(
            "start_date",
            academic_year.start_date,
        )

        academic_year.end_date = request.data.get(
            "end_date",
            academic_year.end_date,
        )

        academic_year.status = request.data.get(
            "status",
            academic_year.status,
        )

        academic_year.save()

        return CustomResponse.successResponse(
            description="Academic year updated successfully",
        )


class CreateGradeAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "grade.create",

    def post(self, request):


        school = School.objects.filter(

            id=request.data.get("school_id"),

        ).first()

        academic_year = AcademicYear.objects.filter(
            id=request.data.get("academic_year_id"),
        ).first()

        if academic_year is None:
            return CustomResponse.errorResponse(
                description="Academic Year not found.",
            )

        if Grade.objects.filter(
            academic_year=academic_year,
            name=request.data.get("name"),
        ).exists():
            return CustomResponse.errorResponse(
                description="Grade already exists.",
            )

        grade = Grade.objects.create(
            school=school,
            academic_year=academic_year,
            name=request.data.get("name"),
            display_order = request.data.get("display_order"),
            status=request.data.get(
                "status",
                Grade.Status.ACTIVE,
            ),
        )

        return CustomResponse.successResponse(
            description="Grade created successfully.",
            data={
                "id": str(grade.id),
            },
        )

class GradeListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]

    required_permission = "grade.view",

    def get(self, request):



        grades = Grade.objects.select_related(
            "school",
            "academic_year",
        ).all()

        data = []

        for grade in grades:

            data.append(
                {
                    "id": grade.id,
                    "school": grade.school.name,
                    "academic_year": grade.academic_year.name,
                    "name": grade.name,
                    "display_order": grade.display_order,
                    "status": grade.status,
                }
            )

        return CustomResponse.successResponse(
            data=data,
        )
class UpdateGradeAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "grade.update",

    def put(
        self,
        request,
        grade_id,
    ):



        grade = Grade.objects.filter(
            id=grade_id,
        ).first()

        if grade is None:
            return CustomResponse.errorResponse(
                description="Grade not found.",
            )

        grade.name = request.data.get(
            "name",
            grade.name,
        )
        grade.display_order = request.data.get(
            "display_order",
            grade.display_order,
        )



        grade.status = request.data.get(
            "status",
            grade.status,
        )

        grade.save()

        return CustomResponse.successResponse(
            description="Grade updated successfully.",
        )

class CreateSectionAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "section.create",

    def post(self, request):



        grade = Grade.objects.filter(
            id=request.data.get("grade_id"),
        ).first()

        if grade is None:
            return CustomResponse.errorResponse(
                description="Grade not found.",
            )

        if Section.objects.filter(
            grade=grade,
            name=request.data.get("name"),
        ).exists():
            return CustomResponse.errorResponse(
                description="Section already exists.",
            )

        section = Section.objects.create(
            grade=grade,
            name=request.data.get("name"),
            capacity=request.data.get("capacity"),
            status=request.data.get(
                "status",
                Section.Status.ACTIVE,
            ),
        )

        return CustomResponse.successResponse(
            description="Section created successfully.",
            data={
                "id": str(section.id),
            },
        )

class SectionListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "section.list",

    def get(self, request):



        sections = Section.objects.select_related(
            "grade",
        ).all()

        data = []

        for section in sections:

            data.append(
                {
                    "id": section.id,
                    "name": section.name,
                    "grade": section.grade.name,
                    "capacity": section.capacity,
                    "status": section.status,
                }
            )

        return CustomResponse.successResponse(
            data=data,
        )

class UpdateSectionAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission]
    required_permission = "section.update",

    def put(
        self,
        request,
        section_id,
    ):



        section = Section.objects.filter(
            id=section_id,
        ).first()

        if section is None:
            return CustomResponse.errorResponse(
                description="Section not found.",
            )

        section.name = request.data.get(
            "name",
            section.name,
        )

        section.capacity = request.data.get(
            "capacity",
            section.capacity,
        )

        section.status = request.data.get(
            "status",
            section.status,
        )

        section.save()

        return CustomResponse.successResponse(
            description="Section updated successfully.",
        )

class CreateStudentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student.create"

    def post(self, request):
        print("=" * 80)

        print("Create Student API Called")

        print(request.data)

        school = School.objects.filter(

            id=request.data.get("school_id"),

        ).first()

        print("School :", school)

        academic_year = AcademicYear.objects.filter(

            id=request.data.get("academic_year_id"),

        ).first()

        print("Academic Year :", academic_year)

        grade = Grade.objects.filter(

            id=request.data.get("grade_id"),

        ).first()

        print("Grade :", grade)

        section = Section.objects.filter(

            id=request.data.get("section_id"),

        ).first()

        print("Section :", section)

        print("Creating Father...")

        father = get_or_create_parent(

            request.data.get("father_mobile"),

        )

        print("Creating Mother...")

        mother = get_or_create_parent(

            request.data.get("mother_mobile"),

        )

        print("Creating Guardian...")

        guardian = get_or_create_parent(

            request.data.get("guardian_mobile"),

        )

        print("Creating Student...")

        student = Student.objects.create(

            school=school,

            academic_year=academic_year,

            grade=grade,

            section=section,

            father=father,

            mother=mother,

            guardian=guardian,

            admission_number=request.data.get(
                "admission_number",
            ),

            roll_number=request.data.get(
                "roll_number",
            ),

            first_name=request.data.get(
                "first_name",
            ),

            last_name=request.data.get(
                "last_name",
            ),

            gender=request.data.get(
                "gender",
            ),

            date_of_birth=request.data.get(
                "date_of_birth",
            ),

            admission_date=request.data.get(
                "admission_date",
            ),

            email=request.data.get(
                "email",
            ),

            address=request.data.get(
                "address",
            ),

            blood_group=request.data.get(
                "blood_group",
            ),

            status=request.data.get(
                "status",
                Student.Status.ACTIVE,
            ),
        )
        print("Student Created :", student.id)

        print("=" * 80)

        return CustomResponse.successResponse(

            description="Student created successfully.",

            data={
                "id": str(student.id),
            },
        )



class BulkUploadStudentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student.bulk_upload"

    parser_classes = [
        MultiPartParser,
    ]

    def post(self, request):

        file = request.FILES.get("file")

        if file is None:

            return CustomResponse.errorResponse(
                description="Excel file is required.",
            )

        workbook = load_workbook(file)

        sheet = workbook.active

        headers = [
            cell.value
            for cell in sheet[1]
        ]

        required_headers = [

            "School Code",

            "Academic Year",

            "Grade",

            "Section",

            "Admission Number",

            "Roll Number",

            "First Name",

        ]

        for header in required_headers:

            if header not in headers:

                return CustomResponse.errorResponse(
                    description=f"{header} column is missing.",
                )

        success_count = 0

        failed_count = 0

        errors = []

        for row_number, row in enumerate(

            sheet.iter_rows(
                min_row=2,
                values_only=True,
            ),

            start=2,

        ):

            try:

                data = dict(
                    zip(
                        headers,
                        row,
                    )
                )

                school = School.objects.filter(
                    code=data.get(
                        "School Code",
                    ),
                ).first()

                if school is None:
                    raise Exception(
                        "School not found.",
                    )

                academic_year = AcademicYear.objects.filter(
                    school=school,
                    name=data.get(
                        "Academic Year",
                    ),
                ).first()

                if academic_year is None:
                    raise Exception(
                        "Academic year not found.",
                    )

                grade = Grade.objects.filter(
                    school=school,
                    name=data.get(
                        "Grade",
                    ),
                ).first()

                if grade is None:
                    raise Exception(
                        "Grade not found.",
                    )

                section = Section.objects.filter(
                    grade=grade,
                    name=data.get(
                        "Section",
                    ),
                ).first()

                if section is None:
                    raise Exception(
                        "Section not found.",
                    )

                if Student.objects.filter(
                    school=school,
                    admission_number=data.get(
                        "Admission Number",
                    ),
                ).exists():

                    raise Exception(
                        "Admission number already exists.",
                    )

                if Student.objects.filter(
                    section=section,
                    roll_number=data.get(
                        "Roll Number",
                    ),
                ).exists():

                    raise Exception(
                        "Roll number already exists.",
                    )

                with transaction.atomic():

                    father = get_or_create_parent(
                        data.get(
                            "Father Mobile",
                        ),
                    )

                    mother = get_or_create_parent(
                        data.get(
                            "Mother Mobile",
                        ),
                    )

                    guardian = get_or_create_parent(
                        data.get(
                            "Guardian Mobile",
                        ),
                    )

                    Student.objects.create(

                        school=school,

                        academic_year=academic_year,

                        grade=grade,

                        section=section,

                        father=father,

                        mother=mother,

                        guardian=guardian,

                        admission_number=data.get(
                            "Admission Number",
                        ),

                        roll_number=data.get(
                            "Roll Number",
                        ),

                        first_name=data.get(
                            "First Name",
                        ),

                        last_name=data.get(
                            "Last Name",
                        ),

                        gender=data.get(
                            "Gender",
                        ),

                        date_of_birth=data.get(
                            "Date Of Birth",
                        ),

                        admission_date=data.get(
                            "Admission Date",
                        ),

                        email=data.get(
                            "Email",
                        ),

                        address=data.get(
                            "Address",
                        ),

                        blood_group=data.get(
                            "Blood Group",
                        ),

                        status=Student.Status.ACTIVE,

                    )

                success_count += 1

            except Exception as e:

                failed_count += 1

                errors.append(
                    {
                        "row": row_number,
                        "message": str(e),
                    }
                )

        return CustomResponse.successResponse(

            description="Student bulk upload completed.",

            data={

                "total_records": success_count + failed_count,

                "success_count": success_count,

                "failed_count": failed_count,

                "errors": errors,

            },
        )
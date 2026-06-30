from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q
from apps.core.models import Roles, UserMaster, UserRoles
from apps.fee.models import FeeTemplate, StudentFeeAssignment, FeeConcession
from apps.school.models import School
from apps.school.models.school import AcademicYear, Grade, Section, Student, StudentDocument, Staff
from shared.enums.roles import RolesEnum
from shared.helpers.rbac import check_permission
from shared.helpers.student import get_or_create_parent
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from openpyxl import load_workbook
from django.conf import settings

from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db import IntegrityError
from apps.core.models import (
    Roles,
    UserRoles,
)
from shared.permissions.rbac import HasPermission
from shared.enums.roles import RolesEnum
from django.db import transaction

from shared.utils.fee import generate_student_fees
from io import BytesIO

from openpyxl import Workbook

from django.http import HttpResponse, FileResponse

from rest_framework.views import APIView

from rest_framework.permissions import IsAuthenticated


class CreateAcademicYearAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "academic_year.create"

    def post(self, request):

        school = request.school

        if school is None:
            return CustomResponse.errorResponse(

                description="School not found.",

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
        print("AcademicYearListAPIView Called")
        queryset = AcademicYear.objects.filter(

            school=request.school,

        ).order_by(

            "-created_at",

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

            school=request.school,

        ).first()

        if academic_year is None:
            return CustomResponse.errorResponse(

                description="Academic year not found.",

            )



        # if request.data.get("status") == "ACTIVE":
        #     AcademicYear.objects.filter(
        #         school=academic_year.school,
        #     ).exclude(
        #         id=academic_year.id,
        #     ).update(
        #         status="INACTIVE",
        #     )
        if request.data.get("status") == "ACTIVE":
            AcademicYear.objects.filter(
                school=academic_year.school,
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

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "grade.create"

    def post(self, request):

        print("=" * 80)
        print("CreateGradeAPIView Called")
        print("User :", request.user)
        print("Request School :", request.school)
        print("Request School ID :", request.school_id)
        print("Request Data :", request.data)
        print("=" * 80)

        school = request.school

        print("Fetching Academic Year...")

        academic_year = AcademicYear.objects.filter(
            id=request.data.get("academic_year_id"),
            school=school,
        ).first()

        print("Academic Year :", academic_year)

        if academic_year is None:

            print("Academic Year Not Found")

            return CustomResponse.errorResponse(
                description="Academic Year not found.",
            )

        print("Checking Existing Grade...")

        grade_exists = Grade.objects.filter(
            school=school,
            academic_year=academic_year,
            name=request.data.get("name"),
        ).exists()

        print("Grade Exists :", grade_exists)

        if grade_exists:

            print("Grade Already Exists")

            return CustomResponse.errorResponse(
                description="Grade already exists.",
            )

        print("Creating Grade...")

        grade = Grade.objects.create(
            school=school,
            academic_year=academic_year,
            name=request.data.get("name"),
            display_order=request.data.get("display_order"),
            status=request.data.get(
                "status",
                Grade.Status.ACTIVE,
            ),
        )

        print("Grade Created Successfully")
        print("Grade ID :", grade.id)
        print("Grade Name :", grade.name)
        print("School :", grade.school)
        print("Academic Year :", grade.academic_year)
        print("=" * 80)

        return CustomResponse.successResponse(
            description="Grade created successfully.",
            data={
                "id": str(grade.id),
            },
        )

class GradeListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "grade.view"

    def get(self, request):
        school = request.school

        print("=" * 80)
        print("Grade List API Called")
        print("User :", request.user)
        print("Roles :", getattr(request, "roles", []))
        print("Permissions :", getattr(request, "permissions", []))

        grades = Grade.objects.select_related(
            "school",
            "academic_year",
        ).filter(school=school)

        print("Total Grades Found :", grades.count())

        data = []

        for grade in grades:

            print("-" * 40)
            print("Grade ID :", grade.id)
            print("School :", grade.school.name)
            print("Academic Year :", grade.academic_year.name)
            print("Grade Name :", grade.name)
            print("Display Order :", grade.display_order)
            print("Status :", grade.status)

            data.append(
                {
                    "id": str(grade.id),
                    "school": grade.school.name,
                    "academic_year": grade.academic_year.name,
                    "name": grade.name,
                    "display_order": grade.display_order,
                    "status": grade.status,
                }
            )

        print("Returning Total Records :", len(data))
        print("=" * 80)

        return CustomResponse.successResponse(
            data=data,
        )
class UpdateGradeAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "grade.update"

    def put(
        self,
        request,
        grade_id,
    ):

        print("=" * 80)
        print("Update Grade API Called")
        print("User :", request.user)
        print("School :", request.school)
        print("School ID :", getattr(request, "school_id", None))
        print("Grade ID :", grade_id)
        print("Request Data :", request.data)
        print("=" * 80)

        school = request.school

        print("Fetching Grade...")

        grade = Grade.objects.filter(
            id=grade_id,
            school=school,
        ).first()

        print("Grade Object :", grade)

        if grade is None:

            print("Grade Not Found")
            print("=" * 80)

            return CustomResponse.errorResponse(
                description="Grade not found.",
            )

        print("Old Grade Name :", grade.name)
        print("Old Display Order :", grade.display_order)
        print("Old Status :", grade.status)

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

        print("Updated Grade Name :", grade.name)
        print("Updated Display Order :", grade.display_order)
        print("Updated Status :", grade.status)

        grade.save()

        print("Grade Updated Successfully")
        print("=" * 80)

        return CustomResponse.successResponse(
            description="Grade updated successfully.",
        )

class CreateSectionAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "section.create"

    def post(self, request):

        school = request.school

        grade = Grade.objects.filter(
            id=request.data.get("grade_id"),
            school=school,
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
            capacity=request.data.get(
                "capacity",
                40,
            ),
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

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "section.view"

    def get(self, request):

        print("=" * 80)
        print("Section List API Called")
        print("User :", request.user)
        print("School :", request.school)
        print("School ID :", getattr(request, "school_id", None))
        print("Roles :", getattr(request, "roles", []))
        print("Permissions :", getattr(request, "permissions", []))
        print("=" * 80)

        school = request.school

        sections = Section.objects.select_related(
            "grade",
            "grade__school",
        ).filter(
            grade__school=school,
        )

        print("Total Sections Found :", sections.count())

        data = []

        for section in sections:

            print("-" * 60)
            print("Section ID :", section.id)
            print("Section Name :", section.name)
            print("Grade :", section.grade.name)
            print("School :", section.grade.school.name)
            print("Capacity :", section.capacity)
            print("Status :", section.status)

            data.append(
                {
                    "id": str(section.id),
                    "school": section.grade.school.name,
                    "grade": section.grade.name,
                    "name": section.name,
                    "capacity": section.capacity,
                    "status": section.status,
                }
            )

        print("=" * 80)
        print("Returning Total Records :", len(data))
        print("=" * 80)

        return CustomResponse.successResponse(
            data=data,
        )
class UpdateSectionAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "section.update"

    def put(
        self,
        request,
        section_id,
    ):

        school = request.school

        section = Section.objects.filter(
            id=section_id,
            grade__school=school,
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

        school = request.school

        if school is None:

            return CustomResponse.errorResponse(
                description="School not found.",
            )

        required_fields = [

            "academic_year_id",

            "grade_id",

            "section_id",

            "admission_number",

            "roll_number",

            "name",

            "gender",

            "date_of_birth",

            "admission_date",

        ]

        for field in required_fields:

            if request.data.get(field) in [None, ""]:

                return CustomResponse.errorResponse(
                    description=f"{field} is required.",
                )

        academic_year = AcademicYear.objects.filter(
            id=request.data.get(
                "academic_year_id",
            ),
            school=school,
        ).first()

        if academic_year is None:

            return CustomResponse.errorResponse(
                description="Academic year not found.",
            )

        grade = Grade.objects.filter(
            id=request.data.get(
                "grade_id",
            ),
            school=school,
        ).first()

        if grade is None:

            return CustomResponse.errorResponse(
                description="Grade not found.",
            )

        section = Section.objects.filter(
            id=request.data.get(
                "section_id",
            ),
            grade=grade,
        ).first()

        if section is None:

            return CustomResponse.errorResponse(
                description="Section not found.",
            )

        if request.data.get(
            "gender",
        ) not in Student.Gender.values:

            return CustomResponse.errorResponse(
                description="Invalid gender.",
            )

        board = request.data.get(
            "board",
            Student.Board.STATE,
        )

        if board not in Student.Board.values:

            return CustomResponse.errorResponse(
                description="Invalid board.",
            )

        hostel_type = request.data.get(
            "hostel_type",
            Student.HostelType.DAY_SCHOLAR,
        )

        if hostel_type not in Student.HostelType.values:

            return CustomResponse.errorResponse(
                description="Invalid hostel type.",
            )

        enrollment_type = request.data.get(
            "enrollment_type",
            Student.EnrollmentType.NEW,
        )

        if enrollment_type not in Student.EnrollmentType.values:

            return CustomResponse.errorResponse(
                description="Invalid enrollment type.",
            )

        if Student.objects.filter(
            school=school,
            admission_number=request.data.get(
                "admission_number",
            ),
        ).exists():

            return CustomResponse.errorResponse(
                description="Admission number already exists.",
            )

        if Student.objects.filter(
            section=section,
            roll_number=request.data.get(
                "roll_number",
            ),
        ).exists():

            return CustomResponse.errorResponse(
                description="Roll number already exists in this section.",
            )
        valid_blood_groups = [
               "A+",
                "A-",
                "B+",
                "B-",
                "AB+",
                "AB-",
                "O+",
                "O-",
        ]
        blood_group = request.data.get("blood_group",)
        if blood_group and blood_group not in valid_blood_groups:
            return CustomResponse.errorResponse(
        description="Invalid blood group.",)


        try:

            with transaction.atomic():

                fee_concession_id = request.data.get(
                    "fee_concession_id",
                )

                concession = None

                if fee_concession_id:

                    concession = FeeConcession.objects.filter(
                        id=fee_concession_id,
                        school=school,
                    ).first()

                    if concession is None:

                        return CustomResponse.errorResponse(
                            description="Fee concession not found.",
                        )

                student = Student.objects.create(

                    school=school,

                    board=board,

                    academic_year=academic_year,

                    grade=grade,

                    section=section,

                    admission_number=request.data.get(
                        "admission_number",
                    ).strip(),

                    roll_number=request.data.get(
                        "roll_number",
                    ),

                    name=request.data.get(
                        "name",
                    ).strip(),

                    gender=request.data.get(
                        "gender",
                    ),

                    date_of_birth=request.data.get(
                        "date_of_birth",
                    ),

                    admission_date=request.data.get(
                        "admission_date",
                    ),

                    enrollment_type=enrollment_type,

                    status=request.data.get(
                        "status",
                        Student.Status.ACTIVE,
                    ),

                    place_of_birth=request.data.get(
                        "place_of_birth",
                    ),

                    blood_group=blood_group,

                    photo_url=request.data.get(
                        "photo_url",
                    ),

                    nationality=request.data.get(
                        "nationality",
                        "Indian",
                    ),

                    mother_tongue=request.data.get(
                        "mother_tongue",
                    ),

                    aadhaar_number=request.data.get(
                        "aadhaar_number",
                    ),

                    religion=request.data.get(
                        "religion",
                    ),

                    caste=request.data.get(
                        "caste",
                    ),

                    sub_caste=request.data.get(
                        "sub_caste",
                    ),

                    student_category=request.data.get(
                        "student_category",
                    ),

                    identification_marks=request.data.get(
                        "identification_marks",
                    ),

                    email=request.data.get(
                        "email",
                    ),

                    address=request.data.get(
                        "address",
                    ),

                    emergency_contact_name=request.data.get(
                        "emergency_contact_name",
                    ),

                    emergency_contact_mobile=request.data.get(
                        "emergency_contact_mobile",
                    ),

                    father_name=request.data.get(
                        "father_name",
                    ),

                    father_mobile=request.data.get(
                        "father_mobile",
                    ),

                    father_occupation=request.data.get(
                        "father_occupation",
                    ),

                    mother_name=request.data.get(
                        "mother_name",
                    ),

                    mother_mobile=request.data.get(
                        "mother_mobile",
                    ),

                    mother_occupation=request.data.get(
                        "mother_occupation",
                    ),

                    guardian_name=request.data.get(
                        "guardian_name",
                    ),

                    guardian_mobile=request.data.get(
                        "guardian_mobile",
                    ),

                    guardian_occupation=request.data.get(
                        "guardian_occupation",
                    ),

                    previous_school_name=request.data.get(
                        "previous_school_name",
                    ),

                    previous_school_tc_number=request.data.get(
                        "previous_school_tc_number",
                    ),

                    previous_exam_percentage=request.data.get(
                        "previous_exam_percentage",
                    ),

                    transport_required=request.data.get(
                        "transport_required",
                        False,
                    ),

                    pickup_point=request.data.get(
                        "pickup_point",
                    ),

                    hostel_type=hostel_type,

                )

                fee_template = FeeTemplate.objects.filter(
                    school=school,
                    academic_year=academic_year,
                    grade=grade,
                ).first()

                if fee_template is None:

                    raise Exception(
                        f"Fee template not configured for grade '{grade.name}'."
                    )

                StudentFeeAssignment.objects.create(

                    student=student,
                    fee_template=fee_template,
                    concession=concession,
                    assigned_by=request.user,
                )

                generate_student_fees(
                    student=student,
                    fee_template=fee_template,
                )

        except Exception as e:

            return CustomResponse.errorResponse(
                description=str(e),
            )
        return CustomResponse.successResponse(
            description="Student created successfully.",
            data={
                "id": str(student.id),
                "name": student.name,
                "admission_number": student.admission_number,
            },
        )




class BulkUploadStudentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]
    required_permission = "student.bulk_upload"
    parser_classes = [MultiPartParser,]
    def post(self, request):
        school = request.school
        if school is None:
            return CustomResponse.errorResponse(
                description="School not found.",
            )
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
            "Academic Year",
            "Grade",
            "Section",
            "Admission Number",
            "Roll Number",
            "Name",
            "Gender",
            "Date Of Birth",
            "Admission Date",
            "Fee Concession"
        ]
        for header in required_headers:
            if header not in headers:
                return CustomResponse.errorResponse(
                    description=f"{header} column is missing.",
                )
        success_count = 0
        failed_count = 0
        errors = []
        valid_blood_groups = [
            "A+",
            "A-",
            "B+",
            "B-",
            "AB+",
            "AB-",
            "O+",
            "O-",
        ]
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
                    school=school,
                    grade=grade,
                    name=data.get(
                        "Section",
                    ),
                ).first()
                if section is None:
                    raise Exception(
                        "Section not found.",
                    )
                gender = str(
                    data.get(
                        "Gender",
                    )
                ).upper()
                if gender not in Student.Gender.values:
                    raise Exception(
                        "Invalid gender.",
                    )
                board = str(
                    data.get(
                        "Board",
                        Student.Board.STATE,
                    )
                ).upper()
                if board not in Student.Board.values:
                    raise Exception(
                        "Invalid board.",
                    )
                blood_group = data.get(
                    "Blood Group",
                )
                if blood_group and blood_group not in valid_blood_groups:
                    raise Exception(
                        "Invalid blood group.",
                    )
                if Student.objects.filter(
                    school=school,
                    admission_number=str(
                        data.get(
                            "Admission Number",
                        )
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
                enrollment_type = str(data.get("Enrollment Type",Student.EnrollmentType.NEW,)).upper()
                if enrollment_type not in Student.EnrollmentType.values:
                    raise Exception("Invalid enrollment type.")
                hostel_type = str(data.get("Hostel Type",Student.HostelType.DAY_SCHOLAR, )).upper()
                if hostel_type not in Student.HostelType.values:
                    raise Exception("Invalid hostel type.")
                with transaction.atomic():
                    student = Student.objects.create(
                        school=school,
                        board=board,
                        academic_year=academic_year,
                        grade=grade,
                        section=section,
                        admission_number=str(
                            data.get(
                                "Admission Number",
                            )
                        ).strip(),
                        roll_number=data.get(
                            "Roll Number",
                        ),
                        name=str(
                            data.get(
                                "Name",
                            )
                        ).strip(),
                        gender=gender,
                        date_of_birth=data.get(
                            "Date Of Birth",
                        ),
                        admission_date=data.get(
                            "Admission Date",
                        ),
                        enrollment_type=enrollment_type,
                        place_of_birth=data.get(
                            "Place Of Birth",
                        ),
                        blood_group=blood_group,
                        nationality=data.get(
                            "Nationality",
                            "Indian",
                        ),
                        mother_tongue=data.get(
                            "Mother Tongue",
                        ),
                        aadhaar_number=data.get(
                            "Aadhaar Number",
                        ),
                        religion=data.get(
                            "Religion",
                        ),
                        caste=data.get(
                            "Caste",
                        ),
                        sub_caste=data.get(
                            "Sub Caste",
                        ),
                        student_category=data.get(
                            "Student Category",
                        ),
                        email=data.get(
                            "Email",
                        ),
                        address=data.get(
                            "Address",
                        ),
                        father_name=data.get(
                            "Father Name",
                        ),
                        father_mobile=data.get(
                            "Father Mobile",
                        ),
                        father_occupation=data.get(
                            "Father Occupation",
                        ),
                        mother_name=data.get(
                            "Mother Name",
                        ),
                        mother_mobile=data.get(
                            "Mother Mobile",
                        ),
                        mother_occupation=data.get(
                            "Mother Occupation",
                        ),
                        guardian_name=data.get(
                            "Guardian Name",
                        ),
                        guardian_mobile=data.get(
                            "Guardian Mobile",
                        ),
                        guardian_occupation=data.get(
                            "Guardian Occupation",
                        ),
                        previous_school_name=data.get(
                            "Previous School",
                        ),
                        previous_exam_percentage=data.get(
                            "Previous Exam Percentage",
                        ),
                        transport_required=bool(
                            data.get(
                                "Transport Required",
                                False,
                            )
                        ),
                        pickup_point=data.get(
                            "Pickup Point",
                        ),
                        hostel_type=data.get(
                            "Hostel Type",
                            Student.HostelType.DAY_SCHOLAR,
                        ),
                        status=Student.Status.ACTIVE,)
                    fee_concession_name = (str(data.get("Fee Concession", "")).strip())
                    concession = None
                    if fee_concession_name:
                        concession = FeeConcession.objects.filter(school=school,name__iexact=fee_concession_name).first()
                        if concession is None:
                            raise Exception(f"Fee concession '{fee_concession_name}' not found.")


                    fee_template = FeeTemplate.objects.filter(
                        school=school,
                        academic_year=academic_year,
                        grade=grade,
                        is_active=True,).first()
                    if fee_template is None:
                        raise Exception(f"Fee template not configured for grade '{grade.name}'.")
                    assignment, _ = StudentFeeAssignment.objects.get_or_create(
                        student=student,
                        fee_template=fee_template,
                        defaults={"concession": concession,
                        "assigned_by": request.user,
                        },)
                    generate_student_fees(
                        student=student,
                        fee_template=fee_template,
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






class DownloadStudentTemplateAPIView(APIView):

    permission_classes = [

        IsAuthenticated,

        HasPermission,

    ]

    required_permission = "student.bulk_upload"

    def get(self, request):

        workbook = Workbook()

        sheet = workbook.active

        sheet.title = "Students"

        headers = [

            "Academic Year",

            "Grade",

            "Section",

            "Board",

            "Admission Number",

            "Roll Number",

            "Name",

            "Gender",

            "Date Of Birth",

            "Admission Date",

            "Enrollment Type",

            "Place Of Birth",

            "Blood Group",

            "Nationality",

            "Mother Tongue",

            "Aadhaar Number",

            "Religion",

            "Caste",

            "Sub Caste",

            "Student Category",

            "Identification Marks",

            "Email",

            "Address",

            "Emergency Contact Name",

            "Emergency Contact Mobile",

            "Father Name",

            "Father Mobile",

            "Father Occupation",

            "Mother Name",

            "Mother Mobile",

            "Mother Occupation",

            "Guardian Name",

            "Guardian Mobile",

            "Guardian Occupation",

            "Previous School",

            "Previous School TC Number",

            "Previous Exam Percentage",

            "Transport Required",

            "Pickup Point",

            "Hostel Type",

            "Fee Concession"

        ]

        for column_number, header in enumerate(
            headers,
            start=1,
        ):

            sheet.cell(
                row=1,
                column=column_number,
                value=header,
            )

        sample_row = [

            "2025-2026",

            "Grade 1",

            "A",

            "CBSE",

            "ADM001",

            1,

            "Rahul Kumar",

            "MALE",

            "2018-05-10",

            "2025-06-01",

            "NEW",

            "Hyderabad",

            "O+",

            "Indian",

            "Telugu",

            "123456789012",

            "Hindu",

            "OC",

            "Kamma",

            "General",

            "Mole on chin",

            "rahul@gmail.com",

            "Hyderabad",

            "Ramesh",

            "9876543210",

            "Ramesh",

            "9876543210",

            "Engineer",

            "Sita",

            "9876543211",

            "Teacher",

            "Ramesh",

            "9876543210",

            "Engineer",

            "ABC School",

            "TC123",

            92.5,

            True,

            "Miyapur",

            "DAY_SCHOLAR",

        ]


        excel_file = BytesIO()

        workbook.save(excel_file)

        excel_file.seek(0)

        file_name = (

            f"templates/student_template.xlsx"

        )

        file_path = default_storage.save(

            file_name,

            ContentFile(

                excel_file.getvalue()

            ),

        )

        file_url = (

            settings.MEDIA_URL

            + file_path

        )

        return CustomResponse.successResponse(

            description="Student template generated successfully.",

            data={

                "file_url": file_url,

                "file_path": file_path,

            },

        )

class StudentListAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "student.view"

    pagination_class = CustomPageNumberPagination

    def get(self, request):

        school = request.school

        students = Student.objects.select_related(

            "school",

            "academic_year",

            "grade",

            "section",

        ).filter(

            school=school,

        )

        academic_year_id = request.query_params.get(

            "academic_year_id",

        )

        grade_id = request.query_params.get(

            "grade_id",

        )

        section_id = request.query_params.get(

            "section_id",

        )

        board = request.query_params.get(

            "board",

        )

        hostel_type = request.query_params.get(

            "hostel_type",

        )

        status = request.query_params.get(

            "status",

        )

        search = request.query_params.get(

            "search",

        )

        if academic_year_id:

            students = students.filter(

                academic_year_id=academic_year_id,

            )

        if grade_id:

            students = students.filter(

                grade_id=grade_id,

            )

        if section_id:

            students = students.filter(

                section_id=section_id,

            )

        if board:

            students = students.filter(

                board=board,

            )

        if hostel_type:

            students = students.filter(

                hostel_type=hostel_type,

            )

        if status:

            students = students.filter(

                status=status,

            )

        if search:

            students = students.filter(

                Q(
                    name__icontains=search,
                )
                |
                Q(
                    admission_number__icontains=search,
                )
                |
                Q(
                    father_mobile__icontains=search,
                )
                |
                Q(
                    mother_mobile__icontains=search,
                )

            )

        students = students.order_by(

            "roll_number",

        )

        total = students.count()

        paginator = self.pagination_class()

        page = paginator.paginate_queryset(

            students,

            request,

        )

        data = []

        for student in page:

            data.append(

                {

                    "id": str(student.id),

                    "admission_number": student.admission_number,

                    "roll_number": student.roll_number,

                    "name": student.name,

                    "board": student.board,

                    "gender": student.gender,

                    "date_of_birth": student.date_of_birth,

                    "blood_group": student.blood_group,

                    "status": student.status,

                    "school": {

                        "id": str(student.school.id),

                        "name": student.school.name,

                    },

                    "academic_year": {

                        "id": str(student.academic_year.id),

                        "name": student.academic_year.name,

                    },

                    "grade": {

                        "id": str(student.grade.id),

                        "name": student.grade.name,

                    },

                    "section": {

                        "id": str(student.section.id),

                        "name": student.section.name,

                    },

                    "father_name": student.father_name,

                    "father_mobile": student.father_mobile,

                    "mother_name": student.mother_name,

                    "mother_mobile": student.mother_mobile,

                    "guardian_name": student.guardian_name,

                    "guardian_mobile": student.guardian_mobile,

                    "hostel_type": student.hostel_type,

                    "transport_required": student.transport_required,

                }

            )

        return CustomResponse.successResponse(

            data=data,

            total=total,

        )

# -------------------------------
# Create Student Document API
# -------------------------------

class CreateStudentDocumentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_document.create"

    def post(self, request):
        school = request.school

        student = Student.objects.filter(
            id=request.data.get(
                "student_id",
            ),
        ).first()

        if student is None:

            return CustomResponse.errorResponse(
                description="Student not found.",
            )

        academic_year = None

        if request.data.get(
            "academic_year_id",
        ):

            academic_year = AcademicYear.objects.filter(
                id=request.data.get(
                    "academic_year_id",
                ),school=school,
            ).first()

            if academic_year is None:

                return CustomResponse.errorResponse(
                    description="Academic year not found.",
                )

        if request.data.get(
            "document_type",
        ) not in StudentDocument.DocumentType.values:

            return CustomResponse.errorResponse(
                description="Invalid document type.",
            )

        document = StudentDocument.objects.create(

            student=student,

            academic_year=academic_year,

            document_type=request.data.get(
                "document_type",
            ),

            title=request.data.get(
                "title",
            ),

            file_url=request.data.get(
                "file_url",
            ),

            remarks=request.data.get(
                "remarks",
            ),

            status=request.data.get(
                "status",
                StudentDocument.Status.ACTIVE,
            ),

        )

        return CustomResponse.successResponse(

            description="Student document created successfully.",

            data={
                "id": str(document.id),
            },

        )


# -------------------------------
# Student Document List API
# -------------------------------

class StudentDocumentListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_document.view"

    def get(self, request):
        school = request.school

        documents = StudentDocument.objects.select_related(

            "student",

            "academic_year",

        ).filter(student__school=school,)

        student_id = request.query_params.get(
            "student_id",
        )

        academic_year_id = request.query_params.get(
            "academic_year_id",
        )

        document_type = request.query_params.get(
            "document_type",
        )

        status = request.query_params.get(
            "status",
        )

        if student_id:

            documents = documents.filter(
                student_id=student_id,
            )

        if academic_year_id:

            documents = documents.filter(
                academic_year_id=academic_year_id,
            )

        if document_type:

            documents = documents.filter(
                document_type=document_type,
            )

        if status:

            documents = documents.filter(
                status=status,
            )

        data = []

        for document in documents:

            data.append(

                {

                    "id": str(document.id),

                    "student": {

                        "id": str(document.student.id),

                        "name": document.student.name,

                    },

                    "academic_year": (

                        {

                            "id": str(document.academic_year.id),

                            "name": document.academic_year.name,

                        }

                        if document.academic_year

                        else None

                    ),

                    "document_type": document.document_type,

                    "title": document.title,

                    "file_url": document.file_url,

                    "remarks": document.remarks,

                    "status": document.status,

                }

            )

        return CustomResponse.successResponse(
            data=data,
        )


# -------------------------------
# Update Student Document API
# -------------------------------

class UpdateStudentDocumentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_document.update"

    def put(self,request,document_id,):
        school = request.school

        document = StudentDocument.objects.filter(
            id=document_id,student__school=school,
        ).first()

        if document is None:

            return CustomResponse.errorResponse(
                description="Student document not found.",
            )

        if request.data.get(
            "academic_year_id",
        ):

            academic_year = AcademicYear.objects.filter(
                id=request.data.get(
                    "academic_year_id",
                ),school=school,
            ).first()

            if academic_year is None:

                return CustomResponse.errorResponse(
                    description="Academic year not found.",
                )

            document.academic_year = academic_year

        if request.data.get(
            "document_type",
        ):

            if request.data.get(
                "document_type",
            ) not in StudentDocument.DocumentType.values:

                return CustomResponse.errorResponse(
                    description="Invalid document type.",
                )

            document.document_type = request.data.get(
                "document_type",
            )

        document.title = request.data.get(
            "title",
            document.title,
        )

        document.file_url = request.data.get(
            "file_url",
            document.file_url,
        )

        document.remarks = request.data.get(
            "remarks",
            document.remarks,
        )

        document.status = request.data.get(
            "status",
            document.status,
        )

        document.save()

        return CustomResponse.successResponse(
            description="Student document updated successfully.",
        )

class CreateStaffAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "staff.create"

    def post(self,request):

        school = request.school

        if school is None:
            return CustomResponse.errorResponse(description="School not found.")

        required_fields = [
            "employee_id",
            "staff_type",
            "name",
            "gender",
            "mobile",
            "joining_date",
        ]

        for field in required_fields:
            if request.data.get(field) in [None,""]:
                return CustomResponse.errorResponse(description=f"{field} is required.")

        staff_type = request.data.get("staff_type")

        if staff_type not in Staff.StaffType.values:
            return CustomResponse.errorResponse(description="Invalid staff type.")

        if request.data.get("gender") not in Staff.Gender.values:
            return CustomResponse.errorResponse(description="Invalid gender.")

        mobile = str(request.data.get("mobile"))

        if not mobile.isdigit() or len(mobile) != 10:
            return CustomResponse.errorResponse(description="Enter valid mobile number.")

        if Staff.objects.filter(school=school,employee_id=request.data.get("employee_id")).exists():
            return CustomResponse.errorResponse(description="Employee ID already exists.")

        if Staff.objects.filter(school=school,mobile=mobile).exists():
            return CustomResponse.errorResponse(description="Mobile number already exists.")

        email = request.data.get("email")

        if email and Staff.objects.filter(school=school,email=email).exists():
            return CustomResponse.errorResponse(description="Email already exists.")

        role = Roles.objects.filter(role_name=staff_type).first()

        if role is None:
            return CustomResponse.errorResponse(description=f"{staff_type.title()} role not configured.")

        try:

            with transaction.atomic():

                user = UserMaster.objects.create(

                    school=school,

                    name=request.data.get("name").strip(),

                    mobile=mobile,

                    email=email,

                    is_active=True,

                )

                staff = Staff.objects.create(

                    school=school,

                    employee_id=request.data.get("employee_id").strip(),

                    staff_type=staff_type,

                    name=request.data.get("name").strip(),

                    gender=request.data.get("gender"),

                    date_of_birth=request.data.get("date_of_birth"),

                    mobile=mobile,

                    email=email,

                    qualification=request.data.get("qualification"),

                    experience=request.data.get("experience",0),

                    joining_date=request.data.get("joining_date"),

                    status=request.data.get("status",Staff.Status.ACTIVE),

                    profile_image=request.data.get("profile_image"),

                    address=request.data.get("address"),

                    emergency_contact_name=request.data.get("emergency_contact_name"),

                    emergency_contact_mobile=request.data.get("emergency_contact_mobile"),

                )

                UserRoles.objects.create(

                    user=user,

                    role=role,

                    assigned_by=request.user,

                )

        except Exception as e:

            return CustomResponse.errorResponse(description=str(e))

        return CustomResponse.successResponse(

            description="Staff created successfully.",

            data={
                "id":str(staff.id),
                "employee_id":staff.employee_id,
                "name":staff.name,
                "role":role.role_name,
            },

        )
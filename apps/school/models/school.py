import random
import string
import uuid

from django.db import models

from apps.core.models import UserMaster
from shared.managers import SoftDeleteManager
from shared.mixins.base_model import AuditModel

class Organization(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    name = models.CharField(max_length=255,unique=True,)
    code = models.CharField(max_length=50,unique=True,)

    email = models.EmailField(unique=True,)

    phone_number = models.CharField(max_length=20,unique=True,)

    address = models.TextField(blank=True,null=True,)

    website = models.CharField(max_length=30,null=True,)

    logo = models.CharField(max_length=300,null=True,)

    status = models.CharField(max_length=20,choices=Status.choices, default=Status.ACTIVE,)

    class Meta:

        db_table = "organizations"

        ordering = ["-created_at"]

    def __str__(self):

        return self.name


# class School(AuditModel):
#     class BoardType(models.TextChoices):
#         CBSE = "CBSE", "CBSE"
#         ICSE = "ICSE", "ICSE"
#         STATE = "STATE", "State Board"
#         INTERNATIONAL = "INTERNATIONAL", "International"
#         OTHER = "OTHER", "Other"
#
#     class Status(models.TextChoices):
#         ACTIVE = "ACTIVE", "Active"
#         INACTIVE = "INACTIVE", "Inactive"
#
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False,
#     )
#
#     name = models.CharField(max_length=255)
#
#     code = models.CharField(
#         max_length=50,
#         blank=True,
#         null=True,
#     )
#
#     board = models.CharField(
#         max_length=30,
#         choices=BoardType.choices,
#         default=BoardType.OTHER,
#     )
#
#     email = models.CharField(max_length=50,
#         unique=True
#     )
#
#     phone_number = models.CharField(
#         max_length=20,
#         unique=True,
#     )
#
#     principal_name = models.CharField(
#         max_length=255,
#         blank=True,
#         null=True,
#     )
#
#     total_students = models.PositiveIntegerField(
#         default=0,
#     )
#
#     total_staff = models.PositiveIntegerField(
#         default=0,
#     )
#
#     established_year = models.PositiveIntegerField(
#         blank=True,
#         null=True,
#     )
#
#     address = models.TextField()
#
#     city = models.CharField(max_length=100)
#
#     state = models.CharField(max_length=100)
#
#     country = models.CharField(
#         max_length=100,
#         default="India",
#     )
#
#     pincode = models.CharField(
#         max_length=20,
#         blank=True,
#         null=True,
#     )
#
#     website = models.URLField(
#         blank=True,
#         null=True,
#     )
#
#     logo = models.URLField(
#         blank=True,
#         null=True,
#     )
#
#     is_email_verified = models.BooleanField(default=False)
#
#     is_phone_verified = models.BooleanField(default=False)
#
#     status = models.CharField(
#         max_length=20,
#         choices=Status.choices,
#         default=Status.ACTIVE,
#     )
#
#     class Meta:
#         db_table = "schools"
#         ordering = ["-created_at"]
#         indexes = [
#             models.Index(fields=["code"]),
#             models.Index(fields=["email"]),
#             models.Index(fields=["phone_number"]),
#         ]
#
#     def __str__(self):
#         return f"{self.name} ({self.code})"

class School(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class BoardType(models.TextChoices):

        CBSE = "CBSE", "CBSE"

        ICSE = "ICSE", "ICSE"

        STATE = "STATE", "State Board"

        INTERNATIONAL = "INTERNATIONAL", "International"

        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    organization = models.ForeignKey(Organization,on_delete=models.CASCADE,related_name="schools",null=True,blank=True,)

    name = models.CharField(max_length=255,)

    code = models.CharField(max_length=50,unique=True,)

    board = models.CharField(max_length=30,choices=BoardType.choices,default=BoardType.OTHER,)

    email = models.EmailField(unique=True,)

    phone_number = models.CharField(max_length=20,unique=True,)

    principal_name = models.CharField(max_length=255,blank=True,null=True,)

    principal_email = models.CharField(blank=True,null=True,)

    principal_mobile = models.CharField(max_length=20,blank=True,null=True,)

    established_year = models.PositiveIntegerField(blank=True,null=True,)

    address = models.TextField()

    city = models.CharField(max_length=100,)

    state = models.CharField(max_length=100,)

    country = models.CharField(max_length=100,default="India")

    pincode = models.CharField(max_length=20,blank=True,null=True,)

    website = models.CharField(max_length=30,null=True,)

    logo = models.CharField(max_length=300,blank=True,null=True)

    primary_color = models.CharField(max_length=100, default="FFFFFF")

    secondary_color = models.CharField(max_length=100, default="FFFFFF")

    is_email_verified = models.BooleanField(default=False,)

    is_phone_verified = models.BooleanField(default=False,)

    status = models.CharField(max_length=20,choices=Status.choices,default=Status.ACTIVE,)

    class Meta:

        db_table = "schools"

        ordering = ["-created_at"]

        indexes = [

            models.Index(fields=["code"]),

            models.Index(fields=["organization"]),

        ]

    def __str__(self):

        return self.name

class SchoolConfiguration(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    school = models.OneToOneField(School,on_delete=models.CASCADE,related_name="configuration",)

    website_url = models.URLField(max_length=500,null=True,blank=True,)

    backoffice_url = models.URLField(max_length=500,null=True,blank=True,)

    api_base_url = models.URLField(max_length=500,null=True,blank=True,)

    logo_url = models.URLField(max_length=500,null=True,blank=True,)

    favicon_url = models.URLField(max_length=500,null=True,blank=True,)

    primary_color = models.CharField(max_length=20,default="#2563EB",)

    secondary_color = models.CharField(max_length=20,default="#FFFFFF",)

    parent_android_version = models.CharField(max_length=20,null=True,blank=True,)

    parent_android_force_update = models.BooleanField( default=False,)

    parent_playstore_url = models.URLField(max_length=500,null=True,blank=True,)

    parent_ios_version = models.CharField(max_length=20,null=True,blank=True,)

    parent_ios_force_update = models.BooleanField(default=False,)

    parent_appstore_url = models.URLField(max_length=500,null=True,blank=True,)

    admin_android_version = models.CharField(max_length=20,null=True,blank=True,)

    admin_android_force_update = models.BooleanField(default=False,)

    admin_playstore_url = models.URLField( max_length=500,null=True,blank=True,)

    admin_ios_version = models.CharField(max_length=20,null=True,blank=True,)

    admin_ios_force_update = models.BooleanField(default=False,)

    admin_appstore_url = models.URLField(max_length=500,null=True,blank=True,)

    support_email = models.EmailField(null=True,blank=True,)

    support_mobile = models.CharField(max_length=20,null=True,blank=True,)

    class Meta:
        db_table = "school_configuration"




class SchoolClient(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class ClientType(models.TextChoices):

        WEBSITE = "WEBSITE", "Website"

        BACKOFFICE = "BACKOFFICE", "Backoffice"

        PARENT_ANDROID = "PARENT_ANDROID", "Parent Android"

        PARENT_IOS = "PARENT_IOS", "Parent iOS"

        ADMIN_ANDROID = "ADMIN_ANDROID", "Admin Android"

        ADMIN_IOS = "ADMIN_IOS", "Admin iOS"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    school = models.ForeignKey(School,on_delete=models.CASCADE,related_name="clients",)

    client_type = models.CharField(max_length=30,choices=ClientType.choices,)

    identifier = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Website URL, Backoffice URL, Android Package or iOS Bundle Identifier",
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:

        db_table = "school_client"

        indexes = [models.Index(fields=["school"],),
                   models.Index(fields=["client_type"],),
                   ]

        constraints = [models.UniqueConstraint(
                fields=["school","client_type",],
                name="unique_school_client_type",),]

    def __str__(self):
        return f"{self.school.name} - {self.client_type}"



class Branch(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    school = models.ForeignKey(School,on_delete=models.CASCADE,related_name="branches",)

    name = models.CharField( max_length=255,)

    code = models.CharField(max_length=50, unique=True,)

    email = models.EmailField(blank=True,null=True,)

    phone_number = models.CharField(max_length=20,blank=True,null=True,)

    address = models.TextField()

    city = models.CharField(max_length=100,)

    state = models.CharField(max_length=100,)

    country = models.CharField( max_length=100,default="India",)

    pincode = models.CharField(max_length=20,blank=True,null=True,)

    branch_head_name = models.CharField( max_length=255,blank=True,null=True,)

    status = models.CharField(max_length=20,choices=Status.choices,default=Status.ACTIVE,)

    class Meta:

        db_table = "school_branches"

        ordering = ["-created_at"]

        indexes = [

            models.Index(fields=["school"]),

            models.Index(fields=["code"]),

        ]

    def __str__(self):

        return f"{self.school.name} - {self.name}"


class AcademicYear(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    school = models.ForeignKey("school.School",on_delete=models.CASCADE,related_name="academic_years", )

    name = models.CharField(max_length=100,)

    start_date = models.DateField()

    end_date = models.DateField()

    status = models.CharField(max_length=20,choices=Status.choices,default=Status.ACTIVE,)

    class Meta:

        db_table = "academic_years"

        constraints = [

            models.UniqueConstraint(

                fields=["school", "name"],

                name="unique_school_academic_year",

            )

        ]

        indexes = [

            models.Index(fields=["school"]),

            models.Index(fields=["status"]),

        ]

    def __str__(self):

        return f"{self.school.name} - {self.name}"



class Grade(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    school = models.ForeignKey("school.School",on_delete=models.CASCADE,related_name="grades",)

    academic_year = models.ForeignKey("school.AcademicYear",on_delete=models.CASCADE,related_name="grades",)

    name = models.CharField(max_length=50,)

    display_order = models.PositiveIntegerField(default=1,)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE,)

    class Meta:

        db_table = "grades"

        constraints = [

            models.UniqueConstraint(

                fields=["school","academic_year","name", ],

                name="unique_grade_per_school",

            )

        ]

    def __str__(self):

        return self.name

class Section(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    grade = models.ForeignKey(Grade,on_delete=models.CASCADE,related_name="sections",)

    branch = models.ForeignKey(Branch,on_delete=models.SET_NULL,null=True,blank=True,related_name="sections",)

    name = models.CharField(max_length=30,)

    class_teacher = models.ForeignKey("Staff", on_delete=models.SET_NULL,null=True,blank=True,related_name="class_teacher_sections",)

    capacity = models.PositiveIntegerField(default=40,)

    status = models.CharField(max_length=20,choices=Status.choices,default=Status.ACTIVE,)

    class Meta:

        db_table = "sections"

        constraints = [
            models.UniqueConstraint(
                fields=["grade", "branch", "name"],
                condition=models.Q(branch__isnull=False),
                name="unique_section_per_grade_branch",
            ),
            models.UniqueConstraint(
                fields=["grade", "name"],
                condition=models.Q(branch__isnull=True),
                name="unique_section_per_grade_without_branch",
            ),
]

    def __str__(self):

        return f"{self.grade.name}-{self.name}"

class Student(AuditModel):

    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class Gender(models.TextChoices):

        MALE = "MALE", "Male"

        FEMALE = "FEMALE", "Female"

        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    class EnrollmentType(models.TextChoices):

        NEW = "NEW", "New Admission"

        TRANSFER = "TRANSFER", "Transfer"

        RE_ADMISSION = "RE_ADMISSION", "Re Admission"

    class HostelType(models.TextChoices):

        DAY_SCHOLAR = "DAY_SCHOLAR", "Day Scholar"

        HOSTELLER = "HOSTELLER", "Hosteller"

    class Board(models.TextChoices):

        STATE = "STATE", "State"

        CBSE = "CBSE", "CBSE"

        ICSE = "ICSE", "ICSE"

        IB = "IB", "IB"

        IGCSE = "IGCSE", "IGCSE"

        NIOS = "NIOS", "NIOS"

        OTHER = "OTHER", "Other"




    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    # Academic
    board = models.CharField(max_length=20,choices=Board.choices,default=Board.STATE,db_index=True,)

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="students",
    )
    branch = models.ForeignKey(
    Branch,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="students",
)

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="students",
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name="students",
    )

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="students",
    )

    admission_number = models.CharField(
        max_length=50,
    )

    roll_number = models.PositiveIntegerField()

    enrollment_type = models.CharField(
        max_length=20,
        choices=EnrollmentType.choices,
        default=EnrollmentType.NEW,
    )

    admission_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    # Student Information

    name = models.CharField(
        max_length=100,
    )

    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
    )

    date_of_birth = models.DateField()

    place_of_birth = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    blood_group = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    photo_url = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    nationality = models.CharField(
        max_length=100,
        default="Indian",
    )

    mother_tongue = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    # Government / Demographics

    aadhaar_number = models.CharField(
        max_length=12,
        null=True,
        blank=True,
        db_index=True,
    )

    religion = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    caste = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    sub_caste = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    student_category = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    identification_marks = models.TextField(
        null=True,
        blank=True,
    )

    # Contact

    email = models.EmailField(
        null=True,
        blank=True,
    )

    address = models.TextField(
        null=True,
        blank=True,
    )

    emergency_contact_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    emergency_contact_mobile = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    # Father

    father_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    father_mobile = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
    )

    father_occupation = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    # Mother

    mother_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    mother_mobile = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
    )

    mother_occupation = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    # Guardian

    guardian_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    guardian_mobile = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
    )

    guardian_occupation = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    # Previous School

    previous_school_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    previous_school_tc_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    previous_exam_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Transport

    transport_required = models.BooleanField(
        default=False,
    )

    pickup_point = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    # Hostel

    hostel_type = models.CharField(
        max_length=20,
        choices=HostelType.choices,
        default=HostelType.DAY_SCHOLAR,
    )

    class Meta:

        db_table = "students"

        ordering = [
            "roll_number",
        ]

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "school",
                    "admission_number",
                ],
                name="unique_student_admission_per_school",
            ),

            models.UniqueConstraint(
                fields=[
                    "section",
                    "roll_number",
                ],
                name="unique_roll_per_section",
            ),

        ]

        indexes = [

            models.Index(
                fields=[
                    "school",
                ]
            ),

            models.Index(
                fields=[
                    "academic_year",
                ]
            ),

            models.Index(
                fields=[
                    "grade",
                ]
            ),

            models.Index(
                fields=[
                    "section",
                ]
            ),

            models.Index(
                fields=[
                    "status",
                ]
            ),
            models.Index(
                fields=[
                    "board",
                ]
            ),

            models.Index(
                fields=[
                    "school",
                    "academic_year",
                ]
            ),

            models.Index(
                fields=[
                    "grade",
                    "section",
                ]
            ),

        ]

    def __str__(self):

        return self.name


class StudentDocument(AuditModel):

    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class DocumentType(models.TextChoices):

        AADHAAR = "AADHAAR", "Aadhaar Card"

        PHOTO = "PHOTO", "Photo"

        BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE", "Birth Certificate"

        TRANSFER_CERTIFICATE = "TRANSFER_CERTIFICATE", "Transfer Certificate"

        BONAFIDE = "BONAFIDE", "Bonafide Certificate"

        ACADEMIC_RECORD = "ACADEMIC_RECORD", "Academic Record"

        ID_CARD = "ID_CARD", "ID Card"

        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    document_type = models.CharField(
        max_length=50,
        choices=DocumentType.choices,
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    title = models.CharField(
        max_length=255,
    )

    file_url = models.CharField(
        max_length=500,
    )

    remarks = models.TextField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:

        db_table = "student_documents"

        indexes = [

            models.Index(
                fields=["student"],
            ),

            models.Index(
                fields=["document_type"],
            ),

        ]

class Staff(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class StaffType(models.TextChoices):
        TEACHER = "TEACHER", "Teacher"
        DRIVER = "DRIVER", "Driver"
        # ACCOUNTANT = "ACCOUNTANT", "Accountant"
        # RECEPTIONIST = "RECEPTIONIST", "Receptionist"
        # LIBRARIAN = "LIBRARIAN", "Librarian"
        PRINCIPAL = "PRINCIPAL", "Principal"
        ADMIN = "ADMIN", "Admin"
        # OFFICE_STAFF = "OFFICE_STAFF", "Office Staff"
        # SECURITY = "SECURITY", "Security"
        # ATTENDER = "ATTENDER", "Attender"
        # LAB_ASSISTANT = "LAB_ASSISTANT", "Lab Assistant"
        # TRANSPORT_MANAGER = "TRANSPORT_MANAGER", "Transport Manager"

    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        RESIGNED = "RESIGNED", "Resigned"
        TERMINATED = "TERMINATED", "Terminated"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    school = models.ForeignKey(School,on_delete=models.CASCADE,related_name="staffs",)

    branch = models.ForeignKey(Branch,on_delete=models.SET_NULL,null=True,blank=True,related_name="staffs",)

    user = models.OneToOneField(UserMaster,on_delete=models.CASCADE,related_name="staff",)

    employee_id = models.CharField(max_length=50,)

    staff_type = models.CharField(max_length=30,choices=StaffType.choices,)

    name = models.CharField(max_length=255,)

    gender = models.CharField(max_length=10,choices=Gender.choices,)

    date_of_birth = models.DateField(null=True,blank=True,)

    mobile = models.CharField(max_length=15,)

    email = models.EmailField(null=True,blank=True,)

    qualification = models.CharField(max_length=255,null=True,blank=True,)

    experience = models.DecimalField(max_digits=5,decimal_places=1,default=0, )

    joining_date = models.DateField()

    status = models.CharField(max_length=20,choices=Status.choices,default=Status.ACTIVE,)

    profile_image = models.URLField(null=True, blank=True,)

    address = models.TextField(null=True,blank=True,)

    emergency_contact_name = models.CharField(max_length=255,null=True,blank=True,)

    emergency_contact_mobile = models.CharField(max_length=15,null=True,blank=True,)

    class Meta:

        db_table = "staff"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "school",
                    "employee_id",
                ],
                name="unique_staff_employee_id",
            ),
        ]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["staff_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["mobile"]),
        ]

class StaffDocument(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class DocumentType(models.TextChoices):
        AADHAAR = "AADHAAR","Aadhaar"
        PAN = "PAN","PAN"
        DRIVING_LICENSE = "DRIVING_LICENSE","Driving License"
        PASSPORT = "PASSPORT","Passport"
        PHOTO = "PHOTO","Photo"
        RESUME = "RESUME","Resume"
        QUALIFICATION_CERTIFICATE = "QUALIFICATION_CERTIFICATE","Qualification Certificate"
        EXPERIENCE_CERTIFICATE = "EXPERIENCE_CERTIFICATE","Experience Certificate"
        MEDICAL_CERTIFICATE = "MEDICAL_CERTIFICATE","Medical Certificate"
        POLICE_VERIFICATION = "POLICE_VERIFICATION","Police Verification"
        CONTRACT = "CONTRACT","Contract"
        OTHER = "OTHER","Other"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    staff = models.ForeignKey(Staff,on_delete=models.CASCADE,related_name="documents",)

    document_type = models.CharField(max_length=50,choices=DocumentType.choices,)

    document_name = models.CharField(max_length=255,)

    document_number = models.CharField(max_length=100,null=True,blank=True,)

    document_url = models.URLField(max_length=500,)

    issue_date = models.DateField(null=True,blank=True,)

    expiry_date = models.DateField(null=True,blank=True,)

    is_verified = models.BooleanField(default=False,)

    remarks = models.TextField(null=True,blank=True,)

    class Meta:

        db_table = "staff_documents"

        constraints = [
            models.UniqueConstraint(fields=["staff","document_type"],name="unique_staff_document_type",),
        ]

        indexes = [
            models.Index(fields=["staff"]),
            models.Index(fields=["document_type"]),
            models.Index(fields=["expiry_date"]),
        ]

    def __str__(self):
        return f"{self.staff.name} - {self.document_type}"
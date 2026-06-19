import uuid

from django.db import models

from apps.core.models import UserMaster
from apps.school.models import School
from apps.school.models.school import AcademicYear, Grade, Student
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class FeeType(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="fee_types",
    )

    name = models.CharField(
        max_length=100,
    )

    is_optional = models.BooleanField(
        default=False,
    )

    description = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "fee_types"

        constraints = [

            models.UniqueConstraint(
                fields=["school", "name"],
                name="unique_fee_type_per_school",
            )

        ]

        indexes = [

            models.Index(
                fields=["school"],
            ),

            models.Index(
                fields=["school", "name"],
            ),

        ]

class FeeTemplate(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
    )

    name = models.CharField(
        max_length=100,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "fee_templates"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "school",
                    "academic_year",
                    "grade",
                    "name",
                ],
                name="unique_fee_template",
            )

        ]

        indexes = [

            models.Index(
                fields=[
                    "school",
                    "academic_year",
                ]
            ),

            models.Index(
                fields=[
                    "grade",
                ]
            ),

        ]

class FeeTemplateItem(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    fee_template = models.ForeignKey(
        FeeTemplate,
        on_delete=models.CASCADE,
        related_name="items",
    )

    fee_type = models.ForeignKey(
        FeeType,
        on_delete=models.CASCADE,
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    is_mandatory = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "fee_template_items"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "fee_template",
                    "fee_type",
                ],
                name="unique_fee_template_item",
            )

        ]

        indexes = [

            models.Index(
                fields=[
                    "fee_template",
                ]
            ),

            models.Index(
                fields=[
                    "fee_type",
                ]
            ),

        ]

class FeeCollectionPlan(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class PlanType(models.TextChoices):

        ANNUAL = "ANNUAL"

        TERM = "TERM"

        MONTHLY = "MONTHLY"

        QUARTERLY = "QUARTERLY"

        CUSTOM = "CUSTOM"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    fee_template = models.OneToOneField(
        FeeTemplate,
        on_delete=models.CASCADE,
        related_name="collection_plan",
    )

    plan_type = models.CharField(
        max_length=20,
        choices=PlanType.choices,
    )

    class Meta:
        db_table = "fee_collection_plans"

        indexes = [

            models.Index(
                fields=[
                    "fee_template",
                ]
            ),

        ]

class FeeInstallment(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    collection_plan = models.ForeignKey(
        FeeCollectionPlan,
        on_delete=models.CASCADE,
        related_name="installments",
    )

    name = models.CharField(
        max_length=50,
    )

    due_date = models.DateField()

    order = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        db_table = "fee_installments"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "collection_plan",
                    "name",
                ],
                name="unique_installment_name",
            )

        ]

        indexes = [

            models.Index(
                fields=[
                    "collection_plan",
                ]
            ),

            models.Index(
                fields=[
                    "due_date",
                ]
            ),

            models.Index(
                fields=[
                    "collection_plan",
                    "order",
                ]
            ),

        ]

class FeeInstallmentItem(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    installment = models.ForeignKey(
        FeeInstallment,
        on_delete=models.CASCADE,
        related_name="items",
    )

    fee_template_item = models.ForeignKey(
        FeeTemplateItem,
        on_delete=models.CASCADE,
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        db_table = "fee_installment_items"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "installment",
                    "fee_template_item",
                ],
                name="unique_installment_fee_item",
            )

        ]

        indexes = [

            models.Index(
                fields=[
                    "installment",
                ]
            ),

            models.Index(
                fields=[
                    "fee_template_item",
                ]
            ),

        ]



class LateFeeRule(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    class RuleType(models.TextChoices):

        FLAT = "FLAT"

        PER_DAY = "PER_DAY"

        PERCENTAGE = "PERCENTAGE"

    collection_plan = models.ForeignKey(
        FeeCollectionPlan,
        on_delete=models.CASCADE,
    )

    from_day = models.PositiveIntegerField()

    to_day = models.PositiveIntegerField()

    rule_type = models.CharField(
        max_length=20,
        choices=RuleType.choices,
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        db_table = "late_fee_rules"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "collection_plan",
                    "from_day",
                    "to_day",
                ],
                name="unique_late_fee_rule",
            )

        ]

        indexes = [

            models.Index(
                fields=[
                    "collection_plan",
                ]
            ),

            models.Index(
                fields=[
                    "from_day",
                    "to_day",
                ]
            ),

        ]


class FeeConcession(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    class Type(models.TextChoices):

        FLAT = "FLAT"

        PERCENTAGE = "PERCENTAGE"

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
    )

    name = models.CharField(
        max_length=100,
    )

    concession_type = models.CharField(
        max_length=20,
        choices=Type.choices,
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        db_table = "fee_concessions"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "school",
                    "name",
                ],
                name="unique_fee_concession",
            )

        ]

        indexes = [

            models.Index(
                fields=[
                    "school",
                ]
            ),

        ]

class StudentFeeAssignment(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
    )

    fee_template = models.ForeignKey(
        FeeTemplate,
        on_delete=models.CASCADE,
    )

    assigned_date = models.DateField(
        auto_now_add=True,
    )

    assigned_by = models.ForeignKey(
        UserMaster,
        on_delete=models.SET_NULL,
        null=True,
    )

    class Meta:
        db_table = "student_fee_assignments"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "student",
                    "fee_template",
                ],
                name="unique_student_fee_assignment",
            )

        ]

        indexes = [

            models.Index(
                fields=[
                    "student",
                ]
            ),

            models.Index(
                fields=[
                    "fee_template",
                ]
            ),

        ]

class StudentFee(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class Status(models.TextChoices):

        PENDING = "PENDING"

        PARTIAL = "PARTIAL"

        PAID = "PAID"

        OVERDUE = "OVERDUE"

        WAIVED = "WAIVED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
    )

    installment_item = models.ForeignKey(
        FeeInstallmentItem,
        on_delete=models.CASCADE,
    )

    due_date = models.DateField()

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    concession = models.ForeignKey(
        FeeConcession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    scholarship = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    late_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    class Meta:
        db_table = "student_fees"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "student",
                    "installment_item",
                ],
                name="unique_student_installment_fee",
            )

        ]

        indexes = [

            models.Index(
                fields=[
                    "student",
                ]
            ),

            models.Index(
                fields=[
                    "status",
                ]
            ),

            models.Index(
                fields=[
                    "due_date",
                ]
            ),

            models.Index(
                fields=[
                    "student",
                    "status",
                ]
            ),

        ]

class StudentFeePayment(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class PaymentMode(models.TextChoices):

        CASH = "CASH"

        UPI = "UPI"

        CARD = "CARD"

        CHEQUE = "CHEQUE"

        ONLINE = "ONLINE"

        NEFT = "NEFT"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    student_fee = models.ForeignKey(
        StudentFee,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    receipt_number = models.CharField(
        max_length=50,
        unique=True,
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    payment_mode = models.CharField(
        max_length=20,
        choices=PaymentMode.choices,
    )

    payment_date = models.DateTimeField(
        auto_now_add=True,
    )

    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    remarks = models.TextField(
        blank=True,
        null=True,
    )

    collected_by = models.ForeignKey(
        UserMaster,
        on_delete=models.SET_NULL,
        null=True,
    )

    is_cancelled = models.BooleanField(
        default=False,
    )

    class Meta:
        db_table = "student_fee_payments"

        indexes = [

            models.Index(
                fields=[
                    "student_fee",
                ]
            ),

            models.Index(
                fields=[
                    "payment_date",
                ]
            ),

            models.Index(
                fields=[
                    "receipt_number",
                ]
            ),

            models.Index(
                fields=[
                    "transaction_id",
                ]
            ),

            models.Index(
                fields=[
                    "is_cancelled",
                ]
            ),

        ]
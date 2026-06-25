import uuid

from django.db import models

from apps.fee.models import SchoolPaymentGateway, StudentFee
from apps.school.models import School
from apps.school.models.school import Student
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class PaymentTransaction(AuditModel):

    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class Status(models.TextChoices):

        INITIATED = "INITIATED"

        PENDING = "PENDING"

        SUCCESS = "SUCCESS"

        FAILED = "FAILED"

        CANCELLED = "CANCELLED"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
    )

    gateway = models.ForeignKey(
        SchoolPaymentGateway,
        on_delete=models.PROTECT,
    )

    transaction_number = models.CharField(
        max_length=100,
        unique=True,
    )

    gateway_order_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    gateway_transaction_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
    )

    paid_at = models.DateTimeField(null=True,blank=True,)
    class Meta:

        db_table = "payment_transactions"
        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["student"]),
            models.Index(fields=["status"]),
            models.Index(fields=["transaction_number"]),
            models.Index(fields=["gateway_order_id"]),

        ]


class PaymentTransactionItem(AuditModel):
    objects = SoftDeleteManager()

    all_objects = models.Manager()

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    transaction = models.ForeignKey(PaymentTransaction,on_delete=models.CASCADE,related_name="items",)

    student_fee = models.ForeignKey(StudentFee,on_delete=models.PROTECT,)

    amount = models.DecimalField(max_digits=10,decimal_places=2,)

    class Meta:
        db_table = "payment_transaction_items"
        constraints = [
            models.UniqueConstraint(
                fields=["transaction","student_fee",
                ],
                name="unique_transaction_student_fee",
            )

        ]
        indexes = [
            models.Index(fields=["transaction"]),
            models.Index(fields=["student_fee"]),
        ]
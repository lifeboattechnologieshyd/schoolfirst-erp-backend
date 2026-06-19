# from django.db import models
#
# from apps.school.models import School
# from apps.school.models.school import AcademicYear, Grade
# from shared.mixins import AuditModel
#
#
# class FeeType(AuditModel):
#
#     school = models.ForeignKey(
#         School,
#         on_delete=models.CASCADE,
#     )
#
#     name = models.CharField(
#         max_length=100,
#     )
#
#     is_optional = models.BooleanField(
#         default=False,
#     )
#
#     description = models.TextField(
#         null=True,
#         blank=True,
#     )
#
# class FeeTemplate(AuditModel):
#
#     school = models.ForeignKey(
#         School,
#         on_delete=models.CASCADE,
#     )
#
#     academic_year = models.ForeignKey(
#         AcademicYear,
#         on_delete=models.CASCADE,
#     )
#
#     grade = models.ForeignKey(
#         Grade,
#         on_delete=models.CASCADE,
#     )
#
#     name = models.CharField(
#         max_length=100,
#     )
#
#     is_active = models.BooleanField(
#         default=True,
#     )
#
# class FeeTemplateItem(AuditModel):
#
#     fee_template = models.ForeignKey(
#         FeeTemplate,
#         on_delete=models.CASCADE,
#         related_name="items",
#     )
#
#     fee_type = models.ForeignKey(
#         FeeType,
#         on_delete=models.CASCADE,
#     )
#
#     amount = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#     )
#
# class FeeCollectionPlan(AuditModel):
#
#     class Plan(models.TextChoices):
#
#         ANNUAL = "ANNUAL"
#
#         TERM = "TERM"
#
#         MONTHLY = "MONTHLY"
#
#         QUARTERLY = "QUARTERLY"
#
#         CUSTOM = "CUSTOM"
#
#     school = models.ForeignKey(
#         School,
#         on_delete=models.CASCADE,
#     )
#
#     name = models.CharField(
#         max_length=100,
#     )
#
#     plan_type = models.CharField(
#         max_length=20,
#         choices=Plan.choices,
#     )
#
# class FeeInstallment(AuditModel):
#
#     fee_template = models.ForeignKey(
#         FeeTemplate,
#         on_delete=models.CASCADE,
#     )
#
#     name = models.CharField(
#         max_length=50,
#     )
#
#     due_date = models.DateField()
#
#     amount = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#     )
#
# class LateFeeRule(AuditModel):
#
#     school = models.ForeignKey(
#         School,
#         on_delete=models.CASCADE,
#     )
#
#     from_day = models.IntegerField()
#
#     to_day = models.IntegerField()
#
#     fine_amount = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#     )
#
# class StudentFee(AuditModel):
#
#     student = models.ForeignKey(
#         Student,
#         on_delete=models.CASCADE,
#     )
#
#     installment = models.ForeignKey(
#         FeeInstallment,
#         on_delete=models.CASCADE,
#     )
#
#     amount = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#     )
#
#     concession = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         default=0,
#     )
#
#     scholarship = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         default=0,
#     )
#
#     paid_amount = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         default=0,
#     )
#
# class StudentFeePayment(AuditModel):
#
#     student_fee = models.ForeignKey(
#         StudentFee,
#         on_delete=models.CASCADE,
#     )
#
#     amount = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#     )
#
#     payment_mode = models.CharField(
#         max_length=30,
#     )
#
#     transaction_id = models.CharField(
#         max_length=100,
#         null=True,
#         blank=True,
#     )
#
# class FeeConcession(AuditModel):
#
#     school = models.ForeignKey(
#         School,
#         on_delete=models.CASCADE,
#     )
#
#     name = models.CharField(
#         max_length=100,
#     )
#
#     amount = models.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#     )
#
#     is_percentage = models.BooleanField(
#         default=False,
#     )
# import uuid
#
# from django.db import models
#
# from apps.school.models import School
# from apps.school.models.school import Branch, AcademicYear, Grade, Staff, Section
# from shared.managers import SoftDeleteManager
# from shared.mixins import AuditModel
#
#
# class Homework(AuditModel):
#
#     objects = SoftDeleteManager()
#     all_objects = models.Manager()
#
#     class Status(models.TextChoices):
#         DRAFT = "DRAFT", "Draft"
#         PUBLISHED = "PUBLISHED", "Published"
#         CANCELLED = "CANCELLED", "Cancelled"
#
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False,
#     )
#
#     school = models.ForeignKey(
#         School,
#         on_delete=models.CASCADE,
#         related_name="homeworks",
#     )
#
#     branch = models.ForeignKey(
#         Branch,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name="homeworks",
#     )
#
#     academic_year = models.ForeignKey(
#         AcademicYear,
#         on_delete=models.CASCADE,
#         related_name="homeworks",
#     )
#
#     grade = models.ForeignKey(
#         Grade,
#         on_delete=models.CASCADE,
#         related_name="homeworks",
#     )
#
#     subject = models.ForeignKey(
#         Subject,
#         on_delete=models.CASCADE,
#         related_name="homeworks",
#     )
#
#     teacher = models.ForeignKey(
#         Staff,
#         on_delete=models.PROTECT,
#         related_name="created_homeworks",
#     )
#
#     title = models.CharField(max_length=255)
#
#     description = models.TextField()
#
#     assigned_date = models.DateField()
#
#     due_date = models.DateField()
#
#     status = models.CharField(
#         max_length=20,
#         choices=Status.choices,
#         default=Status.DRAFT,
#     )
#
#     class Meta:
#         db_table = "homeworks"
#
#
# class HomeworkSection(AuditModel):
#
#     meeting = models.ForeignKey(
#         Homework,
#         on_delete=models.CASCADE,
#         related_name="homework_sections",
#     )
#
#     section = models.ForeignKey(
#         Section,
#         on_delete=models.CASCADE,
#     )
#
#     class Meta:
#
#         db_table = "homework_sections"
#
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["meeting", "section"],
#                 name="unique_homework_section",
#             )
#         ]
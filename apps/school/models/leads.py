from django.db import models
import uuid

from shared.mixins.base_model import AuditModel

class SchoolLead(AuditModel):
    STATUS_CHOICES = [
        ("lead", "Lead"),
        ("subscribed", "Subscribed"),

    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=100)
    number_of_students = models.PositiveIntegerField(default=0)
    location = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email = models.CharField(max_length=50)
    is_mobile_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="lead")


    class Meta:
        db_table = "school_leads"
        ordering = ["-created_at"]

    def __str__(self):
        return self.school_name


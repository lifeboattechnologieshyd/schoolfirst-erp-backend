from django.db import models
import uuid


class SchoolLead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    school_name = models.CharField(max_length=255)

    contact_person = models.CharField(max_length=255)

    number_of_students = models.PositiveIntegerField()

    location = models.CharField(max_length=255)

    phone_number = models.CharField(max_length=20)

    email = models.EmailField()

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "school_leads"
        ordering = ["-created_at"]

    def __str__(self):
        return self.school_name


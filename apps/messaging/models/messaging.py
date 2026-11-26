import uuid

from django.db import models

from apps.core.models import UserMaster
from apps.school.models import School
from apps.school.models.school import Staff, Student
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


def default_available_days():
    # 0 = Monday ... 6 = Sunday
    return [0, 1, 2, 3, 4]


# =====================================================================
#  STAFF CHAT PROFILE
#  Teacher profile screen: about, classroom, available hours, away toggle
# =====================================================================
class StaffChatProfile(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    staff = models.OneToOneField(
        Staff,
        on_delete=models.CASCADE,
        related_name="chat_profile",
    )

    about = models.TextField(
        null=True,
        blank=True,
    )

    # "Room 12, First Floor"
    classroom_location = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    available_days = models.JSONField(
        default=default_available_days,
        blank=True,
    )

    available_from = models.TimeField(
        null=True,
        blank=True,
    )

    available_to = models.TimeField(
        null=True,
        blank=True,
    )

    # Manual switch: False shows the teacher as "Away"
    is_available = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "messaging_staff_profiles"

    def __str__(self):
        return f"{self.staff.name} chat profile"


# =====================================================================
#  CONVERSATION
#  One chat between a parent (user) and a teacher about one student.
# =====================================================================
class Conversation(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archived"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="conversations",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="conversations",
    )

    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="conversations",
    )

    parent_user = models.ForeignKey(
        UserMaster,
        on_delete=models.CASCADE,
        related_name="parent_conversations",
    )

    # ---- Inbox preview ----
    last_message_text = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    last_message_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    last_message_sender_type = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # ---- Unread counters ----
    parent_unread_count = models.PositiveIntegerField(
        default=0,
    )

    staff_unread_count = models.PositiveIntegerField(
        default=0,
    )

    # Teacher inbox "High priority" filter
    is_high_priority = models.BooleanField(
        default=False,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        db_table = "messaging_conversations"

        ordering = [
            "-last_message_at",
            "-created_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "staff",
                    "parent_user",
                ],
                condition=models.Q(is_deleted=False),
                name="unique_messaging_conversation",
            ),
        ]

        indexes = [
            models.Index(fields=["school", "staff", "last_message_at"]),
            models.Index(fields=["parent_user", "student"]),
            models.Index(fields=["staff", "staff_unread_count"]),
        ]

    def __str__(self):
        return f"{self.parent_user} <-> {self.staff.name} ({self.student.name})"


# =====================================================================
#  MESSAGE
#  Text / image / document / audio / location / contact
# =====================================================================
class Message(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class SenderType(models.TextChoices):
        PARENT = "PARENT", "Parent"
        STAFF = "STAFF", "Staff"

    class MessageType(models.TextChoices):
        TEXT = "TEXT", "Text"
        IMAGE = "IMAGE", "Image"
        DOCUMENT = "DOCUMENT", "Document"
        AUDIO = "AUDIO", "Audio"
        LOCATION = "LOCATION", "Location"
        CONTACT = "CONTACT", "Contact"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    sender_type = models.CharField(
        max_length=20,
        choices=SenderType.choices,
    )

    sender_user = models.ForeignKey(
        UserMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_messages",
    )

    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
    )

    # Text, or caption for an attachment
    text = models.TextField(
        null=True,
        blank=True,
    )

    # ---- Image / document / audio ----
    attachment_url = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    attachment_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    attachment_size = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    attachment_mime_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    # ---- Location ----
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    location_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    # ---- Contact ----
    contact_name = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    contact_phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    # ---- Read status (✓ sent, ✓✓ read) ----
    is_read = models.BooleanField(
        default=False,
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Sent by the app so a retry does not create a duplicate message
    client_message_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "messaging_messages"

        ordering = [
            "created_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "conversation",
                    "client_message_id",
                ],
                condition=models.Q(client_message_id__isnull=False),
                name="unique_messaging_client_message_id",
            ),
        ]

        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["conversation", "sender_type", "is_read"]),
        ]

    def __str__(self):
        return f"{self.sender_type} {self.message_type} in {self.conversation_id}"


# =====================================================================
#  PARENT NOTE
#  "Quick Notes" a parent keeps on a teacher's profile (private to parent)
# =====================================================================
class ParentNote(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="parent_notes",
    )

    parent_user = models.ForeignKey(
        UserMaster,
        on_delete=models.CASCADE,
        related_name="parent_notes",
    )

    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="parent_notes",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="parent_notes",
    )

    note = models.CharField(
        max_length=500,
    )

    class Meta:
        db_table = "messaging_parent_notes"

        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(fields=["parent_user", "staff"]),
        ]

    def __str__(self):
        return self.note[:50]

from django.db import models


class JobExitCodes(models.IntegerChoices):
    SUCCESS = 0
    ERROR = 1
    LOCK_NOT_ACQUIRED = 2
    UNHANDLED_EXCEPTION = 3


class OAuthProvider(models.TextChoices):
    GOOGLE = "google", "Google"
    FACEBOOK = "facebook", "Facebook"
    APPLE = "apple", "Apple"


class UserStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    SUSPENDED = "suspended", "Suspended"
    PENDING = "pending", "Pending"


class OTPPurpose(models.TextChoices):
    EMAIL_VERIFICATION = "email_verification", "Email Verification"
    PASSWORD_RESET = "password_reset", "Password Reset"
    LOGIN_FALLBACK = "login_fallback", "Login Fallback"


class InviteCodeType(models.TextChoices):
    GENERIC = "generic", "Generic"
    TARGETED = "targeted", "Targeted"


class ApplicationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class DocusafeAccessType(models.TextChoices):
    FAMILY = "FAMILY", "Family"  # Entire family gets read-only access
    USER = "USER", "User"  # Specific user gets read-only access


class TemporaryShareStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "InActive"
    EXPIRED = "EXPIRED", "Expired"
    BLOCKED = "BLOCKED", "Blocked"


class DocusafeStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    DELETED = "DELETED", "Deleted"


class DocusafeLLMStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    NOT_SUPPORTED = "NOT_SUPPORTED", "Not Supported"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class DocusafeEmbeddingType(models.TextChoices):
    CHUNK = "CHUNK", "Chunk"
    TITLE = "TITLE", "Title"
    SUMMARY = "SUMMARY", "Summary"

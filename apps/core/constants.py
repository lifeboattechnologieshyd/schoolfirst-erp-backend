"""Core app constants."""

# Allowed image file extensions for user-facing image uploads (profile, family).
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

ALLOWED_IMAGE_EXTENSIONS_DISPLAY = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))

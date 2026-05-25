from django.db import models


class GlobalAPIMessageCodes(models.TextChoices):
    INTERNAL_ERROR = "INTERNAL_ERROR", "An unexpected error occurred, please try again later."
    INVALID_REQUEST = "INVALID_REQUEST", "The request is invalid."
    UNAUTHORIZED = "UNAUTHORIZED", "Authentication credentials were not provided or are invalid."
    FORBIDDEN = "FORBIDDEN", "You do not have permission to perform this action."
    NOT_FOUND = "NOT_FOUND", "The requested resource was not found."
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED", "You have exceeded your rate limit."
    VALIDATION_ERROR = "VALIDATION_ERROR", "There was a validation error with your request."
    SUCCESS = "SUCCESS", "The request was successful."
    TOKEN_EXPIRED = "TOKEN_EXPIRED", "The token has expired."
    INVALID_TOKEN = "INVALID_TOKEN", "The token provided is invalid."

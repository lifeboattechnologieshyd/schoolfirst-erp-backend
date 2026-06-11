# shared/exceptions.py

from django.db import IntegrityError

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
    NotFound,
)
from rest_framework.views import exception_handler

from shared.mixins import CustomResponse


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if isinstance(exc, ValidationError):
        return CustomResponse.errorResponse(
            description=exc.detail,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, AuthenticationFailed):
        return CustomResponse.errorResponse(
            description="Authentication failed.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if isinstance(exc, NotAuthenticated):
        return CustomResponse.errorResponse(
            description="Authentication credentials were not provided.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if isinstance(exc, PermissionDenied):
        return CustomResponse.errorResponse(
            description="Permission denied.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, NotFound):
        return CustomResponse.errorResponse(
            description="Resource not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, IntegrityError):
        return CustomResponse.errorResponse(
            description="Database integrity error.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if response is not None:
        return CustomResponse.errorResponse(
            description=response.data,
            status_code=response.status_code,
        )

    return CustomResponse.errorResponse(
        description="Internal server error.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
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
from rest_framework.response import Response
from rest_framework.views import exception_handler

from shared.mixins import CustomResponse

#
# def custom_exception_handler(exc, context):
#
#     response = exception_handler(exc, context)
#
#     if isinstance(exc, ValidationError):
#         return CustomResponse.errorResponse(
#             description=exc.detail,
#             status_code=status.HTTP_400_BAD_REQUEST,
#         )
#
#     if isinstance(exc, AuthenticationFailed):
#         return CustomResponse.errorResponse(
#             description="Authentication failed.",
#             status_code=status.HTTP_401_UNAUTHORIZED,
#         )
#
#     if isinstance(exc, NotAuthenticated):
#         return CustomResponse.errorResponse(
#             description="Authentication credentials were not provided.",
#             status_code=status.HTTP_401_UNAUTHORIZED,
#         )
#
#     if isinstance(exc, PermissionDenied):
#         return CustomResponse.errorResponse(
#             description="Permission denied.",
#             status_code=status.HTTP_403_FORBIDDEN,
#         )
#
#     if isinstance(exc, NotFound):
#         return CustomResponse.errorResponse(
#             description="Resource not found.",
#             status_code=status.HTTP_404_NOT_FOUND,
#         )
#
#     if isinstance(exc, IntegrityError):
#         return CustomResponse.errorResponse(
#             description="Database integrity error.",
#             status_code=status.HTTP_400_BAD_REQUEST,
#         )
#
#     if response is not None:
#         return CustomResponse.errorResponse(
#             description=response.data,
#             status_code=response.status_code,
#         )
#
#     return CustomResponse.errorResponse(
#         description="Internal server error.",
#         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#     )


from rest_framework.views import exception_handler
from rest_framework import status

#
# def custom_exception_handler(exc, context):
#
#     response = exception_handler(exc, context)
#
#     if response is not None:
#
#         description = "Request failed."
#
#         if isinstance(response.data, dict):
#
#             if "detail" in response.data:
#                 description = response.data["detail"]
#
#             else:
#                 description = response.data
#
#         response.data = {
#             "success": False,
#             "data": {},
#             "description": description,
#             "status_code": response.status_code,
#         }
#
#         return response
#
#     return Response(
#         {
#             "success": False,
#             "data": {},
#             "description": "Internal server error.",
#             "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
#         },
#         status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#     )

def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if isinstance(exc, ValidationError):
        return CustomResponse.errorResponse(
            description=exc.detail,
            status_code=400,
        )

    if isinstance(exc, AuthenticationFailed):
        return CustomResponse.errorResponse(
            description="Authentication failed.",
            status_code=401,
        )

    if isinstance(exc, NotAuthenticated):
        return CustomResponse.errorResponse(
            description="Authentication credentials were not provided.",
            status_code=401,
        )

    if isinstance(exc, PermissionDenied):
        return CustomResponse.errorResponse(
            description="Permission denied.",
            status_code=403,
        )

    if isinstance(exc, NotFound):
        return CustomResponse.errorResponse(
            description="Resource not found.",
            status_code=404,
        )

    if isinstance(exc, IntegrityError):
        return CustomResponse.errorResponse(
            description=str(exc),
            status_code=400,
        )

    if response is not None:

        return CustomResponse.errorResponse(
            description=response.data,
            status_code=response.status_code,
        )

    # Log unexpected errors here
    import traceback
    traceback.print_exc()

    return CustomResponse.errorResponse(
        description="Internal server error.",
        status_code=500,
    )
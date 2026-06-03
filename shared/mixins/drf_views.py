from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from django.http import Http404
from rest_framework import status

if TYPE_CHECKING:
    from shared.types import AuthenticatedRequest
from rest_framework.exceptions import (
    APIException,
    ParseError,
    PermissionDenied,
    ValidationError,
)
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
    RetrieveUpdateDestroyAPIView,
    UpdateAPIView,
)
from rest_framework.response import Response

from shared.enums import GlobalAPIMessageCodes

logger = structlog.getLogger("default")


def _flatten_validation_errors(detail: Any, parent_field: str | None = None) -> list[dict[str, Any]]:
    """Recursively flatten DRF serializer error dicts into a flat list.

    Nested field paths are dot-joined (e.g. "rrule.until").
    ``non_field_errors`` keys bubble up under the nearest parent field name.
    """
    if isinstance(detail, dict):
        out: list[dict[str, Any]] = []
        for field, errors in detail.items():
            is_non_field = field == "non_field_errors"
            if is_non_field:
                qualified: str | None = parent_field
            elif parent_field:
                qualified = f"{parent_field}.{field}"
            else:
                qualified = field
            out.extend(_flatten_validation_errors(errors, qualified))
        return out
    if isinstance(detail, (list, tuple)):
        out = []
        for err in detail:
            out.extend(_flatten_validation_errors(err, parent_field))
        return out
    return [
        {
            "type": "field" if parent_field else "global",
            "field": parent_field,
            "issue": None,
            "message": str(detail),
        }
    ]


########################
#    CUSTOM RESPONSE   #
########################


class CustomResponse:
    @staticmethod
    def _response_payload(
        *,
        success: bool,
        message: Any = None,
        data: Any = None,
        error: Any = None,
        meta: Any = None,
        extra: Any = None,
    ) -> dict[str, Any]:
        payload = {
            "success": success,
            "data": data,
            "error": error,
            "meta": meta,
        }
        if extra:
            payload.update(extra)
        return payload

    @staticmethod
    def _legacy_response_payload(
        *,
        success: bool,
        data: Any,
        description: str,
        error_code: Any = 0,
        total: int = 0,
        error: Any = None,
        extra: Any = None,
    ) -> dict[str, Any]:
        return CustomResponse._response_payload(
            success=success,
            data=data,
            error=error,
            meta=None,
            extra={
                "errorCode": error_code,
                "description": description,
                "total": total,
                **(extra or {}),
            },
        )

    @staticmethod
    def _default_error_object(
        error_code: Any = 0,
        details: Any = None,
    ) -> dict[str, Any]:
        return {
            "code": str(error_code) if error_code else "ERROR",
            "details": details,
        }

    @staticmethod
    def build_response(
        success: bool,
        data: Any = None,
        error: Any = None,
        meta: Any = None,
        status: Any = status.HTTP_200_OK,
        **kwargs: Any,
    ) -> Response:
        return Response(
            CustomResponse._response_payload(
                success=success,
                data=data,
                # error=error,
                # meta=meta,
                extra=kwargs,
            ),
            status=status,
        )

    @staticmethod
    def successResponse(  # noqa: N802
        data: Any,
        # errorCode: Any = 0,  # noqa: N803
        description: str = "Request Successful",
        total: int = 0,
        status: Any = status.HTTP_200_OK,
        **kwargs: Any,
    ) -> Response:
        return CustomResponse.build_response(
            success=True,
            # message=description,
            data=data,
            error=None,
            meta=None,
            status=status,
            # errorCode=errorCode,
            description=description,
            total=total,
            **kwargs,
        )

    @staticmethod
    def errorResponse(  # noqa: N802
        data: Any = None,
        errorCode: Any = 0,  # noqa: N803
        description: str = "Request Failed",
        total: int = 0,
        status: Any = status.HTTP_200_OK,
        **kwargs: Any,
    ) -> Response:
        if data is None:
            data = {}

        extra = dict(kwargs)
        error_obj = extra.pop("error", None) or CustomResponse._default_error_object(
            # error_code=errorCode,
            description=description,
            details=data,
        )

        return CustomResponse.build_response(
            success=False,
            # message=description,
            # data=data,
            # error=error_obj,
            # meta=None,
            status=status,
            # errorCode=errorCode,
            description=description,
            total=total,
            **extra,
        )

    @staticmethod
    def _format_validation_errors(detail: Any) -> list[dict[str, Any]]:
        """Format DRF ValidationError details into the standard error list shape.

        Handles nested serializer error dicts by flattening them with dot-joined
        field paths (e.g. ``{"rrule": {"until": [...]}}`` → ``"rrule.until"``).
        """
        return _flatten_validation_errors(detail)


########################################
#   GENERICS OVERRIDES FOR DRF VIEWS   #
########################################


######################
# LIST & CREATE VIEW #
######################


class CustomListCreateAPIView(ListCreateAPIView, CustomResponse):
    request: AuthenticatedRequest

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                # PageNumberPagination uses .page; LimitOffsetPagination uses .count
                if hasattr(self.paginator, "page"):
                    total = self.paginator.page.paginator.count
                    if total:
                        page_num = self.paginator.page.number
                        page_size = self.paginator.page.paginator.per_page
                        total_pages = self.paginator.page.paginator.num_pages
                    else:
                        page_num = 1
                        page_size = 0
                        total_pages = 0
                else:
                    # LimitOffsetPagination
                    total = self.paginator.count
                    limit = self.paginator.limit or total or 0
                    offset = self.paginator.offset or 0
                    page_size = limit
                    page_num = (offset // limit + 1) if limit else 1
                    total_pages = ((total + limit - 1) // limit) if limit else (1 if total else 0)
                    if not total:
                        page_num = 1
                        page_size = 0
                        total_pages = 0

                return self.build_response(
                    success=True,
                    data=serializer.data,
                    meta={
                        "total": total,
                        "page": page_num,
                        "page_size": page_size,
                        "total_pages": total_pages,
                    },
                )
            serializer = self.get_serializer(queryset, many=True)
            total = len(serializer.data)
            page_num = 1
            page_size = total or 0
            total_pages = 0 if total == 0 else 1

            return self.build_response(
                success=True,
                data=serializer.data,
                meta={
                    "total": total,
                    "page": page_num,
                    "page_size": page_size,
                    "total_pages": total_pages,
                },
            )
        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        # Handle other exceptions
        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return self.build_response(
                success=True,
                message="Created successfully.",
                data=serializer.data,
                status=status.HTTP_201_CREATED,
            )
        # Handle validation errors specifically
        except ValidationError as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(e.detail),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        # Handle other exceptions
        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )


#####################
#    CREATE VIEW    #
#####################


class CustomCreateAPIView(CreateAPIView, CustomResponse):
    request: AuthenticatedRequest

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return self.build_response(
                success=True,
                message="Created successfully.",
                data=serializer.data,
                status=status.HTTP_201_CREATED,
            )
        # Handle validation errors specifically
        except ValidationError as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(e.detail),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        # Handle other exceptions
        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )


#####################
#     LIST VIEW     #
#####################
class CustomListAPIView(ListAPIView, CustomResponse):
    request: AuthenticatedRequest

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                # PageNumberPagination uses .page; LimitOffsetPagination uses .count
                if hasattr(self.paginator, "page"):
                    total = self.paginator.page.paginator.count
                    if total:
                        page_num = self.paginator.page.number
                        page_size = self.paginator.page.paginator.per_page
                        total_pages = self.paginator.page.paginator.num_pages
                    else:
                        page_num = 0
                        page_size = 0
                        total_pages = 0
                else:
                    # LimitOffsetPagination
                    total = self.paginator.count
                    limit = self.paginator.limit or total or 0
                    offset = self.paginator.offset or 0
                    page_size = limit
                    page_num = (offset // limit + 1) if limit else 1
                    total_pages = ((total + limit - 1) // limit) if limit else (1 if total else 0)
                    if not total:
                        page_num = 0
                        page_size = 0
                        total_pages = 0

                return self.build_response(
                    success=True,
                    data=serializer.data,
                    meta={
                        "total": total,
                        "page": page_num,
                        "page_size": page_size,
                        "total_pages": total_pages,
                    },
                )
            serializer = self.get_serializer(queryset, many=True)
            total = len(serializer.data)
            page_num = 0 if total == 0 else 1
            page_size = total or 0
            total_pages = 0 if total == 0 else 1

            return self.build_response(
                success=True,
                data=serializer.data,
                meta={
                    "total": total,
                    "page": page_num,
                    "page_size": page_size,
                    "total_pages": total_pages,
                },
            )
        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        # Handle other exceptions
        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )


#######################
#    RETRIEVE VIEW    #
#######################


class CustomRetrieveAPIView(RetrieveAPIView, CustomResponse):
    request: AuthenticatedRequest

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return self.build_response(success=True, message="Retrieved successfully.", data=serializer.data)
        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )


#######################
#     UPDATE VIEW     #
#######################


class CustomUpdateAPIView(UpdateAPIView, CustomResponse):
    request: AuthenticatedRequest

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop("partial", False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)

            serializer.is_valid(raise_exception=True)

            self.perform_update(serializer)
            return self.build_response(success=True, message="Updated successfully.", data=serializer.data)

        # Handle validation errors specifically
        except ValidationError as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(e.detail),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        # Handle other exceptions
        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )


############################################
#          RETRIEVE & UPDATE VIEW          #
############################################


class CustomRetrieveUpdateAPIView(RetrieveUpdateAPIView, CustomResponse):
    request: AuthenticatedRequest

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return self.build_response(success=True, message="Retrieved successfully.", data=serializer.data)

        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )

        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop("partial", False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)

            serializer.is_valid(raise_exception=True)

            self.perform_update(serializer)
            return self.build_response(success=True, message="Updated successfully.", data=serializer.data)

        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Handle validation errors specifically
        except ValidationError as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(e.detail),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        # Handle other exceptions
        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )


############################################
#      RETRIEVE, UPDATE & DESTROY VIEW     #
############################################


class CustomRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView, CustomResponse):
    request: AuthenticatedRequest

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return self.build_response(success=True, message="Retrieved successfully.", data=serializer.data)

        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )

        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop("partial", False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)

            serializer.is_valid(raise_exception=True)

            self.perform_update(serializer)
            return self.build_response(success=True, message="Updated successfully.", data=serializer.data)

        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Handle validation errors specifically
        except ValidationError as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(e.detail),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        # Handle other exceptions
        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return self.build_response(success=True, message="Deleted successfully.", data={"deleted": True})

        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except PermissionDenied:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.FORBIDDEN,
                    "message": GlobalAPIMessageCodes.FORBIDDEN.label,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except (ParseError, APIException) as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": getattr(e, "detail", str(e)),
                },
                status=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            )
        # Handle other exceptions
        except Exception:
            logger.exception(
                "Unhandled Exception",
                request_path=request.path,
                request_data=request.data,
            )
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.INTERNAL_ERROR,
                    "message": GlobalAPIMessageCodes.INTERNAL_ERROR.label,
                    "details": None,
                },
            )

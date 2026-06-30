from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from apps.core.models import UserRoles
from apps.school.models import School
from shared.helpers.rbac import (
    get_user_roles,
    get_user_permissions,
)
from shared.mixins import CustomResponse


class StripTrailingSlashMiddleware:
    """
    Strips a trailing slash from the request path before routing so that
    both /api/v1/auth/login and /api/v1/auth/login/ resolve correctly.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path != "/" and request.path.endswith("/"):
            request.path_info = request.path_info.rstrip("/")
        return self.get_response(request)






class SchoolMiddleware:

    def __init__(self, get_response):


        self.get_response = get_response


        self.exempt_paths = (
            "/health/",
            "/admin/",
            "/user/admin/send-otp",
            "/user/admin/verify-otp",
            "/user/send-otp",
            "/user/verify-otp",

            "/fee/phonepe/webhook",

            "/backoffice/organizations",
            "/backoffice/schools",
            "/backoffice/branches",
            "/backoffice/user/list",
            "/backoffice/super-admin",
            "/backoffice/leads",
            "/backoffice/rbac",
            "/backoffice/modules",
            "/backoffice/permissions",
            "/backoffice/roles",
            "/backoffice/user-roles/assign",
            "/backoffice/create/super-admin",
            "/backoffice/client-info"
        )

    def __call__(self, request):
        print("=" * 80)
        print("SchoolMiddleware Called")
        print("Path :", request.path)
        print("Method :", request.method)
        print("Headers :", dict(request.headers))
        print("Request Path :", request.path)

        request.school = None
        request.school_id = None

        if any(
            request.path.startswith(path)
            for path in self.exempt_paths
        ):

            print("Exempted Path")
            print("=" * 80)

            return self.get_response(request)

        school_id = request.headers.get(
            "X-School-Id"
        )

        print("X-School-Id Header :", school_id)

        if not school_id:
            return JsonResponse(
                {
                    "success": False,
                    "data": {},
                    "description": "X-School-Id header is required.",
                    "status_code": 400,
                },
                status=400,

            )



        print("Fetching School...")

        school = School.objects.filter(
            id=school_id,
        ).first()

        print("School Object :", school)

        if school is None:
            return JsonResponse(
                {
                    "success": False,
                    "data": {},
                    "description": "Invalid school.",
                    "status_code": 404,
                },
                status=404,

            )



        request.school = school
        request.school_id = school.id

        print("Request School :", request.school)
        print("Request School ID :", request.school_id)

        print("=" * 80)

        response = self.get_response(request)

        return response




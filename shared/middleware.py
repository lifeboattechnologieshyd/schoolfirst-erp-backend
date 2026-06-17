from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse
from rest_framework.exceptions import PermissionDenied

from apps.core.models import UserRoles
from apps.school.models import School
from shared.helpers.rbac import (
    get_user_roles,
    get_user_permissions,
)

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

            "/admin/",

            "/health/",

            "/user/admin/send-otp",

            "/user/admin/verify-otp",

            "/user/superadmin/send-otp",

            "/user/superadmin/verify-otp",

            "/user/parent/send-otp",

            "/user/parent/verify-otp",

            "/user/student/send-otp",

            "/user/student/verify-otp",

            "/user/teacher/send-otp",

            "/user/teacher/verify-otp",

            "/swagger/",

            "/redoc/",

            "/openapi/",

        )

    def __call__(self, request):

        print("=" * 80)

        print("SchoolMiddleware Called")

        print("Path :", request.path)

        request.school = None

        request.school_id = None

        # Skip school validation for exempted APIs

        if any(

            request.path.startswith(path)

            for path in self.exempt_paths

        ):

            print("Exempted Path")

            return self.get_response(request)

        school_id = request.headers.get(

            "X-School-Id"

        )

        print("X-School-Id :", school_id)

        if not school_id:

            return JsonResponse(

                {

                    "success": False,

                    "description": "X-School-Id header is required.",

                },

                status=400,

            )

        school = School.objects.filter(

            id=school_id,

        ).first()

        if school is None:

            return JsonResponse(

                {

                    "success": False,

                    "description": "Invalid school.",

                },

                status=404,

            )

        request.school = school

        request.school_id = school.id

        print("School :", school.name)

        print("School ID :", school.id)

        print("=" * 80)

        return self.get_response(request)
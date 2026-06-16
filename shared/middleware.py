from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
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

    def __call__(self, request):

        print("=" * 80)
        print("SchoolMiddleware Called")

        request.current_school = None
        request.roles = []
        request.permissions = []

        print("User :", request.user)
        print("Is Authenticated :", request.user.is_authenticated)

        if request.user.is_authenticated:

            school_id = request.headers.get("X-School-Id")

            print("Header X-School-Id :", school_id)

            if school_id:

                request.current_school = School.objects.filter(
                    id=school_id,
                ).first()

                print("Current School :", request.current_school)

            request.roles = get_user_roles(
                user=request.user,
                school_id=school_id,
            )

            print("Roles :", request.roles)

            request.permissions = get_user_permissions(
                user=request.user,
                school_id=school_id,
            )

            print("Permissions :", request.permissions)

        else:

            print("User is Anonymous")

        print("=" * 80)

        response = self.get_response(request)

        return response
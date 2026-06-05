from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
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







class RBACMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        request.roles = []
        request.permissions = []

        if request.user.is_authenticated:

            school_id = request.headers.get(
                "X-School-Id"
            )

            request.roles = get_user_roles(
                user=request.user,
                school_id=school_id,
            )

            request.permissions = get_user_permissions(
                user=request.user,
                school_id=school_id,
            )

        response = self.get_response(request)

        return response
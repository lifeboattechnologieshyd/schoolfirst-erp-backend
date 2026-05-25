from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


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

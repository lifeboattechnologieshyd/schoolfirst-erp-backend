from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str:
    """
    Return the client's IP address from the request.

    Uses REMOTE_ADDR only. X-Forwarded-For is intentionally ignored because
    it is client-controlled and can be spoofed. If the application is deployed
    behind a trusted reverse proxy that sets a verified header, configure
    Django's TRUSTED_PROXIES setting and update this helper accordingly.
    """
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"  # noqa: S104

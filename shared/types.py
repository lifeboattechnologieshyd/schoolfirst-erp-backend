from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.request import Request

if TYPE_CHECKING:
    from apps.core.models.user import UserMaster


class AuthenticatedRequest(Request):
    """DRF Request subclass used only for type-checking.

    Narrows ``request.user`` to the project's custom user model so that
    all views inheriting from the shared custom generics get accurate
    type information without per-view annotations.
    """

    user: UserMaster  # type: ignore[override]

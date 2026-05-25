"""
Base OAuth Provider interface.
All OAuth providers (Google, Facebook, Apple, etc.) should implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class OAuthUserInfo:
    """Standardized user information from OAuth providers."""

    provider_user_id: str  # Unique ID from the provider (e.g., 'sub' from Google)
    email: str
    email_verified: bool
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    picture: str | None = None
    raw_data: dict | None = None  # Full provider response for storage


class OAuthProvider(ABC):
    """Abstract base class for OAuth providers with minimal shared behaviour.

    Responsibilities:
    - Store the raw authorization payload received from client (auth code, state, etc.)
    - Provide a consistent contract for token exchange & user info retrieval
    """

    TIMEOUT_SECONDS = 10

    def __init__(self) -> None:  # pragma: no cover - trivial
        self.authorization_payload: dict[str, Any] | None = None

    # ----- Optional lifecycle hooks -------------------------------------------------
    def set_authorization_payload(self, payload: dict[str, Any]) -> None:
        """Attach the full provider authorization payload.

        Providers needing extra fields (ex: Apple 'id_token', Facebook 'state', etc.)
        can access them via self.authorization_payload.
        """
        self.authorization_payload = payload or {}

    # ----- Abstract contract --------------------------------------------------------
    @abstractmethod
    def exchange_code_for_tokens(self, auth_code: str, redirect_uri: str | None) -> dict:
        """Exchange authorization code for provider tokens.

        Return structure MUST include at minimum either an 'access_token' or an 'error'.
        Implementations MAY enrich with fields like: refresh_token, id_token,
        expires_in, provider_user_id, etc.
        """

    @abstractmethod
    def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Return normalized user info raising ValueError on failure."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider machine name (e.g. 'google')."""

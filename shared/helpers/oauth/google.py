"""
Google OAuth Provider implementation.
Handles all Google-specific OAuth logic.
"""

import jwt
import requests
import structlog
from django.conf import settings

from .base import OAuthProvider, OAuthUserInfo

logger = structlog.get_logger("default")


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth 2.0 provider implementation."""

    def get_provider_name(self) -> str:
        return "google"

    def exchange_code_for_tokens(self, auth_code: str, redirect_uri: str | None = None) -> dict:
        """
        Exchange Google authorization code for tokens.

        Args:
            auth_code: Authorization code from Google
            redirect_uri: Redirect URI (uses settings if not provided)

        Returns:
            Dict containing access_token, refresh_token, provider_user_id, id_token
        """
        token_url = settings.GOOGLE_TOKEN_URL
        redirect_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI

        data = {
            "code": auth_code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            response = requests.post(token_url, data=data, timeout=self.TIMEOUT_SECONDS)
            response.raise_for_status()
            tokens = response.json()

            # Decode ID token to extract 'sub' (Google user ID)
            id_token = tokens.get("id_token")
            if id_token:
                try:
                    # No signature verification needed - came directly from Google
                    decoded = jwt.decode(id_token, options={"verify_signature": False})
                    tokens["provider_user_id"] = decoded.get("sub")
                    logger.debug("Google token exchange successful", provider_user_id=tokens.get("provider_user_id"))
                except jwt.InvalidTokenError:
                    logger.exception("Failed to decode Google id_token")
                    tokens["provider_user_id"] = None

            return tokens

        except requests.exceptions.HTTPError:
            logger.exception("HTTP error during Google token exchange")
            error_body = response.json() if response.content else {}
            return {"error": error_body.get("error", "token_exchange_failed")}
        except requests.exceptions.Timeout:
            logger.exception("Timeout during Google token exchange")
            return {"error": "token_exchange_timeout"}
        except Exception:
            logger.exception("Unexpected error during Google token exchange")
            return {"error": "token_exchange_failed"}

    def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """
        Fetch user information from Google using access token.

        Args:
            access_token: Google access token

        Returns:
            OAuthUserInfo with standardized user data

        Raises:
            ValueError: If user info fetch fails
        """
        url = settings.GOOGLE_USERINFO_URL
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = requests.get(url, headers=headers, timeout=self.TIMEOUT_SECONDS)
            response.raise_for_status()
            user_data = response.json()

            return OAuthUserInfo(
                provider_user_id=user_data.get("id"),
                email=user_data.get("email"),
                email_verified=user_data.get("verified_email", False),
                first_name=user_data.get("given_name"),
                last_name=user_data.get("family_name"),
                full_name=user_data.get("name"),
                picture=user_data.get("picture"),
                raw_data=user_data,
            )

        except requests.exceptions.HTTPError:
            logger.exception("HTTP error during Google user info fetch")
            error_body = response.json() if response.content else {}
            raise ValueError(f"Failed to fetch user info: {error_body.get('error', 'userinfo_fetch_failed')}")  # noqa: B904
        except requests.exceptions.Timeout:
            logger.exception("Timeout during Google user info fetch")
            raise ValueError("User info fetch timeout")  # noqa: B904
        except Exception:
            logger.exception("Unexpected error during Google user info fetch")
            raise ValueError("Failed to fetch user info")  # noqa: B904

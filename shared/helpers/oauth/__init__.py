"""
OAuth provider integrations.
Each provider implements the base OAuth interface.
"""

from .base import OAuthProvider, OAuthUserInfo
from .google import GoogleOAuthProvider

__all__ = ["OAuthProvider", "OAuthUserInfo", "GoogleOAuthProvider"]

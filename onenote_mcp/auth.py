"""Device Code Flow and encrypted MSAL token-cache handling."""

from __future__ import annotations

import logging
from typing import Any

import msal
from msal_extensions import PersistedTokenCache, build_encrypted_persistence

from .config import Settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://graph.microsoft.com/Notes.ReadWrite",
    "https://graph.microsoft.com/User.Read",
]


class AuthenticationRequired(RuntimeError):
    """Raised when the user must run the Device Code Flow."""


class AuthenticationError(RuntimeError):
    """Raised when MSAL cannot complete a requested authentication operation."""


class AuthManager:
    """Owns the public-client application and never exposes access tokens."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: msal.SerializableTokenCache | PersistedTokenCache | None = None
        self._app: msal.PublicClientApplication | None = None
        self._flow: dict[str, Any] | None = None
        self._persistent_cache_available = False

    @property
    def cache_status(self) -> str:
        if not self._settings.cache_tokens:
            return "disabled"
        return "encrypted" if self._persistent_cache_available else "session_only"

    def _get_app(self) -> msal.PublicClientApplication:
        if not self._settings.client_id:
            raise AuthenticationError("AZURE_CLIENT_ID environment variable is not set")
        if self._app is None:
            self._cache = self._build_cache()
            self._app = msal.PublicClientApplication(
                self._settings.client_id,
                authority=self._settings.authority,
                token_cache=self._cache,
            )
        return self._app

    def _build_cache(self) -> msal.SerializableTokenCache | PersistedTokenCache:
        if not self._settings.cache_tokens:
            return msal.SerializableTokenCache()
        try:
            self._settings.cache_path.parent.mkdir(parents=True, exist_ok=True)
            persistence = build_encrypted_persistence(str(self._settings.cache_path))
            self._persistent_cache_available = True
            return PersistedTokenCache(persistence)
        except Exception:
            self._persistent_cache_available = False
            logger.warning("Encrypted token persistence is unavailable; using session-only tokens")
            return msal.SerializableTokenCache()

    def start_device_flow(self) -> dict[str, Any]:
        flow = self._get_app().initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow or "verification_uri" not in flow:
            raise AuthenticationError("Unable to initiate Device Code Flow")
        self._flow = flow
        return {
            "status": "authentication_required",
            "instructions": "Open verification_uri, enter user_code, then call complete_authentication.",
            "verification_uri": flow["verification_uri"],
            "user_code": flow["user_code"],
            "expires_in": flow.get("expires_in", 900),
        }

    def complete_device_flow(self) -> None:
        if self._flow is None:
            raise AuthenticationError("No Device Code Flow is in progress. Call start_authentication first.")
        try:
            result = self._get_app().acquire_token_by_device_flow(self._flow)
        finally:
            self._flow = None
        if "access_token" not in result:
            raise AuthenticationError("Device Code Flow was not completed successfully")

    def get_access_token(self) -> str:
        app = self._get_app()
        accounts = app.get_accounts()
        if not accounts:
            raise AuthenticationRequired("No cached session. Call start_authentication first.")
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        token = result.get("access_token") if result else None
        if not token:
            raise AuthenticationRequired("Authentication has expired. Call start_authentication again.")
        return token

    def has_valid_session(self) -> bool:
        try:
            self.get_access_token()
        except (AuthenticationRequired, AuthenticationError):
            return False
        return True

    def clear_cache(self) -> None:
        self._flow = None
        self._cache = None
        self._app = None
        if self._persistent_cache_available and self._settings.cache_path.exists():
            self._settings.cache_path.unlink()
        self._persistent_cache_available = False

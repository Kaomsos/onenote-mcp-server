"""Small, testable Microsoft Graph HTTP client."""

from __future__ import annotations

from typing import Any

import httpx

from .auth import AuthManager
from .config import Settings


class GraphRequestError(RuntimeError):
    """A sanitized Graph error suitable for MCP responses."""

    def __init__(self, status_code: int | None, correlation_id: str | None = None) -> None:
        self.status_code = status_code
        self.correlation_id = correlation_id
        super().__init__(self.code)

    @property
    def code(self) -> str:
        if self.status_code == 401:
            return "authentication_failed"
        if self.status_code == 403:
            return "forbidden"
        if self.status_code == 409:
            return "conflict"
        if self.status_code == 429:
            return "rate_limited"
        if self.status_code and self.status_code >= 500:
            return "graph_service_error"
        if self.status_code is None:
            return "network_error"
        return "graph_request_failed"


class GraphClient:
    def __init__(self, settings: Settings, auth: AuthManager, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._settings = settings
        self._auth = auth
        self._transport = transport

    async def request_json(
        self,
        method: str,
        endpoint: str,
        *,
        json_body: Any | None = None,
        content: str | None = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        response = await self._request(method, endpoint, json_body=json_body, content=content, content_type=content_type)
        return response.json() if response.content else {}

    async def request_text(self, method: str, endpoint: str) -> str:
        response = await self._request(method, endpoint, content_type="text/html")
        return response.text

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json_body: Any | None = None,
        content: str | None = None,
        content_type: str,
    ) -> httpx.Response:
        token = self._auth.get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": content_type}
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=15.0) as client:
                response = await client.request(
                    method,
                    f"{self._settings.graph_base_url}{endpoint}",
                    headers=headers,
                    json=json_body,
                    content=content,
                )
        except httpx.HTTPError as exc:
            raise GraphRequestError(None) from exc
        if response.status_code >= 400:
            raise GraphRequestError(
                response.status_code,
                response.headers.get("request-id") or response.headers.get("x-correlationid"),
            )
        return response

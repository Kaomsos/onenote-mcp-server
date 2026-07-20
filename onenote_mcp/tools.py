"""OneNote operations and FastMCP tool registration."""

from __future__ import annotations

import json
from html import escape
from typing import Any
from urllib.parse import quote

from fastmcp import FastMCP

from .auth import AuthManager, AuthenticationError, AuthenticationRequired
from .config import Settings
from .graph import GraphClient, GraphRequestError

NOTEBOOK_FORBIDDEN = set("?*/:<>|'\"")
SECTION_FORBIDDEN = set("?*/:<>|&#'%~")


class InputValidationError(ValueError):
    """Raised for invalid tool input before any Graph request is sent."""


class WriteDisabledError(PermissionError):
    """Raised when a mutation tool is not explicitly enabled."""


def _validated_name(name: str, *, kind: str) -> str:
    normalized = name.strip() if isinstance(name, str) else ""
    if not normalized:
        raise InputValidationError(f"{kind} name must not be empty")
    limit = 128 if kind == "notebook" else 50
    forbidden = NOTEBOOK_FORBIDDEN if kind == "notebook" else SECTION_FORBIDDEN
    if len(normalized) > limit:
        raise InputValidationError(f"{kind} name must not exceed {limit} characters")
    if any(character in forbidden for character in normalized):
        raise InputValidationError(f"{kind} name contains unsupported characters")
    return normalized


def _resource_id(resource_id: str, *, kind: str) -> str:
    if not isinstance(resource_id, str) or not resource_id.strip():
        raise InputValidationError(f"{kind} ID must not be empty")
    return quote(resource_id.strip(), safe="")


def _error_result(error: Exception) -> str:
    if isinstance(error, InputValidationError):
        result: dict[str, Any] = {"status": "error", "code": "invalid_input", "message": str(error)}
    elif isinstance(error, WriteDisabledError):
        result = {"status": "error", "code": "writes_disabled", "message": "Set ONENOTE_ENABLE_WRITES=true to enable write tools."}
    elif isinstance(error, AuthenticationRequired):
        result = {"status": "error", "code": "authentication_required", "message": "Call start_authentication first."}
    elif isinstance(error, AuthenticationError):
        result = {"status": "error", "code": "authentication_error", "message": str(error)}
    elif isinstance(error, GraphRequestError):
        result = {"status": "error", "code": error.code, "message": "Microsoft Graph request failed."}
        if error.correlation_id:
            result["correlation_id"] = error.correlation_id
    else:
        result = {"status": "error", "code": "internal_error", "message": "Unexpected server error."}
    return json.dumps(result, indent=2)


class OneNoteTools:
    """Business operations separated from MCP transport for unit testing."""

    def __init__(self, settings: Settings, auth: AuthManager, graph: GraphClient) -> None:
        self._settings = settings
        self._auth = auth
        self._graph = graph

    def _require_writes(self) -> None:
        if not self._settings.writes_enabled:
            raise WriteDisabledError

    async def list_notebooks(self) -> str:
        try:
            notebooks = await self._graph.request_json("GET", "/me/onenote/notebooks")
            result = [
                {
                    "id": item.get("id"),
                    "name": item.get("displayName"),
                    "created": item.get("createdDateTime"),
                    "modified": item.get("lastModifiedDateTime"),
                }
                for item in notebooks.get("value", [])
            ]
            return json.dumps(result, indent=2)
        except Exception as error:
            return _error_result(error)

    async def list_sections(self, notebook_id: str) -> str:
        try:
            notebook = _resource_id(notebook_id, kind="notebook")
            sections = await self._graph.request_json("GET", f"/me/onenote/notebooks/{notebook}/sections")
            result = [
                {
                    "id": item.get("id"),
                    "name": item.get("displayName"),
                    "created": item.get("createdDateTime"),
                    "modified": item.get("lastModifiedDateTime"),
                }
                for item in sections.get("value", [])
            ]
            return json.dumps(result, indent=2)
        except Exception as error:
            return _error_result(error)

    async def list_pages(self, section_id: str) -> str:
        try:
            section = _resource_id(section_id, kind="section")
            pages = await self._graph.request_json("GET", f"/me/onenote/sections/{section}/pages")
            result = [
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "created": item.get("createdDateTime"),
                    "modified": item.get("lastModifiedDateTime"),
                    "content_url": item.get("contentUrl"),
                }
                for item in pages.get("value", [])
            ]
            return json.dumps(result, indent=2)
        except Exception as error:
            return _error_result(error)

    async def get_page_content(self, page_id: str) -> str:
        try:
            page = _resource_id(page_id, kind="page")
            return await self._graph.request_text("GET", f"/me/onenote/pages/{page}/content")
        except Exception as error:
            return _error_result(error)

    async def create_notebook(self, name: str) -> str:
        try:
            self._require_writes()
            display_name = _validated_name(name, kind="notebook")
            notebook = await self._graph.request_json(
                "POST", "/me/onenote/notebooks", json_body={"displayName": display_name}
            )
            return json.dumps(
                {
                    "status": "success",
                    "message": f"Notebook '{display_name}' created successfully",
                    "notebook": {
                        "id": notebook.get("id"),
                        "name": notebook.get("displayName"),
                        "created": notebook.get("createdDateTime"),
                    },
                },
                indent=2,
            )
        except Exception as error:
            return _error_result(error)

    async def create_section(self, notebook_id: str, name: str) -> str:
        try:
            self._require_writes()
            notebook = _resource_id(notebook_id, kind="notebook")
            display_name = _validated_name(name, kind="section")
            section = await self._graph.request_json(
                "POST",
                f"/me/onenote/notebooks/{notebook}/sections",
                json_body={"displayName": display_name},
            )
            return json.dumps(
                {
                    "status": "success",
                    "message": f"Section '{display_name}' created successfully",
                    "section": {
                        "id": section.get("id"),
                        "name": section.get("displayName"),
                        "created": section.get("createdDateTime"),
                    },
                },
                indent=2,
            )
        except Exception as error:
            return _error_result(error)

    async def create_page(self, section_id: str, title: str, content_html: str | None = None) -> str:
        try:
            self._require_writes()
            section = _resource_id(section_id, kind="section")
            page_title = _validated_name(title, kind="notebook")
            body = content_html or "<p>Page created by OneNote MCP Server</p>"
            page_html = body if body.lstrip().lower().startswith("<html") else (
                "<!DOCTYPE html><html><head><title>"
                f"{escape(page_title)}"
                "</title></head><body><h1>"
                f"{escape(page_title)}"
                f"</h1>{body}</body></html>"
            )
            page = await self._graph.request_json(
                "POST",
                f"/me/onenote/sections/{section}/pages",
                content=page_html,
                content_type="application/xhtml+xml",
            )
            return json.dumps(
                {
                    "status": "success",
                    "message": f"Page '{page_title}' created successfully",
                    "page": {
                        "id": page.get("id"),
                        "title": page.get("title"),
                        "created": page.get("createdDateTime"),
                        "content_url": page.get("contentUrl"),
                    },
                },
                indent=2,
            )
        except Exception as error:
            return _error_result(error)

    async def update_page_content(self, page_id: str, content_html: str, target_element: str = "body") -> str:
        try:
            self._require_writes()
            page = _resource_id(page_id, kind="page")
            await self._graph.request_json(
                "PATCH",
                f"/me/onenote/pages/{page}/content",
                json_body=[{"target": target_element, "action": "append", "content": content_html}],
            )
            return json.dumps({"status": "success", "message": "Page content updated successfully", "page_id": page_id}, indent=2)
        except Exception as error:
            return _error_result(error)


def register_tools(mcp: FastMCP, service: OneNoteTools, auth: AuthManager) -> None:
    """Register stable MCP tool names against the service implementation."""

    @mcp.tool()
    async def start_authentication() -> str:
        try:
            return json.dumps(auth.start_device_flow(), indent=2)
        except Exception as error:
            return _error_result(error)

    @mcp.tool()
    async def complete_authentication() -> str:
        try:
            auth.complete_device_flow()
            return json.dumps({"status": "success", "message": "Authentication completed successfully."}, indent=2)
        except Exception as error:
            return _error_result(error)

    @mcp.tool()
    async def check_authentication() -> str:
        return json.dumps(
            {"status": "authenticated" if auth.has_valid_session() else "not_authenticated", "token_caching": auth.cache_status},
            indent=2,
        )

    @mcp.tool()
    async def clear_token_cache() -> str:
        try:
            auth.clear_cache()
            return json.dumps({"status": "success", "message": "Token cache cleared. Re-authentication is required."}, indent=2)
        except Exception as error:
            return _error_result(error)

    mcp.tool()(service.list_notebooks)
    mcp.tool()(service.list_sections)
    mcp.tool()(service.list_pages)
    mcp.tool()(service.get_page_content)
    mcp.tool()(service.create_notebook)
    mcp.tool()(service.create_section)
    mcp.tool()(service.create_page)
    mcp.tool()(service.update_page_content)

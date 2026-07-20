import json

import pytest

from onenote_mcp.config import Settings
from onenote_mcp.tools import OneNoteTools


class StubAuth:
    def get_access_token(self) -> str:
        return "test-token"


class RecordingGraph:
    def __init__(self) -> None:
        self.calls = []

    async def request_json(self, method, endpoint, **kwargs):
        self.calls.append((method, endpoint, kwargs))
        if endpoint.endswith("/notebooks"):
            return {"id": "notebook-id", "displayName": "Test Notebook", "createdDateTime": "2026-01-01T00:00:00Z"}
        if endpoint.endswith("/sections"):
            return {"id": "section-id", "displayName": "Test Section", "createdDateTime": "2026-01-01T00:00:00Z"}
        return {"id": "page-id", "title": "Test Page", "createdDateTime": "2026-01-01T00:00:00Z"}

    async def request_text(self, method, endpoint):
        self.calls.append((method, endpoint, {}))
        return "<html><body>test</body></html>"


def settings(*, writes_enabled: bool) -> Settings:
    return Settings(client_id="public-client-id", cache_tokens=False, writes_enabled=writes_enabled, cache_path=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_notebook_is_disabled_by_default():
    graph = RecordingGraph()
    tools = OneNoteTools(settings(writes_enabled=False), StubAuth(), graph)  # type: ignore[arg-type]

    result = json.loads(await tools.create_notebook("Test Notebook"))

    assert result["code"] == "writes_disabled"
    assert graph.calls == []


@pytest.mark.asyncio
async def test_create_notebook_posts_official_payload():
    graph = RecordingGraph()
    tools = OneNoteTools(settings(writes_enabled=True), StubAuth(), graph)  # type: ignore[arg-type]

    result = json.loads(await tools.create_notebook("  Test Notebook  "))

    assert result["status"] == "success"
    assert result["notebook"]["id"] == "notebook-id"
    assert graph.calls == [("POST", "/me/onenote/notebooks", {"json_body": {"displayName": "Test Notebook"}})]


@pytest.mark.asyncio
async def test_create_section_encodes_resource_id_and_validates_name():
    graph = RecordingGraph()
    tools = OneNoteTools(settings(writes_enabled=True), StubAuth(), graph)  # type: ignore[arg-type]

    result = json.loads(await tools.create_section("notebook/id", "Roadmap"))

    assert result["status"] == "success"
    assert graph.calls == [
        ("POST", "/me/onenote/notebooks/notebook%2Fid/sections", {"json_body": {"displayName": "Roadmap"}})
    ]

    invalid = json.loads(await tools.create_section("notebook-id", "bad/name"))
    assert invalid["code"] == "invalid_input"
    assert len(graph.calls) == 1


@pytest.mark.asyncio
async def test_create_page_uses_xhtml_and_escapes_title():
    graph = RecordingGraph()
    tools = OneNoteTools(settings(writes_enabled=True), StubAuth(), graph)  # type: ignore[arg-type]

    await tools.create_page("section-id", "A & B", "<p>body</p>")

    method, endpoint, kwargs = graph.calls[0]
    assert (method, endpoint) == ("POST", "/me/onenote/sections/section-id/pages")
    assert kwargs["content_type"] == "application/xhtml+xml"
    assert "A &amp; B" in kwargs["content"]

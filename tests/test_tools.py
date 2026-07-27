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


def settings(*, writes_enabled: bool, deletes_enabled: bool = False) -> Settings:
    return Settings(
        client_id="public-client-id",
        cache_tokens=False,
        writes_enabled=writes_enabled,
        cache_path=None,  # type: ignore[arg-type]
        deletes_enabled=deletes_enabled,
    )


class MetadataGraph:
    def __init__(self, *, page_title: str = "Test Page") -> None:
        self.calls = []
        self.page_title = page_title

    async def request_json(self, method, endpoint, **kwargs):
        self.calls.append((method, endpoint, kwargs))
        if "/notebooks/" in endpoint:
            return {
                "id": "notebook-id",
                "displayName": "Test Notebook",
                "createdDateTime": "2026-01-01T00:00:00Z",
                "lastModifiedDateTime": "2026-01-02T00:00:00Z",
                "sectionsUrl": "https://example.invalid/sections",
            }
        if "/sections/" in endpoint:
            return {
                "id": "section-id",
                "displayName": "Test Section",
                "createdDateTime": "2026-01-01T00:00:00Z",
                "lastModifiedDateTime": "2026-01-02T00:00:00Z",
                "pagesUrl": "https://example.invalid/pages",
            }
        if method == "GET":
            return {
                "id": "page-id",
                "title": self.page_title,
                "createdDateTime": "2026-01-01T00:00:00Z",
                "lastModifiedDateTime": "2026-01-02T00:00:00Z",
                "contentUrl": "https://example.invalid/content",
            }
        return {}


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


@pytest.mark.asyncio
async def test_get_tools_encode_ids_and_map_metadata():
    graph = MetadataGraph()
    tools = OneNoteTools(settings(writes_enabled=False), StubAuth(), graph)  # type: ignore[arg-type]

    notebook = json.loads(await tools.get_notebook("notebook/id"))
    section = json.loads(await tools.get_section("section/id"))
    page = json.loads(await tools.get_page_metadata("page/id"))

    assert notebook == {
        "id": "notebook-id",
        "name": "Test Notebook",
        "created": "2026-01-01T00:00:00Z",
        "modified": "2026-01-02T00:00:00Z",
        "sections_url": "https://example.invalid/sections",
    }
    assert section["name"] == "Test Section"
    assert section["pages_url"] == "https://example.invalid/pages"
    assert page["title"] == "Test Page"
    assert page["content_url"] == "https://example.invalid/content"
    assert [call[:2] for call in graph.calls] == [
        ("GET", "/me/onenote/notebooks/notebook%2Fid"),
        ("GET", "/me/onenote/sections/section%2Fid"),
        ("GET", "/me/onenote/pages/page%2Fid"),
    ]


@pytest.mark.asyncio
async def test_delete_page_requires_writes_before_any_graph_request():
    graph = MetadataGraph()
    tools = OneNoteTools(settings(writes_enabled=False, deletes_enabled=True), StubAuth(), graph)  # type: ignore[arg-type]

    result = json.loads(await tools.delete_page("page-id", "Test Page"))

    assert result["code"] == "writes_disabled"
    assert graph.calls == []


@pytest.mark.asyncio
async def test_delete_page_requires_separate_delete_switch():
    graph = MetadataGraph()
    tools = OneNoteTools(settings(writes_enabled=True), StubAuth(), graph)  # type: ignore[arg-type]

    result = json.loads(await tools.delete_page("page-id", "Test Page"))

    assert result["code"] == "deletes_disabled"
    assert graph.calls == []


@pytest.mark.asyncio
async def test_delete_page_rejects_title_mismatch_without_delete():
    graph = MetadataGraph(page_title="Current Title")
    tools = OneNoteTools(
        settings(writes_enabled=True, deletes_enabled=True), StubAuth(), graph  # type: ignore[arg-type]
    )

    result = json.loads(await tools.delete_page("page/id", "Expected Title"))

    assert result["code"] == "confirmation_mismatch"
    assert [call[:2] for call in graph.calls] == [("GET", "/me/onenote/pages/page%2Fid")]


@pytest.mark.asyncio
async def test_delete_page_checks_title_then_deletes_once():
    graph = MetadataGraph(page_title="Expected Title")
    tools = OneNoteTools(
        settings(writes_enabled=True, deletes_enabled=True), StubAuth(), graph  # type: ignore[arg-type]
    )

    result = json.loads(await tools.delete_page("page/id", "Expected Title"))

    assert result == {"status": "success", "message": "Page deleted successfully."}
    assert [call[:2] for call in graph.calls] == [
        ("GET", "/me/onenote/pages/page%2Fid"),
        ("DELETE", "/me/onenote/pages/page%2Fid"),
    ]

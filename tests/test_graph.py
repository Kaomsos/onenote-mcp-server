import json

import httpx
import pytest

from onenote_mcp.config import Settings
from onenote_mcp.graph import GraphClient, GraphRequestError
from onenote_mcp.tools import OneNoteTools


class StubAuth:
    def get_access_token(self) -> str:
        return "test-token"


def settings() -> Settings:
    return Settings(client_id="public-client-id", cache_tokens=False, writes_enabled=True, cache_path=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_graph_client_sends_bearer_and_returns_json():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.url.path == "/v1.0/me/onenote/notebooks"
        assert json.loads(request.content) == {"displayName": "Test Notebook"}
        return httpx.Response(201, json={"id": "new-id"})

    graph = GraphClient(settings(), StubAuth(), httpx.MockTransport(handler))  # type: ignore[arg-type]

    response = await graph.request_json("POST", "/me/onenote/notebooks", json_body={"displayName": "Test Notebook"})

    assert response == {"id": "new-id"}


@pytest.mark.asyncio
async def test_graph_errors_never_expose_response_body():
    graph = GraphClient(
        settings(),
        StubAuth(),  # type: ignore[arg-type]
        httpx.MockTransport(lambda request: httpx.Response(409, text="secret Graph response", headers={"request-id": "request-123"})),
    )
    tools = OneNoteTools(settings(), StubAuth(), graph)  # type: ignore[arg-type]

    result = json.loads(await tools.create_notebook("Test Notebook"))

    assert result == {
        "status": "error",
        "code": "conflict",
        "message": "Microsoft Graph request failed.",
        "correlation_id": "request-123",
    }
    assert "secret Graph response" not in json.dumps(result)


@pytest.mark.asyncio
async def test_empty_patch_response_is_supported():
    graph = GraphClient(
        settings(),
        StubAuth(),  # type: ignore[arg-type]
        httpx.MockTransport(lambda request: httpx.Response(204)),
    )

    assert await graph.request_json("PATCH", "/me/onenote/pages/page-id/content", json_body=[]) == {}


@pytest.mark.asyncio
async def test_graph_client_maps_network_error_without_details():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private endpoint failure", request=request)

    graph = GraphClient(settings(), StubAuth(), httpx.MockTransport(handler))  # type: ignore[arg-type]

    with pytest.raises(GraphRequestError) as error:
        await graph.request_json("GET", "/me/onenote/notebooks")

    assert error.value.code == "network_error"

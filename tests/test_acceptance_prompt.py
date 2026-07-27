from pathlib import Path

import pytest

from onenote_mcp.config import Settings
from onenote_mcp.server import create_server


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = PROJECT_ROOT / "tests" / "prompts" / "onenote_full_tool_acceptance_zh.md"


@pytest.mark.asyncio
async def test_full_tool_acceptance_prompt_covers_every_registered_tool(tmp_path):
    settings = Settings(
        client_id=None,
        cache_tokens=False,
        writes_enabled=False,
        cache_path=tmp_path / "unused-token-cache.bin",
    )
    registered_tools = await create_server(settings).get_tools()
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    assert registered_tools
    assert {name for name in registered_tools if name.startswith("delete_")} == {"delete_page"}
    for tool_name in registered_tools:
        assert f"`{tool_name}`" in prompt

    annotations = registered_tools["delete_page"].annotations
    assert annotations is not None
    assert annotations.destructiveHint is True
    assert annotations.readOnlyHint is False
    assert annotations.idempotentHint is False


def test_full_tool_acceptance_prompt_enforces_isolation_and_cleanup():
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    required_safety_markers = (
        "MCP-FULL-TOOL-ACCEPTANCE-YYYYMMDD-HHMMSS-<6位随机串>",
        "ONENOTE_ENABLE_WRITES=true",
        "ONENOTE_ENABLE_WRITES=false",
        "ONENOTE_ENABLE_DELETES=false",
        "不得绕过 MCP 直接调用 Microsoft Graph",
        "没有 `delete_notebook`、`delete_section`",
        "标题完全一致",
        "手动删除整个 Notebook",
        "SKIPPED_BY_POLICY",
        "不得盲目重发",
        "既有 OneNote 资源：未操作 / 无法确认",
    )
    for marker in required_safety_markers:
        assert marker in prompt

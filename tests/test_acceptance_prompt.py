from pathlib import Path

import pytest

from onenote_mcp.config import Settings
from onenote_mcp.server import create_server


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = PROJECT_ROOT / "tests" / "prompts" / "onenote_full_tool_acceptance_zh.md"
AGENT_POLICY_PATH = PROJECT_ROOT / "AGENTS.md"


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
        "本地 pytest 清理 Notebook 测试上下文",
        "不得请求、接收或使用 `Files.ReadWrite`",
        "不发送给 Agent、被调用的 Agent 或 Provider",
        "ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED=1",
        "package.type=oneNote",
        "`If-Match`",
        "SKIPPED_BY_POLICY",
        "不得盲目重发",
        "既有 OneNote 资源：未操作 / 无法确认",
    )
    for marker in required_safety_markers:
        assert marker in prompt


def test_agent_policy_keeps_files_permission_outside_every_agent_boundary():
    policy = AGENT_POLICY_PATH.read_text(encoding="utf-8")

    required_policy_markers = (
        "## 使用第三方 Agent 验收认证 MCP",
        "生产 `SCOPES`、MCP Server、Claude/Codex 配置和 Agent 临时 MCP 配置严禁请求或注入 `Files.ReadWrite`",
        "不得交给外部 Agent、被调用的 Agent 或其子进程决定和执行",
        "严禁使用 `Files.ReadWrite.All`",
        "复用生产 MCP 的平台加密 MSAL cache",
        "ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED=1",
        "`MCP-FULL-TOOL-ACCEPTANCE-` 前缀",
        "`If-Match`",
        "PHASE_RESULT=<phase>:FAIL:<safe_code>",
        "docs/lessons/authenticated_mcp_agent_acceptance.md",
    )
    for marker in required_policy_markers:
        assert marker in policy

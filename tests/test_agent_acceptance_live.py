"""Opt-in real-account OneNote tool acceptance through Claude Code and pytest.

The runner is deliberately fail-closed. It validates the local runtime,
encrypted authentication cache, MCP registration, tool registry, persistent
safety switches, and explicit data/write authorizations before every Claude
agent invocation. Sensitive cleanup and verification stay in this local test
process; raw MCP or Claude output is held in memory and never logged.
"""

from __future__ import annotations

import asyncio
import ast
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence
from urllib.parse import quote

import pytest

from onenote_mcp.auth import SCOPES, AuthManager, AuthenticationError
from onenote_mcp.config import Settings
from onenote_mcp.graph import GraphClient, GraphRequestError
from onenote_mcp.server import create_server
from onenote_mcp.tools import OneNoteTools


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL_CONFIG = PROJECT_ROOT / ".codex" / "config.toml"
TOKEN_CACHE_PATH = Settings.from_environment().cache_path
LIVE_CONTROL_SCOPES = (*SCOPES, "https://graph.microsoft.com/Files.ReadWrite")
MCP_ENV_SECTION = "mcp_servers.onenote.env"
PLACEHOLDER_VALUES = {"", "YOUR_AZURE_CLIENT_ID_HERE", "your-public-client-id"}

EXPECTED_TOOLS = frozenset(
    {
        "start_authentication",
        "complete_authentication",
        "check_authentication",
        "clear_token_cache",
        "list_notebooks",
        "get_notebook",
        "list_sections",
        "get_section",
        "list_pages",
        "get_page_metadata",
        "get_page_content",
        "create_notebook",
        "create_section",
        "create_page",
        "update_page_content",
        "delete_page",
    }
)

GUARD_TOOLS = frozenset({"check_authentication", "create_notebook", "list_notebooks"})
NOTEBOOK_TOOLS = frozenset(
    {
        "check_authentication",
        "list_notebooks",
        "get_notebook",
        "create_notebook",
    }
)
SECTION_TOOLS = frozenset(
    {
        "check_authentication",
        "list_notebooks",
        "get_notebook",
        "list_sections",
        "get_section",
        "create_section",
    }
)
PAGE_TOOLS = frozenset(
    {
        "check_authentication",
        "list_notebooks",
        "get_notebook",
        "list_sections",
        "get_section",
        "list_pages",
        "get_page_metadata",
        "create_page",
    }
)
UPDATE_TOOLS = frozenset(
    {
        "check_authentication",
        "list_notebooks",
        "get_notebook",
        "list_sections",
        "get_section",
        "list_pages",
        "get_page_metadata",
        "get_page_content",
        "update_page_content",
    }
)
TRACE_MARKER = re.compile(r"^PHASE_RESULT=([a-z_]+):(PASS|FAIL):([a-z_]+)$", re.MULTILINE)
SECTION_PATTERN = re.compile(r"^\s*\[([^]]+)]\s*$")
ASSIGNMENT_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
SAFE_AGENT_FAILURE_CODES = frozenset(
    {
        "authentication_required",
        "content_mismatch",
        "target_exists",
        "target_missing",
        "target_not_visible",
        "tool_error",
        "unexpected_result",
        "write_rejected",
    }
)


class AcceptanceError(RuntimeError):
    """A safe, fixed-code failure that cannot contain tool or credential data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class LocalMcpConfig:
    client_id: str = field(repr=False)
    cache_tokens: bool
    writes_enabled: bool
    deletes_enabled: bool
    source_path: Path = field(repr=False)


@dataclass(frozen=True)
class Phase:
    name: str
    writes_enabled: bool
    deletes_enabled: bool
    allowed_tools: frozenset[str]
    required_calls: frozenset[str]
    expected_code: str


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = field(repr=False)
    stderr: str = field(repr=False)


CommandRunner = Callable[[Sequence[str], Path, int], CommandResult]
PhasePreflight = Callable[[Path, LocalMcpConfig, Phase], None]


PHASES = {
    "guard": Phase(
        name="guard",
        writes_enabled=False,
        deletes_enabled=False,
        allowed_tools=GUARD_TOOLS,
        required_calls=frozenset({"check_authentication", "create_notebook", "list_notebooks"}),
        expected_code="writes_disabled",
    ),
    "notebook": Phase(
        name="notebook",
        writes_enabled=True,
        deletes_enabled=False,
        allowed_tools=NOTEBOOK_TOOLS,
        required_calls=NOTEBOOK_TOOLS,
        expected_code="verified",
    ),
    "section": Phase(
        name="section",
        writes_enabled=True,
        deletes_enabled=False,
        allowed_tools=SECTION_TOOLS,
        required_calls=SECTION_TOOLS,
        expected_code="verified",
    ),
    "page": Phase(
        name="page",
        writes_enabled=True,
        deletes_enabled=False,
        allowed_tools=PAGE_TOOLS,
        required_calls=PAGE_TOOLS,
        expected_code="verified",
    ),
    "update": Phase(
        name="update",
        writes_enabled=True,
        deletes_enabled=False,
        allowed_tools=UPDATE_TOOLS,
        required_calls=UPDATE_TOOLS,
        expected_code="verified",
    ),
}


def _parse_bool(value: str, *, key: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise AcceptanceError(f"invalid_{key.lower()}")


def _parse_toml_string(raw_value: str, *, key: str) -> str:
    try:
        parsed = ast.literal_eval(raw_value)
    except (SyntaxError, ValueError) as exc:
        raise AcceptanceError(f"invalid_{key.lower()}") from exc
    if not isinstance(parsed, str):
        raise AcceptanceError(f"invalid_{key.lower()}")
    return parsed


def load_local_mcp_config(path: Path = DEFAULT_LOCAL_CONFIG) -> LocalMcpConfig:
    """Read only the local OneNote env section without returning its Client ID."""

    if not path.is_file() or path.is_symlink():
        raise AcceptanceError("local_config_missing_or_unsafe")
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise AcceptanceError("local_config_permissions")

    values: dict[str, str] = {}
    section = ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AcceptanceError("local_config_unreadable") from exc

    if any("AZURE_CLIENT_SECRET" in raw_line for raw_line in lines):
        raise AcceptanceError("client_secret_forbidden")

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        section_match = SECTION_PATTERN.match(raw_line)
        if section_match:
            section = section_match.group(1).strip()
            continue
        assignment = ASSIGNMENT_PATTERN.match(raw_line)
        if section != MCP_ENV_SECTION or assignment is None:
            continue
        key, raw_value = assignment.groups()
        if key == "AZURE_CLIENT_SECRET":
            raise AcceptanceError("client_secret_forbidden")
        if key in {
            "AZURE_CLIENT_ID",
            "ONENOTE_CACHE_TOKENS",
            "ONENOTE_ENABLE_WRITES",
            "ONENOTE_ENABLE_DELETES",
        }:
            values[key] = _parse_toml_string(raw_value, key=key)

    client_id = values.get("AZURE_CLIENT_ID", "")
    if client_id in PLACEHOLDER_VALUES:
        raise AcceptanceError("client_id_missing")
    try:
        uuid.UUID(client_id)
    except (ValueError, AttributeError) as exc:
        raise AcceptanceError("client_id_invalid") from exc

    config = LocalMcpConfig(
        client_id=client_id,
        cache_tokens=_parse_bool(values.get("ONENOTE_CACHE_TOKENS", "true"), key="cache_tokens"),
        writes_enabled=_parse_bool(values.get("ONENOTE_ENABLE_WRITES", "false"), key="writes"),
        deletes_enabled=_parse_bool(values.get("ONENOTE_ENABLE_DELETES", "false"), key="deletes"),
        source_path=path,
    )
    if not config.cache_tokens:
        raise AcceptanceError("encrypted_cache_disabled")
    if config.writes_enabled or config.deletes_enabled:
        raise AcceptanceError("persistent_safety_switches_not_false")
    return config


def _settings(local: LocalMcpConfig) -> Settings:
    return Settings(
        client_id=local.client_id,
        cache_tokens=True,
        writes_enabled=False,
        deletes_enabled=False,
        cache_path=TOKEN_CACHE_PATH,
    )


async def _registered_tools() -> frozenset[str]:
    settings = Settings(
        client_id=None,
        cache_tokens=False,
        writes_enabled=False,
        deletes_enabled=False,
        cache_path=PROJECT_ROOT / ".acceptance-unused-cache",
    )
    tools = await create_server(settings).get_tools()
    delete_annotations = tools.get("delete_page").annotations if "delete_page" in tools else None
    if (
        delete_annotations is None
        or delete_annotations.destructiveHint is not True
        or delete_annotations.readOnlyHint is not False
        or delete_annotations.idempotentHint is not False
    ):
        raise AcceptanceError("delete_annotations_invalid")
    return frozenset(tools)


async def _check_auth_and_graph(local: LocalMcpConfig) -> None:
    settings = _settings(local)
    auth = AuthManager(settings)
    if not auth.has_valid_session():
        raise AcceptanceError("authentication_not_ready")
    if auth.cache_status != "encrypted":
        raise AcceptanceError("encrypted_cache_unavailable")
    graph = GraphClient(settings, auth)
    try:
        response = await graph.request_json("GET", "/me/onenote/notebooks")
    except GraphRequestError as exc:
        raise AcceptanceError(f"graph_{exc.code}") from exc
    if not isinstance(response.get("value"), list):
        raise AcceptanceError("graph_list_shape_invalid")


def _safe_progress_events(raw_line: str) -> tuple[str, ...]:
    """Extract only non-sensitive progress markers from one Claude JSON event."""

    try:
        event = json.loads(raw_line)
    except json.JSONDecodeError:
        return ()
    if not isinstance(event, dict):
        return ()

    progress: list[str] = []
    message = event.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), list):
        for block in message["content"]:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name")
            if isinstance(name, str) and name.startswith("mcp__onenote__"):
                tool_name = name.removeprefix("mcp__onenote__")
                if tool_name in EXPECTED_TOOLS:
                    progress.append(f"AGENT_TOOL_CALL={tool_name}")

    result_text = event.get("result") if event.get("type") == "result" else None
    if isinstance(result_text, str):
        marker = TRACE_MARKER.search(result_text)
        if marker is not None:
            phase, status, code = marker.groups()
            configured_phase = PHASES.get(phase)
            valid_code = (
                configured_phase is not None
                and (
                    (status == "PASS" and code == configured_phase.expected_code)
                    or (status == "FAIL" and code in SAFE_AGENT_FAILURE_CODES)
                )
            )
            if valid_code:
                progress.append(f"AGENT_RESULT={phase}:{status}:{code}")
            else:
                safe_phase = phase if configured_phase is not None else "unknown"
                progress.append(f"AGENT_RESULT={safe_phase}:FAIL:failure_code_invalid")
    return tuple(progress)


def _default_command_runner(command: Sequence[str], cwd: Path, timeout: int) -> CommandResult:
    """Stream sanitized progress while retaining complete output in memory."""

    try:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise AcceptanceError("command_not_found") from exc

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def drain_stdout() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            stdout_lines.append(line)
            for progress in _safe_progress_events(line):
                print(progress, flush=True)

    def drain_stderr() -> None:
        assert process.stderr is not None
        stderr_lines.extend(process.stderr)

    stdout_thread = threading.Thread(target=drain_stdout, daemon=True)
    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        stdout_thread.join()
        stderr_thread.join()
        raise AcceptanceError("command_timeout") from exc
    stdout_thread.join()
    stderr_thread.join()
    return CommandResult(returncode, "".join(stdout_lines), "".join(stderr_lines))


def _require_command(name: str) -> str:
    command = shutil.which(name)
    if command is None:
        raise AcceptanceError(f"{name}_not_found")
    return command


def _run_project_checks(uv_command: str, runner: CommandRunner) -> None:
    lock = runner([uv_command, "lock", "--check", "--offline"], PROJECT_ROOT, 120)
    if lock.returncode != 0:
        raise AcceptanceError("lock_check_failed")
    tests = runner([uv_command, "run", "pytest", "-q", "-m", "not live"], PROJECT_ROOT, 300)
    if tests.returncode != 0:
        raise AcceptanceError("unit_tests_failed")


def _check_claude_mcp(claude_command: str, runner: CommandRunner) -> None:
    health = runner([claude_command, "mcp", "list"], PROJECT_ROOT, 60)
    combined = f"{health.stdout}\n{health.stderr}"
    if health.returncode != 0 or not re.search(r"(?m)^onenote:.*(?:✔\s*)?Connected\s*$", combined):
        raise AcceptanceError("claude_mcp_not_connected")
    details = runner([claude_command, "mcp", "get", "onenote"], PROJECT_ROOT, 60)
    detail_text = f"{details.stdout}\n{details.stderr}"
    if details.returncode != 0:
        raise AcceptanceError("claude_mcp_details_unavailable")
    if "AZURE_CLIENT_SECRET" in detail_text:
        raise AcceptanceError("client_secret_forbidden")
    for variable, code in (
        ("ONENOTE_ENABLE_WRITES", "claude_persistent_writes_enabled"),
        ("ONENOTE_ENABLE_DELETES", "claude_persistent_deletes_enabled"),
    ):
        enabled = re.search(rf"{variable}\s*(?::|=)\s*[\"']?true\b", detail_text, re.IGNORECASE)
        if enabled:
            raise AcceptanceError(code)


def run_base_preflight(
    local_config_path: Path = DEFAULT_LOCAL_CONFIG,
    *,
    runner: CommandRunner = _default_command_runner,
) -> LocalMcpConfig:
    """Run all checks that must pass before any agent process may start."""

    if sys.version_info < (3, 10):
        raise AcceptanceError("python_too_old")
    uv_command = _require_command("uv")
    claude_command = _require_command("claude")
    local = load_local_mcp_config(local_config_path)
    if asyncio.run(_registered_tools()) != EXPECTED_TOOLS:
        raise AcceptanceError("tool_registry_mismatch")
    _run_project_checks(uv_command, runner)
    _check_claude_mcp(claude_command, runner)
    asyncio.run(_check_auth_and_graph(local))
    return local


def ensure_authorizations(*, provider_data: bool, writes: bool, drive_cleanup: bool) -> None:
    if not provider_data:
        raise AcceptanceError("provider_data_authorization_required")
    if not writes:
        raise AcceptanceError("write_authorization_required")
    if not drive_cleanup:
        raise AcceptanceError("drive_cleanup_authorization_required")


@contextmanager
def temporary_mcp_config(
    local: LocalMcpConfig,
    phase: Phase,
    *,
    uv_command: str,
) -> Iterator[Path]:
    """Create a mode-0600 Claude MCP config and delete it after the phase."""

    payload = {
        "mcpServers": {
            "onenote": {
                "command": uv_command,
                "args": [
                    "--directory",
                    str(PROJECT_ROOT),
                    "run",
                    "--frozen",
                    "onenote-mcp-server",
                ],
                "env": {
                    "AZURE_CLIENT_ID": local.client_id,
                    "ONENOTE_CACHE_TOKENS": "true",
                    "ONENOTE_ENABLE_WRITES": str(phase.writes_enabled).lower(),
                    "ONENOTE_ENABLE_DELETES": str(phase.deletes_enabled).lower(),
                },
            }
        }
    }
    with tempfile.TemporaryDirectory(prefix="onenote-agent-acceptance-") as directory:
        directory_path = Path(directory)
        if os.name != "nt":
            directory_path.chmod(0o700)
        config_path = directory_path / "mcp.json"
        descriptor = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        yield config_path


def validate_phase_preconditions(config_path: Path, local: LocalMcpConfig, phase: Phase) -> None:
    """Re-check local and ephemeral safety state immediately before Claude."""

    current = load_local_mcp_config(local.source_path)
    if current.client_id != local.client_id:
        raise AcceptanceError("client_id_changed_during_run")
    if not config_path.is_file() or config_path.is_symlink():
        raise AcceptanceError("temporary_config_missing_or_unsafe")
    if os.name != "nt" and stat.S_IMODE(config_path.stat().st_mode) != 0o600:
        raise AcceptanceError("temporary_config_permissions")
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        server = payload["mcpServers"]["onenote"]
        env = server["env"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise AcceptanceError("temporary_config_invalid") from exc
    if "AZURE_CLIENT_SECRET" in env:
        raise AcceptanceError("client_secret_forbidden")
    if env.get("AZURE_CLIENT_ID") != local.client_id:
        raise AcceptanceError("temporary_client_id_mismatch")
    if env.get("ONENOTE_ENABLE_WRITES") != str(phase.writes_enabled).lower():
        raise AcceptanceError("temporary_write_switch_mismatch")
    if env.get("ONENOTE_ENABLE_DELETES") != str(phase.deletes_enabled).lower():
        raise AcceptanceError("temporary_delete_switch_mismatch")
    if phase.deletes_enabled and not phase.writes_enabled:
        raise AcceptanceError("delete_without_write_forbidden")
    if not phase.allowed_tools.issubset(EXPECTED_TOOLS):
        raise AcceptanceError("phase_tool_allowlist_invalid")
    if asyncio.run(_registered_tools()) != EXPECTED_TOOLS:
        raise AcceptanceError("tool_registry_changed_during_run")
    asyncio.run(_check_auth_and_graph(local))


def build_claude_command(
    *,
    claude_command: str,
    config_path: Path,
    phase: Phase,
    prompt: str,
) -> list[str]:
    allowed = ",".join(f"mcp__onenote__{name}" for name in sorted(phase.allowed_tools))
    return [
        claude_command,
        "-p",
        prompt,
        "--strict-mcp-config",
        "--mcp-config",
        str(config_path),
        "--setting-sources",
        "user,project,local",
        "--tools",
        "",
        "--allowedTools",
        allowed,
        "--permission-mode",
        "dontAsk",
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--verbose",
    ]


def _collect_trace(stdout: str) -> tuple[frozenset[str], str | None]:
    calls: set[str] = set()
    final_text: str | None = None
    for raw_line in stdout.splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        message = event.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name")
                    if isinstance(name, str) and name.startswith("mcp__onenote__"):
                        calls.add(name.removeprefix("mcp__onenote__"))
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            final_text = event["result"]
    return frozenset(calls), final_text


def validate_agent_trace(result: CommandResult, phase: Phase) -> None:
    if result.returncode != 0:
        raise AcceptanceError(f"agent_{phase.name}_failed")
    calls, final_text = _collect_trace(result.stdout)
    marker = TRACE_MARKER.search(final_text or "")
    if marker is None:
        raise AcceptanceError(f"agent_{phase.name}_result_invalid")
    marker_phase, status, code = marker.groups()
    if marker_phase != phase.name:
        raise AcceptanceError(f"agent_{phase.name}_result_failed")
    if status == "FAIL":
        if code not in SAFE_AGENT_FAILURE_CODES:
            raise AcceptanceError(f"agent_{phase.name}_failure_code_invalid")
        raise AcceptanceError(f"agent_{phase.name}_reported_{code}")
    if code != phase.expected_code:
        raise AcceptanceError(f"agent_{phase.name}_result_failed")
    missing = sorted(phase.required_calls - calls)
    if missing:
        raise AcceptanceError(f"agent_{phase.name}_missing_{'_'.join(missing)}")


def _result_contract(phase_name: str, success_code: str) -> str:
    failure_codes = "、".join(sorted(SAFE_AGENT_FAILURE_CODES))
    return (
        f"成功时只输出 PHASE_RESULT={phase_name}:PASS:{success_code}。"
        f"失败时只输出 PHASE_RESULT={phase_name}:FAIL:<原因码>，原因码只能是：{failure_codes}；"
        "不得在原因码或其他输出中加入资源名称、ID、响应正文或认证信息。"
    )


def _guard_prompt(notebook_name: str) -> str:
    return f"""你是 OneNote MCP 自动验收 Agent。只执行默认写保护阶段。
测试 Notebook 名称是 {notebook_name}。先调用 check_authentication，必须已认证；调用 create_notebook 一次，必须返回 writes_disabled；再调用 list_notebooks，只确认该精确名称不存在。不得输出任何列表、名称、资源 ID、账号或认证材料，不得调用未授权工具。你和你调用的任何 Agent 都不得请求 Files 权限、Drive/原始 Graph 工具或 Notebook 清理信息；清理由本地 pytest 独立执行。禁止真实写入或重试。{_result_contract("guard", "writes_disabled")}"""


def _notebook_prompt(notebook_name: str) -> str:
    return f"""你是 OneNote MCP 自动验收 Agent。只执行 Notebook 创建与精确回读阶段，唯一目标名称是 {notebook_name}。
先调用 check_authentication，再调用 list_notebooks 确认精确名称不存在。只调用一次 create_notebook；随后再次调用 list_notebooks 确认恰好一个精确匹配，并必须调用 get_notebook 回读该 Notebook。此阶段不得创建 Section/Page，不得更新或删除。超时先只读回查，禁止盲目重发。你和你调用的任何 Agent 都不得请求 Files 权限、Drive/原始 Graph 工具、DriveItem 信息或 Notebook 删除；测试上下文清理由本地 pytest 独立执行。不得输出列表、资源 ID、账号或认证材料。{_result_contract("notebook", "verified")}"""


def _section_prompt(notebook_name: str, section_name: str) -> str:
    return f"""你是 OneNote MCP 自动验收 Agent。只执行 Section 创建与精确回读阶段：Notebook={notebook_name}，Section={section_name}。
先调用 check_authentication，再依次调用 list_notebooks 和 get_notebook 精确定位唯一 Notebook。调用 list_sections 确认目标 Section 不存在，只调用一次 create_section；随后再次调用 list_sections 确认恰好一个精确匹配，并必须调用 get_section 回读该 Section。此阶段不得创建 Notebook/Page，不得更新或删除。超时先只读回查，禁止盲目重发。你和你调用的任何 Agent 都不得请求 Files 权限、Drive/原始 Graph 工具、DriveItem 信息或 Notebook 删除；测试上下文清理由本地 pytest 独立执行。不得输出列表、资源 ID、账号或认证材料。{_result_contract("section", "verified")}"""


def _page_prompt(notebook_name: str, section_name: str, page_title: str, suffix: str) -> str:
    return f"""你是 OneNote MCP 自动验收 Agent。只执行 Page 创建与元数据回读阶段：Notebook={notebook_name}，Section={section_name}，Page={page_title}。
先调用 check_authentication，再依次调用 list_notebooks、get_notebook、list_sections、get_section 精确定位唯一 Section。调用 list_pages 确认目标 Page 不存在，只调用一次 create_page，页面内容必须包含 CREATE-MARKER-{suffix}；随后再次调用 list_pages 确认恰好一个精确匹配，并必须调用 get_page_metadata 回读该 Page。此阶段不得创建 Notebook/Section，不得读取 HTML、更新或删除。超时先只读回查，禁止盲目重发。你和你调用的任何 Agent 都不得请求 Files 权限、Drive/原始 Graph 工具、DriveItem 信息或 Notebook 删除；测试上下文清理由本地 pytest 独立执行。不得输出列表、资源 ID、HTML、账号或认证材料。{_result_contract("page", "verified")}"""


def _update_prompt(notebook_name: str, section_name: str, page_title: str, suffix: str) -> str:
    return f"""你是 OneNote MCP 自动验收 Agent。只执行既有隔离 Page 的内容读取与单次更新阶段：Notebook={notebook_name}，Section={section_name}，Page={page_title}。
先 check_authentication，再依次调用 list_notebooks、get_notebook、list_sections、get_section、list_pages、get_page_metadata，按精确名称定位本轮唯一层级。调用 get_page_content 确认 CREATE-MARKER-{suffix} 存在。然后只调用一次 update_page_content，向 body 追加 UPDATE-MARKER-{suffix}；再次调用 get_page_content，确认创建标记仍存在且更新标记恰好一次；最后再次调用 get_page_metadata。此阶段没有创建或删除工具，不得操作其他资源。更新超时先回读，禁止盲目重发。你和你调用的任何 Agent 都不得请求 Files 权限、Drive/原始 Graph 工具、DriveItem 信息或 Notebook 删除；测试上下文清理由本地 pytest 独立执行。不得输出列表、资源 ID、HTML、账号或认证材料。{_result_contract("update", "verified")}"""


def execute_agent_phase(
    *,
    local: LocalMcpConfig,
    phase: Phase,
    prompt: str,
    runner: CommandRunner = _default_command_runner,
    preflight: PhasePreflight = validate_phase_preconditions,
    timeout: int = 600,
) -> None:
    """Preflight the exact phase config, then invoke Claude with minimal tools."""

    uv_command = _require_command("uv")
    claude_command = _require_command("claude")
    print(f"AGENT_PHASE_START={phase.name}", flush=True)
    with temporary_mcp_config(local, phase, uv_command=uv_command) as config_path:
        preflight(config_path, local, phase)
        command = build_claude_command(
            claude_command=claude_command,
            config_path=config_path,
            phase=phase,
            prompt=prompt,
        )
        result = runner(command, PROJECT_ROOT, timeout)
        try:
            validate_agent_trace(result, phase)
        except AcceptanceError as exc:
            print(f"AGENT_PHASE_FAIL={phase.name}:{exc.code}", flush=True)
            raise
        print(f"AGENT_PHASE_PASS={phase.name}", flush=True)


@dataclass(frozen=True)
class LiveNames:
    notebook: str
    section: str
    page: str
    suffix: str


@dataclass(frozen=True)
class LiveResources:
    notebook_id: str = field(repr=False)
    section_id: str = field(repr=False)
    page_id: str = field(repr=False)
    page_title: str


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _test_names() -> LiveNames:
    configured_run_id = os.getenv("ONENOTE_LIVE_RUN_ID", "").strip()
    if configured_run_id:
        if re.fullmatch(r"[A-Za-z0-9-]{1,48}", configured_run_id) is None:
            raise AcceptanceError("live_run_id_invalid")
        run_id = configured_run_id.upper()
    else:
        stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        run_id = f"{stamp}-{secrets.token_hex(3).upper()}"
    suffix = run_id[-24:]
    return LiveNames(
        notebook=f"MCP-FULL-TOOL-ACCEPTANCE-{run_id}",
        section=f"CRUD-SECTION-{suffix}",
        page=f"CRUD PAGE {run_id}",
        suffix=suffix,
    )


def _live_components(
    local: LocalMcpConfig,
    *,
    writes_enabled: bool = False,
    deletes_enabled: bool = False,
) -> tuple[GraphClient, OneNoteTools]:
    settings = Settings(
        client_id=local.client_id,
        cache_tokens=True,
        writes_enabled=writes_enabled,
        deletes_enabled=deletes_enabled,
        cache_path=TOKEN_CACHE_PATH,
    )
    auth = AuthManager(settings)
    graph = GraphClient(settings, auth)
    return graph, OneNoteTools(settings, auth, graph)


def _control_auth(local: LocalMcpConfig) -> tuple[Settings, AuthManager]:
    settings = Settings(
        client_id=local.client_id,
        cache_tokens=True,
        writes_enabled=False,
        deletes_enabled=False,
        cache_path=TOKEN_CACHE_PATH,
    )
    auth = AuthManager(settings, scopes=LIVE_CONTROL_SCOPES)
    return settings, auth


def _control_graph(local: LocalMcpConfig) -> GraphClient:
    """Build a local-only Drive client that reuses the encrypted MCP cache."""

    settings, auth = _control_auth(local)
    if not auth.has_valid_session():
        raise AcceptanceError("files_scope_authentication_not_ready")
    if auth.cache_status != "encrypted":
        raise AcceptanceError("files_scope_encrypted_cache_unavailable")
    return GraphClient(settings, auth, allowed_endpoint_prefixes=("/me/drive/",))


def _collection(response: dict[str, Any], *, code: str) -> list[dict[str, Any]]:
    value = response.get("value")
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AcceptanceError(code)
    return value


async def _matching_notebooks(graph: GraphClient, notebook_name: str) -> list[dict[str, Any]]:
    response = await graph.request_json("GET", "/me/onenote/notebooks")
    return [
        item
        for item in _collection(response, code="notebook_list_shape_invalid")
        if item.get("displayName") == notebook_name
    ]


async def _matching_drive_notebooks(graph: GraphClient, notebook_name: str) -> list[dict[str, Any]]:
    escaped_name = quote(notebook_name.replace("'", "''"), safe="")
    response = await graph.request_json(
        "GET",
        f"/me/drive/root/search(q='{escaped_name}')"
        "?$select=id,name,package,eTag,remoteItem&$top=200",
    )
    if response.get("@odata.nextLink"):
        raise AcceptanceError("drive_search_pagination_ambiguous")
    candidates = _collection(response, code="drive_search_shape_invalid")
    return [
        item
        for item in candidates
        if item.get("name") == notebook_name
        and isinstance(item.get("package"), dict)
        and item["package"].get("type") == "oneNote"
        and "remoteItem" not in item
    ]


async def cleanup_matching_test_notebook(local: LocalMcpConfig, notebook_name: str) -> bool:
    """Delete one exact test Notebook package through the local control plane.

    The DriveItem must have the exact reserved test name, be the only matching
    OneNote package, expose an eTag, and not be a remote item. Deletion uses
    If-Match and moves the package to the OneDrive recycle bin.
    """

    if not notebook_name.startswith("MCP-FULL-TOOL-ACCEPTANCE-"):
        raise AcceptanceError("drive_cleanup_name_outside_test_prefix")
    notes_graph, _ = _live_components(local)
    drive_graph = _control_graph(local)
    try:
        notes_matches = await _matching_notebooks(notes_graph, notebook_name)
        drive_matches = await _matching_drive_notebooks(drive_graph, notebook_name)
    except GraphRequestError as exc:
        raise AcceptanceError(f"cleanup_{exc.code}") from exc

    if len(notes_matches) > 1 or len(drive_matches) > 1:
        raise AcceptanceError("drive_cleanup_match_ambiguous")
    if not notes_matches and not drive_matches:
        return False
    if len(drive_matches) != 1:
        raise AcceptanceError("drive_cleanup_package_not_unique")

    search_item_id = drive_matches[0].get("id")
    if not isinstance(search_item_id, str) or not search_item_id:
        raise AcceptanceError("drive_cleanup_identity_incomplete")
    try:
        drive_item = await drive_graph.request_json(
            "GET",
            f"/me/drive/items/{quote(search_item_id, safe='')}"
            "?$select=id,name,package,eTag,remoteItem",
        )
        item_id = drive_item.get("id")
        etag = drive_item.get("eTag")
        if (
            item_id != search_item_id
            or drive_item.get("name") != notebook_name
            or not isinstance(drive_item.get("package"), dict)
            or drive_item["package"].get("type") != "oneNote"
            or "remoteItem" in drive_item
        ):
            raise AcceptanceError("drive_cleanup_identity_mismatch")
        if not isinstance(etag, str) or not etag:
            raise AcceptanceError("drive_cleanup_identity_incomplete")
        await drive_graph.request_json(
            "DELETE",
            f"/me/drive/items/{quote(item_id, safe='')}",
            if_match=etag,
        )
        for _ in range(5):
            if not await _matching_notebooks(notes_graph, notebook_name) and not await _matching_drive_notebooks(
                drive_graph, notebook_name
            ):
                return True
            await asyncio.sleep(1)
    except GraphRequestError as exc:
        raise AcceptanceError(f"cleanup_{exc.code}") from exc
    raise AcceptanceError("drive_cleanup_not_observed")


async def notebook_is_absent(local: LocalMcpConfig, notebook_name: str) -> bool:
    graph, _ = _live_components(local)
    return not await _matching_notebooks(graph, notebook_name)


async def verify_created_resources(local: LocalMcpConfig, names: LiveNames) -> LiveResources:
    """Verify Agent-created state locally without sending results to a Provider."""

    graph, _ = _live_components(local)
    notebooks = await _matching_notebooks(graph, names.notebook)
    if len(notebooks) != 1 or not isinstance(notebooks[0].get("id"), str):
        raise AcceptanceError("created_notebook_not_unique")
    notebook_id = notebooks[0]["id"]

    section_response = await graph.request_json(
        "GET", f"/me/onenote/notebooks/{quote(notebook_id, safe='')}/sections"
    )
    sections = [
        item
        for item in _collection(section_response, code="section_list_shape_invalid")
        if item.get("displayName") == names.section
    ]
    if len(sections) != 1 or not isinstance(sections[0].get("id"), str):
        raise AcceptanceError("created_section_not_unique")
    section_id = sections[0]["id"]

    page_response = await graph.request_json(
        "GET", f"/me/onenote/sections/{quote(section_id, safe='')}/pages"
    )
    pages = [
        item
        for item in _collection(page_response, code="page_list_shape_invalid")
        if item.get("title") == names.page
    ]
    if len(pages) != 1 or not isinstance(pages[0].get("id"), str):
        raise AcceptanceError("created_page_not_unique")
    page_id = pages[0]["id"]
    content = await graph.request_text("GET", f"/me/onenote/pages/{quote(page_id, safe='')}/content")
    if f"CREATE-MARKER-{names.suffix}" not in content:
        raise AcceptanceError("create_marker_missing")
    if content.count(f"UPDATE-MARKER-{names.suffix}") != 1:
        raise AcceptanceError("update_marker_count_invalid")
    return LiveResources(notebook_id, section_id, page_id, names.page)


async def delete_test_page_locally(local: LocalMcpConfig, resources: LiveResources) -> None:
    """Invoke the guarded Page tool locally; no resource data reaches Claude."""

    graph, tools = _live_components(local, writes_enabled=True, deletes_enabled=True)
    result = json.loads(await tools.delete_page(resources.page_id, resources.page_title))
    if result != {"status": "success", "message": "Page deleted."}:
        raise AcceptanceError("local_page_delete_failed")
    page_response = await graph.request_json(
        "GET", f"/me/onenote/sections/{quote(resources.section_id, safe='')}/pages"
    )
    pages = _collection(page_response, code="page_list_shape_invalid")
    if any(item.get("id") == resources.page_id for item in pages):
        raise AcceptanceError("local_page_delete_not_observed")


async def verify_safety_guards_locally(local: LocalMcpConfig, suffix: str) -> None:
    """Exercise sensitive guard paths in-process without Claude or Graph writes."""

    _, tools = _live_components(local, writes_enabled=False, deletes_enabled=False)
    delete_result = json.loads(await tools.delete_page(f"guard-page-{suffix}", f"guard-title-{suffix}"))
    create_result = json.loads(await tools.create_notebook(f"WRITE-GUARD-{suffix}"))
    if delete_result.get("code") != "writes_disabled" or create_result.get("code") != "writes_disabled":
        raise AcceptanceError("local_safety_guard_failed")


def _live_timeout() -> int:
    try:
        timeout = int(os.getenv("ONENOTE_LIVE_AGENT_TIMEOUT", "600"))
    except ValueError as exc:
        raise AcceptanceError("live_timeout_invalid") from exc
    if timeout < 30 or timeout > 1800:
        raise AcceptanceError("live_timeout_invalid")
    return timeout


@pytest.mark.live
def test_files_control_scope_authentication_live() -> None:
    """Ensure the shared encrypted cache can supply Files.ReadWrite without an Agent."""

    if not _env_enabled("ONENOTE_LIVE_CONTROL_AUTH"):
        pytest.skip("set ONENOTE_LIVE_CONTROL_AUTH=1 to opt in")
    console_path = Path("CONOUT$") if os.name == "nt" else Path("/dev/tty")
    if not console_path.exists():
        pytest.fail("interactive_terminal_required", pytrace=False)
    try:
        local = load_local_mcp_config(DEFAULT_LOCAL_CONFIG)
        _, auth = _control_auth(local)
        if auth.has_valid_session():
            assert auth.cache_status == "encrypted"
            return
        flow = auth.start_device_flow()
        with console_path.open("w", encoding="utf-8") as console:
            console.write(f"Open: {flow['verification_uri']}\n")
            console.write(f"Code: {flow['user_code']}\n")
            console.write("Complete the local test-control authorization in the browser.\n")
        auth.complete_device_flow()
        if not auth.has_valid_session() or auth.cache_status != "encrypted":
            raise AcceptanceError("files_scope_authentication_failed")
    except (AcceptanceError, AuthenticationError) as exc:
        code = exc.code if isinstance(exc, AcceptanceError) else "files_scope_authentication_failed"
        pytest.fail(code, pytrace=False)


@pytest.mark.live
def test_claude_agent_onenote_tools_live() -> None:
    """Run opt-in Agent CRUD while local code owns all sensitive controls."""

    if not _env_enabled("ONENOTE_RUN_LIVE_AGENT_ACCEPTANCE"):
        pytest.skip("set ONENOTE_RUN_LIVE_AGENT_ACCEPTANCE=1 to opt in")

    names: LiveNames | None = None
    local: LocalMcpConfig | None = None
    primary_error: AcceptanceError | None = None
    cleanup_error: AcceptanceError | None = None
    drive_cleanup_approved = _env_enabled("ONENOTE_LIVE_DRIVE_CLEANUP_APPROVED")
    try:
        ensure_authorizations(
            provider_data=_env_enabled("ONENOTE_PROVIDER_DATA_APPROVED"),
            writes=_env_enabled("ONENOTE_LIVE_WRITES_APPROVED"),
            drive_cleanup=drive_cleanup_approved,
        )
        local = run_base_preflight(DEFAULT_LOCAL_CONFIG)
        names = _test_names()
        asyncio.run(cleanup_matching_test_notebook(local, names.notebook))
        timeout = _live_timeout()

        execute_agent_phase(
            local=local,
            phase=PHASES["guard"],
            prompt=_guard_prompt(names.notebook),
            timeout=timeout,
        )
        execute_agent_phase(
            local=local,
            phase=PHASES["notebook"],
            prompt=_notebook_prompt(names.notebook),
            timeout=timeout,
        )
        execute_agent_phase(
            local=local,
            phase=PHASES["section"],
            prompt=_section_prompt(names.notebook, names.section),
            timeout=timeout,
        )
        execute_agent_phase(
            local=local,
            phase=PHASES["page"],
            prompt=_page_prompt(names.notebook, names.section, names.page, names.suffix),
            timeout=timeout,
        )
        execute_agent_phase(
            local=local,
            phase=PHASES["update"],
            prompt=_update_prompt(names.notebook, names.section, names.page, names.suffix),
            timeout=timeout,
        )

        resources = asyncio.run(verify_created_resources(local, names))
        if _env_enabled("ONENOTE_LIVE_PAGE_DELETE_APPROVED"):
            asyncio.run(delete_test_page_locally(local, resources))
        asyncio.run(verify_safety_guards_locally(local, names.suffix))
        load_local_mcp_config(DEFAULT_LOCAL_CONFIG)
    except AcceptanceError as exc:
        primary_error = exc
    finally:
        if drive_cleanup_approved and local is not None and names is not None:
            try:
                asyncio.run(cleanup_matching_test_notebook(local, names.notebook))
            except AcceptanceError as exc:
                cleanup_error = exc

    if cleanup_error is not None:
        primary = f"{primary_error.code};" if primary_error is not None else ""
        assert names is not None
        pytest.fail(
            f"{primary}{cleanup_error.code};manual_cleanup_required={names.notebook}",
            pytrace=False,
        )
    if primary_error is not None:
        pytest.fail(primary_error.code, pytrace=False)

    assert names is not None
    print(f"TEST_CONTEXT_CLEANED={names.notebook}")
    print("PERSISTENT_SWITCHES=false,false")


@pytest.mark.live
def test_manual_notebook_cleanup_verified_live() -> None:
    """Verify manual Notebook cleanup directly through Graph, without Claude."""

    notebook_name = os.getenv("ONENOTE_VERIFY_CLEANUP_NAME", "").strip()
    if not notebook_name:
        pytest.skip("set ONENOTE_VERIFY_CLEANUP_NAME to verify manual cleanup")
    try:
        local = run_base_preflight(DEFAULT_LOCAL_CONFIG)
        if not asyncio.run(notebook_is_absent(local, notebook_name)):
            pytest.fail("manual_cleanup_pending", pytrace=False)
    except AcceptanceError as exc:
        pytest.fail(exc.code, pytrace=False)

import json
import os
import stat
import sys
import uuid
from pathlib import Path

import pytest

from tests import test_agent_acceptance_live as acceptance


def _client_id() -> str:
    return str(uuid.UUID(int=0))


def _write_local_config(
    path: Path,
    *,
    writes: str = "false",
    deletes: str = "false",
    cache: str = "true",
    extra: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (
                "[mcp_servers.onenote.env]",
                f'AZURE_CLIENT_ID = "{_client_id()}"',
                f'ONENOTE_CACHE_TOKENS = "{cache}"',
                f'ONENOTE_ENABLE_WRITES = "{writes}"',
                f'ONENOTE_ENABLE_DELETES = "{deletes}"',
                extra,
            )
        ),
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)


def _local(path: Path) -> acceptance.LocalMcpConfig:
    _write_local_config(path)
    return acceptance.load_local_mcp_config(path)


def _trace(phase: acceptance.Phase) -> str:
    events = []
    for index, tool_name in enumerate(sorted(phase.required_calls)):
        events.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": f"tool-{index}",
                            "name": f"mcp__onenote__{tool_name}",
                            "input": {},
                        }
                    ]
                },
            }
        )
    events.append(
        {
            "type": "result",
            "result": f"PHASE_RESULT={phase.name}:PASS:{phase.expected_code}",
        }
    )
    return "\n".join(json.dumps(event) for event in events)


def test_local_config_requires_private_file_and_disabled_persistent_switches(tmp_path):
    path = tmp_path / "config.toml"
    config = _local(path)

    assert config.client_id == _client_id()
    assert config.cache_tokens is True
    assert config.writes_enabled is False
    assert config.deletes_enabled is False
    assert config.source_path == path

    if os.name != "nt":
        path.chmod(0o644)
        with pytest.raises(acceptance.AcceptanceError) as permissions:
            acceptance.load_local_mcp_config(path)
        assert permissions.value.code == "local_config_permissions"

    _write_local_config(path, writes="true")
    with pytest.raises(acceptance.AcceptanceError) as switches:
        acceptance.load_local_mcp_config(path)
    assert switches.value.code == "persistent_safety_switches_not_false"


def test_local_config_rejects_client_secret_anywhere(tmp_path):
    path = tmp_path / "config.toml"
    secret_key = "AZURE_CLIENT_" + "SECRET"
    sensitive_fixture = "fixture-" + "must-not-leak"
    _write_local_config(path, extra=f'{secret_key} = "{sensitive_fixture}"')

    with pytest.raises(acceptance.AcceptanceError) as error:
        acceptance.load_local_mcp_config(path)

    assert error.value.code == "client_secret_forbidden"
    assert sensitive_fixture not in str(error.value)


def test_authorizations_are_required_before_run():
    with pytest.raises(acceptance.AcceptanceError) as provider:
        acceptance.ensure_authorizations(provider_data=False, writes=True, drive_cleanup=True)
    assert provider.value.code == "provider_data_authorization_required"

    with pytest.raises(acceptance.AcceptanceError) as writes:
        acceptance.ensure_authorizations(provider_data=True, writes=False, drive_cleanup=True)
    assert writes.value.code == "write_authorization_required"

    with pytest.raises(acceptance.AcceptanceError) as cleanup:
        acceptance.ensure_authorizations(provider_data=True, writes=True, drive_cleanup=False)
    assert cleanup.value.code == "drive_cleanup_authorization_required"

    acceptance.ensure_authorizations(provider_data=True, writes=True, drive_cleanup=True)


def test_files_control_reuses_encrypted_mcp_cache_but_not_production_scopes(tmp_path):
    local = _local(tmp_path / "config.toml")
    control_settings, control_auth = acceptance._control_auth(local)
    production_settings = acceptance._settings(local)

    assert control_settings.cache_path == production_settings.cache_path == acceptance.TOKEN_CACHE_PATH
    assert control_auth.requested_scopes == acceptance.LIVE_CONTROL_SCOPES
    assert not any("Files." in scope for scope in acceptance.SCOPES)


def test_temporary_config_is_private_and_uses_phase_specific_switches(tmp_path):
    local = _local(tmp_path / "config.toml")
    phase = acceptance.PHASES["notebook"]

    with acceptance.temporary_mcp_config(local, phase, uv_command="/safe/uv") as config_path:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        env = payload["mcpServers"]["onenote"]["env"]

        assert env["AZURE_CLIENT_ID"] == local.client_id
        assert env["ONENOTE_ENABLE_WRITES"] == "true"
        assert env["ONENOTE_ENABLE_DELETES"] == "false"
        assert "AZURE_CLIENT_SECRET" not in env
        assert all("Files.ReadWrite" not in str(value) for value in payload.values())
        if os.name != "nt":
            assert stat.S_IMODE(config_path.stat().st_mode) == 0o600

    assert not config_path.exists()


def test_claude_command_is_strict_nonpersistent_and_minimally_allowlisted(tmp_path):
    phase = acceptance.PHASES["guard"]
    config_path = tmp_path / "mcp.json"
    command = acceptance.build_claude_command(
        claude_command="claude",
        config_path=config_path,
        phase=phase,
        prompt="safe prompt",
    )

    assert "--strict-mcp-config" in command
    assert "--no-session-persistence" in command
    assert "dontAsk" in command
    assert "stream-json" in command
    allowed = command[command.index("--allowedTools") + 1].split(",")
    assert set(allowed) == {f"mcp__onenote__{name}" for name in phase.allowed_tools}
    assert _client_id() not in command


def test_agent_prompts_explicitly_refuse_files_and_delegate_cleanup_locally():
    names = acceptance._test_names()
    prompts = (
        acceptance._guard_prompt(names.notebook),
        acceptance._notebook_prompt(names.notebook),
        acceptance._section_prompt(names.notebook, names.section),
        acceptance._page_prompt(names.notebook, names.section, names.page, names.suffix),
        acceptance._update_prompt(names.notebook, names.section, names.page, names.suffix),
    )

    for prompt in prompts:
        assert "不得请求 Files 权限" in prompt
        assert "Drive/原始 Graph" in prompt
        assert "本地 pytest 独立执行" in prompt
        assert "target_not_visible" in prompt
        assert "不得在原因码或其他输出中加入资源名称、ID、响应正文或认证信息" in prompt


def test_agent_trace_requires_real_tool_coverage_and_fixed_marker():
    phase = acceptance.PHASES["guard"]
    acceptance.validate_agent_trace(acceptance.CommandResult(0, _trace(phase), ""), phase)

    incomplete = "\n".join(_trace(phase).splitlines()[1:])
    with pytest.raises(acceptance.AcceptanceError) as error:
        acceptance.validate_agent_trace(acceptance.CommandResult(0, incomplete, "sensitive raw output"), phase)
    assert error.value.code == "agent_guard_missing_check_authentication"
    assert "sensitive" not in str(error.value)

    reported_failure = json.dumps(
        {"type": "result", "result": "PHASE_RESULT=guard:FAIL:target_not_visible"}
    )
    with pytest.raises(acceptance.AcceptanceError) as reported:
        acceptance.validate_agent_trace(
            acceptance.CommandResult(0, reported_failure, "sensitive raw output"),
            phase,
        )
    assert reported.value.code == "agent_guard_reported_target_not_visible"
    assert "sensitive" not in str(reported.value)

    untrusted_failure = json.dumps(
        {"type": "result", "result": "PHASE_RESULT=guard:FAIL:private_secret"}
    )
    with pytest.raises(acceptance.AcceptanceError) as invalid:
        acceptance.validate_agent_trace(acceptance.CommandResult(0, untrusted_failure, ""), phase)
    assert invalid.value.code == "agent_guard_failure_code_invalid"


def test_realtime_runner_prints_only_sanitized_progress_and_retains_trace(capsys):
    sensitive = "private-tool-result-must-not-be-printed"
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "private-tool-id",
                    "name": "mcp__onenote__check_authentication",
                    "input": {"private": sensitive},
                }
            ]
        },
    }
    script = (
        "import json,sys;"
        f"print(json.dumps({event!r}));"
        f"print({sensitive!r}, file=sys.stderr)"
    )

    result = acceptance._default_command_runner(
        [sys.executable, "-c", script],
        acceptance.PROJECT_ROOT,
        30,
    )
    captured = capsys.readouterr()

    assert result.returncode == 0
    assert sensitive in result.stdout
    assert sensitive in result.stderr
    assert captured.out.strip() == "AGENT_TOOL_CALL=check_authentication"
    assert sensitive not in captured.out
    assert captured.err == ""

    invalid_result = json.dumps(
        {"type": "result", "result": "PHASE_RESULT=guard:FAIL:private_secret"}
    )
    assert acceptance._safe_progress_events(invalid_result) == (
        "AGENT_RESULT=guard:FAIL:failure_code_invalid",
    )


def test_execute_agent_phase_runs_preflight_before_claude(monkeypatch, tmp_path):
    local = _local(tmp_path / "config.toml")
    phase = acceptance.PHASES["guard"]
    events: list[str] = []

    monkeypatch.setattr(acceptance, "_require_command", lambda name: name)

    def preflight(config_path, checked_local, checked_phase):
        assert config_path.exists()
        assert checked_local is local
        assert checked_phase is phase
        events.append("preflight")

    def runner(command, cwd, timeout):
        assert events == ["preflight"]
        assert command[0] == "claude"
        assert cwd == acceptance.PROJECT_ROOT
        assert timeout == 30
        events.append("claude")
        return acceptance.CommandResult(0, _trace(phase), "")

    acceptance.execute_agent_phase(
        local=local,
        phase=phase,
        prompt="safe prompt",
        runner=runner,
        preflight=preflight,
        timeout=30,
    )

    assert events == ["preflight", "claude"]


def test_claude_mcp_preflight_captures_details_without_leaking_values():
    sensitive_value = "do-not-echo-this-value"

    def connected_runner(command, cwd, timeout):
        assert cwd == acceptance.PROJECT_ROOT
        assert timeout == 60
        if command[-1] == "list":
            return acceptance.CommandResult(0, "onenote: command - ✔ Connected\n", "")
        return acceptance.CommandResult(
            0,
            f"AZURE_CLIENT_ID: {sensitive_value}\nONENOTE_ENABLE_WRITES: false\nONENOTE_ENABLE_DELETES: false\n",
            "",
        )

    acceptance._check_claude_mcp("claude", connected_runner)

    def unsafe_runner(command, cwd, timeout):
        if command[-1] == "list":
            return acceptance.CommandResult(0, "onenote: command - ✔ Connected\n", "")
        return acceptance.CommandResult(
            0,
            f"AZURE_CLIENT_ID: {sensitive_value}\nONENOTE_ENABLE_WRITES: true\n",
            "",
        )

    with pytest.raises(acceptance.AcceptanceError) as error:
        acceptance._check_claude_mcp("claude", unsafe_runner)
    assert error.value.code == "claude_persistent_writes_enabled"
    assert sensitive_value not in str(error.value)


@pytest.mark.asyncio
async def test_exact_test_notebook_is_deleted_by_local_drive_control_plane(monkeypatch, tmp_path):
    local = _local(tmp_path / "config.toml")
    notebook_name = "MCP-FULL-TOOL-ACCEPTANCE-FIXED"
    state = {"deleted": False}
    calls: list[tuple[str, str | None]] = []

    class NotesGraph:
        async def request_json(self, method, endpoint, **kwargs):
            assert method == "GET"
            assert endpoint == "/me/onenote/notebooks"
            value = [] if state["deleted"] else [{"displayName": notebook_name, "id": "private-note-id"}]
            return {"value": value}

    class DriveGraph:
        async def request_json(self, method, endpoint, **kwargs):
            if method == "GET":
                if "/me/drive/root/search" in endpoint:
                    value = [] if state["deleted"] else [
                        {
                            "id": "private-drive-id",
                            "name": notebook_name,
                            "package": {"type": "oneNote"},
                        }
                    ]
                    return {"value": value}
                assert endpoint.startswith("/me/drive/items/private-drive-id?")
                return {
                    "id": "private-drive-id",
                    "name": notebook_name,
                    "package": {"type": "oneNote"},
                    "eTag": "private-etag",
                }
            assert method == "DELETE"
            assert endpoint == "/me/drive/items/private-drive-id"
            assert kwargs["if_match"] == "private-etag"
            calls.append((method, kwargs["if_match"]))
            state["deleted"] = True
            return {}

    monkeypatch.setattr(acceptance, "_live_components", lambda checked_local: (NotesGraph(), object()))
    monkeypatch.setattr(acceptance, "_control_graph", lambda checked_local: DriveGraph())

    assert await acceptance.cleanup_matching_test_notebook(local, notebook_name) is True
    assert calls == [("DELETE", "private-etag")]


@pytest.mark.asyncio
async def test_drive_cleanup_revalidates_detail_identity_before_delete(monkeypatch, tmp_path):
    local = _local(tmp_path / "config.toml")
    notebook_name = "MCP-FULL-TOOL-ACCEPTANCE-DETAIL-MISMATCH"

    class NotesGraph:
        async def request_json(self, method, endpoint, **kwargs):
            return {"value": [{"displayName": notebook_name, "id": "private-note-id"}]}

    class DriveGraph:
        async def request_json(self, method, endpoint, **kwargs):
            assert method == "GET"
            if "/me/drive/root/search" in endpoint:
                return {
                    "value": [
                        {
                            "id": "private-drive-id",
                            "name": notebook_name,
                            "package": {"type": "oneNote"},
                        }
                    ]
                }
            return {
                "id": "different-private-id",
                "name": notebook_name,
                "package": {"type": "oneNote"},
                "eTag": "private-etag",
            }

    monkeypatch.setattr(acceptance, "_live_components", lambda checked_local: (NotesGraph(), object()))
    monkeypatch.setattr(acceptance, "_control_graph", lambda checked_local: DriveGraph())

    with pytest.raises(acceptance.AcceptanceError) as error:
        await acceptance.cleanup_matching_test_notebook(local, notebook_name)

    assert error.value.code == "drive_cleanup_identity_mismatch"


@pytest.mark.asyncio
async def test_drive_cleanup_rejects_ambiguous_packages_without_delete(monkeypatch, tmp_path):
    local = _local(tmp_path / "config.toml")
    notebook_name = "MCP-FULL-TOOL-ACCEPTANCE-AMBIGUOUS"

    class NotesGraph:
        async def request_json(self, method, endpoint, **kwargs):
            return {"value": [{"displayName": notebook_name, "id": "private-note-id"}]}

    class DriveGraph:
        async def request_json(self, method, endpoint, **kwargs):
            assert method == "GET"
            item = {"name": notebook_name, "package": {"type": "oneNote"}, "eTag": "etag"}
            return {"value": [{**item, "id": "first"}, {**item, "id": "second"}]}

    monkeypatch.setattr(acceptance, "_live_components", lambda checked_local: (NotesGraph(), object()))
    monkeypatch.setattr(acceptance, "_control_graph", lambda checked_local: DriveGraph())

    with pytest.raises(acceptance.AcceptanceError) as error:
        await acceptance.cleanup_matching_test_notebook(local, notebook_name)

    assert error.value.code == "drive_cleanup_match_ambiguous"
    assert "private-note-id" not in str(error.value)


@pytest.mark.asyncio
async def test_drive_cleanup_rejects_unreserved_name_before_any_graph_request(monkeypatch, tmp_path):
    local = _local(tmp_path / "config.toml")

    monkeypatch.setattr(
        acceptance,
        "_live_components",
        lambda checked_local: pytest.fail("Graph must not be initialized for an unreserved name"),
    )
    monkeypatch.setattr(
        acceptance,
        "_control_graph",
        lambda checked_local: pytest.fail("Drive must not be initialized for an unreserved name"),
    )

    with pytest.raises(acceptance.AcceptanceError) as error:
        await acceptance.cleanup_matching_test_notebook(local, "Personal Notes")

    assert error.value.code == "drive_cleanup_name_outside_test_prefix"


@pytest.mark.asyncio
async def test_drive_cleanup_rejects_paginated_search_without_delete(monkeypatch, tmp_path):
    local = _local(tmp_path / "config.toml")
    notebook_name = "MCP-FULL-TOOL-ACCEPTANCE-PAGINATED"

    class NotesGraph:
        async def request_json(self, method, endpoint, **kwargs):
            return {"value": [{"displayName": notebook_name, "id": "private-note-id"}]}

    class DriveGraph:
        async def request_json(self, method, endpoint, **kwargs):
            assert method == "GET"
            return {
                "@odata.nextLink": "private-next-page",
                "value": [
                    {
                        "id": "private-drive-id",
                        "name": notebook_name,
                        "package": {"type": "oneNote"},
                        "eTag": "private-etag",
                    }
                ],
            }

    monkeypatch.setattr(acceptance, "_live_components", lambda checked_local: (NotesGraph(), object()))
    monkeypatch.setattr(acceptance, "_control_graph", lambda checked_local: DriveGraph())

    with pytest.raises(acceptance.AcceptanceError) as error:
        await acceptance.cleanup_matching_test_notebook(local, notebook_name)

    assert error.value.code == "drive_search_pagination_ambiguous"


@pytest.mark.asyncio
async def test_page_cleanup_runs_locally_without_agent(monkeypatch, tmp_path):
    local = _local(tmp_path / "config.toml")
    calls: list[str] = []

    class StubGraph:
        async def request_json(self, method, endpoint):
            calls.append(f"graph:{method}")
            return {"value": []}

    class StubTools:
        async def delete_page(self, page_id, expected_title):
            assert page_id == "private-page-id"
            assert expected_title == "test page"
            calls.append("local:delete_page")
            return json.dumps({"status": "success", "message": "Page deleted."})

    def components(checked_local, *, writes_enabled=False, deletes_enabled=False):
        assert checked_local is local
        assert writes_enabled is True
        assert deletes_enabled is True
        return StubGraph(), StubTools()

    monkeypatch.setattr(acceptance, "_live_components", components)
    resources = acceptance.LiveResources(
        notebook_id="private-notebook-id",
        section_id="private-section-id",
        page_id="private-page-id",
        page_title="test page",
    )

    await acceptance.delete_test_page_locally(local, resources)

    assert calls == ["local:delete_page", "graph:GET"]


@pytest.mark.asyncio
async def test_expected_registry_matches_all_phase_allowlists():
    assert await acceptance._registered_tools() == acceptance.EXPECTED_TOOLS
    assert all(phase.deletes_enabled is False for phase in acceptance.PHASES.values())
    assert all("delete_page" not in phase.allowed_tools for phase in acceptance.PHASES.values())
    assert all("drive" not in tool_name.lower() for tool_name in acceptance.EXPECTED_TOOLS)
    assert not any("Files." in scope for scope in acceptance.SCOPES)
    assert "https://graph.microsoft.com/Files.ReadWrite" in acceptance.LIVE_CONTROL_SCOPES
    assert all(
        phase.allowed_tools.issubset(acceptance.EXPECTED_TOOLS)
        for phase in acceptance.PHASES.values()
    )

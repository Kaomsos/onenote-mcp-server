from onenote_mcp.auth import SCOPES, AuthManager
from onenote_mcp.config import Settings


def _settings(tmp_path):
    return Settings(
        client_id="public-client-id",
        cache_tokens=False,
        writes_enabled=False,
        deletes_enabled=False,
        cache_path=tmp_path / "unused-cache.bin",
    )


def test_production_auth_scopes_never_include_files_permission(tmp_path):
    auth = AuthManager(_settings(tmp_path))

    assert auth.requested_scopes == tuple(SCOPES)
    assert not any("Files." in scope for scope in auth.requested_scopes)


def test_callers_can_isolate_explicit_test_control_scopes(tmp_path):
    test_scopes = (*SCOPES, "https://graph.microsoft.com/Files.ReadWrite")

    auth = AuthManager(_settings(tmp_path), scopes=test_scopes)

    assert auth.requested_scopes == test_scopes
    assert AuthManager(_settings(tmp_path)).requested_scopes == tuple(SCOPES)

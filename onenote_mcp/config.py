"""Runtime configuration without secret persistence."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str, default: bool) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Environment-backed settings for a public-client MCP server."""

    client_id: str | None
    cache_tokens: bool
    writes_enabled: bool
    cache_path: Path
    authority: str = "https://login.microsoftonline.com/common"
    graph_base_url: str = "https://graph.microsoft.com/v1.0"

    @classmethod
    def from_environment(cls) -> "Settings":
        local_app_data = os.getenv("LOCALAPPDATA")
        cache_root = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
        return cls(
            client_id=os.getenv("AZURE_CLIENT_ID"),
            cache_tokens=_as_bool(os.getenv("ONENOTE_CACHE_TOKENS", "true"), True),
            writes_enabled=_as_bool(os.getenv("ONENOTE_ENABLE_WRITES", "false"), False),
            cache_path=cache_root / "onenote-mcp-server" / "msal_token_cache.bin",
        )

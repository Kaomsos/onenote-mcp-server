"""MCP application assembly and command-line entry point."""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from .auth import AuthManager
from .config import Settings
from .graph import GraphClient
from .tools import OneNoteTools, register_tools


def create_server(settings: Settings | None = None) -> FastMCP:
    configured_settings = settings or Settings.from_environment()
    auth = AuthManager(configured_settings)
    graph = GraphClient(configured_settings, auth)
    service = OneNoteTools(configured_settings, auth, graph)
    mcp = FastMCP("OneNote MCP Server")
    register_tools(mcp, service, auth)
    return mcp


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    create_server().run()

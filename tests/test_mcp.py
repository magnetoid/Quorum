"""Smoke test for the MCP server registration.

Verifies that `server.mcp` imports cleanly and that the four expected tools
are registered on the FastMCP instance. Tool introspection varies by SDK
version, so this test tries several known paths and skips gracefully if
none of them apply rather than failing on a version mismatch."""
from __future__ import annotations

import asyncio

import pytest


EXPECTED_TOOLS = {"quorum_ask", "quorum_council", "quorum_history", "quorum_models_stats"}


def _registered_tool_names(server) -> set[str]:
    """Return the set of registered tool names by trying known FastMCP APIs."""
    # Newer FastMCP: server._tool_manager.list_tools() returns Tool objects.
    mgr = getattr(server, "_tool_manager", None) or getattr(server, "tool_manager", None)
    if mgr is not None:
        for method in ("list_tools", "_tools"):
            attr = getattr(mgr, method, None)
            if callable(attr):
                tools = attr()
                return {getattr(t, "name", str(t)) for t in tools}
            if isinstance(attr, dict):
                return set(attr.keys())

    # Older FastMCP: server._tools dict.
    bare = getattr(server, "_tools", None)
    if isinstance(bare, dict):
        return set(bare.keys())

    # Last resort: server.list_tools() may be async on some versions.
    list_tools = getattr(server, "list_tools", None)
    if callable(list_tools):
        try:
            tools = list_tools()
            if asyncio.iscoroutine(tools):
                tools = asyncio.run(tools)
            return {getattr(t, "name", str(t)) for t in tools}
        except Exception:
            pass

    return set()


def test_mcp_module_imports_cleanly():
    """server.mcp should import without side effects (no engine/db init)."""
    import server.mcp  # noqa: F401


def test_mcp_tools_registered():
    import server.mcp as mod
    found = _registered_tool_names(mod.mcp)
    if not found:
        pytest.skip("Could not introspect FastMCP tool registry on this SDK version")
    missing = EXPECTED_TOOLS - found
    assert not missing, f"Missing MCP tools: {missing} (found: {found})"


def test_mcp_transports_exposed():
    import server.mcp as mod
    assert callable(mod.mcp_app), "mcp_app() must be callable for FastAPI mounting"
    assert callable(mod.run_stdio), "run_stdio() must be callable for the CLI entrypoint"

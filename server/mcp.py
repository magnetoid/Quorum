"""MCP server for Quorum.

Exposes the consensus engine as an MCP tool surface so sibling projects
(Morpheus, ClearCount, Alethia, OpenClaw) can call Quorum without bespoke
HTTP plumbing. Two transports:

  * `mcp_app()`   — SSE ASGI app, mounted by `server.api` at `/mcp`.
                    Used by HTTP-capable MCP clients via `quorum serve`.
  * `run_stdio()` — stdio transport for local agents (Claude Code, Claude
                    Desktop, Cursor). Invoked by the `quorum mcp` CLI command.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from config import load_config
from core.engine import Engine
from core.reputation import ReputationManager
from storage.db import DB

mcp = FastMCP("quorum")

# Lazy state — built on first tool call so module import stays cheap.
_state: Dict[str, Any] = {}


async def _get_engine_and_db():
    if "engine" not in _state:
        cfg = load_config()
        db = DB()
        await db.init_db()
        _state["config"] = cfg
        _state["db"] = db
        _state["engine"] = Engine(cfg, db)
    return _state["engine"], _state["db"]


@mcp.tool()
async def quorum_ask(
    question: str,
    domain: str = "default",
    budget: float = 0.05,
    models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Submit a question to the council and return the aggregated consensus.

    Returns the full consensus result: consensus text, confidence, disputed
    zone (if any), per-agent votes, domain, cost, and query_id.
    """
    engine, db = await _get_engine_and_db()
    result = await engine.run(
        prompt=question,
        domain=domain,
        budget=budget,
        override_models=models,
    )
    await db.save_history(
        query_id=result["query_id"],
        prompt=question,
        domain=result["domain"],
        consensus=result["consensus"],
        disputed_flag=result["disputed_flag"],
        cost=result["cost"],
    )
    return result


@mcp.tool()
async def quorum_council(
    question: str,
    domain: str = "default",
    budget: float = 0.05,
    models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run the council and return raw per-model responses without aggregation.

    Useful when the *caller* is itself a model that wants to do its own
    synthesis over the raw council output instead of trusting Quorum's
    voting layer. Does not write to history.
    """
    engine, _ = await _get_engine_and_db()
    result = await engine.run(
        prompt=question,
        domain=domain,
        budget=budget,
        override_models=models,
    )
    return {
        "query_id": result["query_id"],
        "domain": result["domain"],
        "agents": result["agents"],
        "cost": result["cost"],
    }


@mcp.tool()
async def quorum_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent queries from the local SQLite history."""
    _, db = await _get_engine_and_db()
    return await db.get_history(limit=limit)


@mcp.tool()
async def quorum_models_stats(domain: str = "default") -> Dict[str, float]:
    """Return reputation scores per model for the given domain."""
    _, db = await _get_engine_and_db()
    rm = ReputationManager(db)
    return await rm.get_scores(domain)


def mcp_app():
    """ASGI app for HTTP+SSE transport. Mount on FastAPI at `/mcp`."""
    return mcp.sse_app()


def run_stdio() -> None:
    """Run MCP over stdio. Entrypoint for `quorum mcp` (local agents)."""
    mcp.run()

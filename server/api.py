"""Quorum HTTP surface.

Three endpoints:

  * `GET  /healthz`              — liveness probe + provider summary
  * `POST /api/ask`              — Quorum-native shape, returns the full
                                   consensus result (see schema in README)
  * `POST /v1/chat/completions`  — OpenAI-compatible router. Drop-in for any
                                   client expecting an OpenAI API; the
                                   `model` field selects council strategy

Plus the MCP SSE app mounted at `/mcp`. The OpenAI-compatible endpoint
returns the standard OpenAI shape, with an extra top-level `quorum` field
carrying the full consensus result (disputed zones, per-agent votes,
confidence, cost) so power users get more than just the bare consensus
text without breaking OpenAI-style consumers."""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from config import load_config
from core.engine import Engine
from storage.db import DB

from contextlib import asynccontextmanager

# API Key security
API_KEY_NAME = "X-Quorum-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    expected_key = os.environ.get("QUORUM_API_KEY")
    if not expected_key:
        return "" # No auth configured
    if api_key_header == expected_key:
        return api_key_header
    # Fallback to Bearer token for OpenAI compatibility
    raise HTTPException(
        status_code=403, detail="Could not validate API key"
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    yield

app = FastAPI(
    title="Quorum API",
    description="Consensus reasoning engine — REST + OpenAI-compatible router + MCP.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS open by default for ease of integration. Tighten via config or a
# reverse proxy if deploying outside localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = load_config()
db = DB()
engine = Engine(config, db)


# ── Schemas ─────────────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    prompt: str
    domain: str = "default"
    budget: float = 0.05
    models: Optional[List[str]] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False  # Streaming not yet supported; ignored.


# ── Liveness + REST ─────────────────────────────────────────────────────────


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "quorum",
        "version": "0.1.0",
        "providers_enabled": [name for name, p in config.providers.items() if p.enabled],
    }


@app.post("/api/ask")
async def ask(req: AskRequest) -> Dict[str, Any]:
    try:
        result = await engine.run(
            prompt=req.prompt,
            domain=req.domain,
            budget=req.budget,
            override_models=req.models,
        )
        await db.save_history(
            query_id=result["query_id"],
            prompt=req.prompt,
            domain=result["domain"],
            consensus=result["consensus"],
            disputed_flag=result["disputed_flag"],
            cost=result["cost"],
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── OpenAI-compatible router ────────────────────────────────────────────────


def _parse_model_spec(model: str) -> Tuple[str, Optional[List[str]]]:
    """Parse the `model` field of a `/v1/chat/completions` request.

    Returns `(domain, override_models)`.

        "quorum"                       → ("default", None)
        "quorum:code"                  → ("code", None)
        "quorum:m1,m2,m3"              → ("default", [m1, m2, m3])
        "quorum:code:m1,m2"            → ("code", [m1, m2])
        "ollama/llama3.2" (or other)   → ("default", ["ollama/llama3.2"])
    """
    if model == "quorum":
        return ("default", None)
    if model.startswith("quorum:"):
        spec = model[len("quorum:"):]
        if not spec:
            return ("default", None)
        if ":" in spec:
            domain_part, _, models_part = spec.partition(":")
            return (domain_part or "default",
                    [m.strip() for m in models_part.split(",") if m.strip()])
        if "," in spec or "/" in spec:
            return ("default", [m.strip() for m in spec.split(",") if m.strip()])
        return (spec, None)
    # Single-model passthrough.
    return ("default", [model])


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest) -> Dict[str, Any]:
    """OpenAI-compatible chat-completions router.

    Point any OpenAI-compatible client at this endpoint and select a council
    via the `model` field. The response uses the standard OpenAI shape so
    drop-in works (LangChain, llm CLI, Open WebUI, etc.). The top-level
    `quorum` field exposes the full consensus result for callers that
    want the disputed zone, per-agent votes, and cost breakdown.
    """
    user_messages = [m.content for m in req.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(
            status_code=400,
            detail="messages must contain at least one user message",
        )

    # Honor caller-provided system messages by prepending them to the prompt.
    # The engine separately injects a domain persona from config; both can
    # apply.
    system_msgs = [m.content for m in req.messages if m.role == "system"]
    prompt = user_messages[-1]
    if system_msgs:
        prompt = "\n".join(system_msgs) + "\n\n" + prompt

    domain, override_models = _parse_model_spec(req.model)
    budget = 0.05  # TODO: pluggable via custom header

    try:
        result = await engine.run(
            prompt=prompt,
            domain=domain,
            budget=budget,
            override_models=override_models,
        )
        await db.save_history(
            query_id=result["query_id"],
            prompt=prompt,
            domain=result["domain"],
            consensus=result["consensus"],
            disputed_flag=result["disputed_flag"],
            cost=result["cost"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    total_in = sum(int(a.get("input_tokens", 0)) for a in result.get("agents", []))
    total_out = sum(int(a.get("output_tokens", 0)) for a in result.get("agents", []))

    return {
        "id": f"chatcmpl-{result['query_id']}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["consensus"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": total_in,
            "completion_tokens": total_out,
            "total_tokens": total_in + total_out,
        },
        "quorum": {
            "consensus": result["consensus"],
            "disputed": result.get("disputed", ""),
            "disputed_flag": result.get("disputed_flag", False),
            "confidence": result.get("confidence", 0.0),
            "agents": result.get("agents", []),
            "domain": result.get("domain"),
            "query_id": result["query_id"],
            "cost": result.get("cost", "$0.0000"),
        },
    }


# Mount the MCP server (SSE transport) so HTTP-capable MCP clients can reach
# it at /mcp alongside the REST endpoints. Stdio transport for local agents
# is exposed separately via the `quorum mcp` CLI command.
from server.mcp import mcp_app  # noqa: E402  (deferred to avoid circular import)
app.mount("/mcp", mcp_app())

"""Quorum HTTP surface.

Endpoints:

  * `GET  /healthz`              — liveness probe + provider summary
  * `POST /api/ask`              — Quorum-native shape, returns the full
                                   consensus result
  * `POST /v1/chat/completions`  — OpenAI-compatible router
  * `POST /graphql`              — typed GraphQL API

Plus the MCP SSE app mounted at `/mcp`.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, Header, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict

from config import load_config
from core.engine import Engine
from storage.db import DB


# API Key security. If QUORUM_API_KEY is unset, auth is disabled for local dev.
# When set, clients may authenticate either with X-Quorum-Key or the
# OpenAI-compatible Authorization: Bearer <key> header.
API_KEY_NAME = "X-Quorum-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def _env_csv(name: str, default: str) -> List[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def get_api_key(
    api_key_header: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(default=None),
) -> str:
    expected_key = os.environ.get("QUORUM_API_KEY")
    if not expected_key:
        return ""  # No auth configured; useful for local development.

    if api_key_header == expected_key:
        return api_key_header

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip() == expected_key:
            return token.strip()

    raise HTTPException(status_code=403, detail="Could not validate API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    yield


app = FastAPI(
    title="Quorum API",
    description="Consensus reasoning engine — REST + OpenAI-compatible router + GraphQL + MCP.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS defaults are local-dev friendly, but production deployments should set:
# QUORUM_ALLOWED_ORIGINS="https://app.example.com,https://admin.example.com"
allowed_origins = _env_csv(
    "QUORUM_ALLOWED_ORIGINS",
    "http://localhost,http://localhost:3000,http://localhost:5173,http://localhost:8000,http://localhost:8080,http://127.0.0.1,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8000,http://127.0.0.1:8080",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", API_KEY_NAME],
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
    stream: Optional[bool] = False


# ── Shared execution helpers ────────────────────────────────────────────────


async def _run_and_save(
    prompt: str,
    domain: str = "default",
    budget: float = 0.05,
    override_models: Optional[List[str]] = None,
) -> Dict[str, Any]:
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
    return result


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
        spec = model[len("quorum:") :]
        if not spec:
            return ("default", None)
        if ":" in spec:
            domain_part, _, models_part = spec.partition(":")
            return (
                domain_part or "default",
                [m.strip() for m in models_part.split(",") if m.strip()],
            )
        if "," in spec or "/" in spec:
            return ("default", [m.strip() for m in spec.split(",") if m.strip()])
        return (spec, None)
    # Single-model passthrough.
    return ("default", [model])


def _chat_response(req: ChatCompletionRequest, result: Dict[str, Any]) -> Dict[str, Any]:
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


def _chat_sse_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_chat_response(req: ChatCompletionRequest, result: Dict[str, Any]):
    """OpenAI-compatible SSE stream.

    This currently streams the completed consensus in one delta. It gives OpenAI
    clients a compatible streaming transport while true token-level provider
    streaming is added underneath later.
    """
    created = int(time.time())
    chunk_id = f"chatcmpl-{result['query_id']}"
    content = result.get("consensus", "")

    yield _chat_sse_event(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": req.model,
            "choices": [
                {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
            ],
        }
    )
    yield _chat_sse_event(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": req.model,
            "choices": [
                {"index": 0, "delta": {"content": content}, "finish_reason": None}
            ],
            "quorum": {
                "confidence": result.get("confidence", 0.0),
                "disputed_flag": result.get("disputed_flag", False),
                "domain": result.get("domain"),
                "query_id": result.get("query_id"),
                "cost": result.get("cost", "$0.0000"),
            },
        }
    )
    yield _chat_sse_event(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": req.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
    )
    yield "data: [DONE]\n\n"


# ── Liveness + REST ─────────────────────────────────────────────────────────


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "quorum",
        "version": "0.1.0",
        "surfaces": ["rest", "openai-compatible", "graphql", "mcp"],
        "providers_enabled": [name for name, p in config.providers.items() if p.enabled],
    }


@app.post("/api/ask", dependencies=[Depends(get_api_key)])
async def ask(req: AskRequest) -> Dict[str, Any]:
    try:
        return await _run_and_save(
            prompt=req.prompt,
            domain=req.domain,
            budget=req.budget,
            override_models=req.models,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── OpenAI-compatible router ────────────────────────────────────────────────


@app.post("/v1/chat/completions", dependencies=[Depends(get_api_key)])
async def chat_completions(
    req: ChatCompletionRequest,
    x_quorum_budget: Optional[float] = Header(None, alias="X-Quorum-Budget"),
):
    """OpenAI-compatible chat-completions router.

    Supports normal JSON responses and OpenAI-style SSE when `stream=true`.
    """
    user_messages = [m.content for m in req.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(
            status_code=400,
            detail="messages must contain at least one user message",
        )

    system_msgs = [m.content for m in req.messages if m.role == "system"]
    prompt = user_messages[-1]
    if system_msgs:
        prompt = "\n".join(system_msgs) + "\n\n" + prompt

    domain, override_models = _parse_model_spec(req.model)
    budget = x_quorum_budget if x_quorum_budget is not None else 0.05

    try:
        result = await _run_and_save(
            prompt=prompt,
            domain=domain,
            budget=budget,
            override_models=override_models,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if req.stream:
        return StreamingResponse(
            _stream_chat_response(req, result),
            media_type="text/event-stream",
        )

    return _chat_response(req, result)


# Mount GraphQL and MCP after REST routes so import-time work stays isolated.
from server.graphql import graphql_app  # noqa: E402
from server.mcp import mcp_app  # noqa: E402  (deferred to avoid circular import)

app.include_router(graphql_app(engine, db), prefix="/graphql")
app.mount("/mcp", mcp_app())

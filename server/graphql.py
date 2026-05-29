"""GraphQL API surface for Quorum.

Mounted by `server.api` at `/graphql`. It exposes the same core engine flow as
REST and MCP, while giving frontend/backend clients typed selection sets.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import strawberry
from fastapi import Request
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from core.engine import Engine
from storage.db import DB


@strawberry.type
class AgentResult:
    model: str
    response: str
    vote: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


@strawberry.type
class AskResult:
    consensus: str
    confidence: float
    disputed: str
    disputed_flag: bool
    domain: str
    query_id: str
    cost: str
    agents: List[AgentResult]


@strawberry.type
class HistoryItem:
    query_id: str
    prompt: str
    domain: str
    consensus: str
    disputed_flag: bool
    cost: str


@strawberry.type
class ModelScore:
    model: str
    score: float


def _agent_from_dict(agent: Dict[str, Any]) -> AgentResult:
    return AgentResult(
        model=str(agent.get("model", "")),
        response=str(agent.get("response", "")),
        vote=str(agent.get("vote", "")),
        input_tokens=int(agent.get("input_tokens", 0) or 0),
        output_tokens=int(agent.get("output_tokens", 0) or 0),
        cost=float(agent.get("cost", 0.0) or 0.0),
    )


def _ask_result_from_dict(result: Dict[str, Any]) -> AskResult:
    return AskResult(
        consensus=str(result.get("consensus", "")),
        confidence=float(result.get("confidence", 0.0) or 0.0),
        disputed=str(result.get("disputed", "")),
        disputed_flag=bool(result.get("disputed_flag", False)),
        domain=str(result.get("domain", "default")),
        query_id=str(result.get("query_id", "")),
        cost=str(result.get("cost", "$0.0000")),
        agents=[_agent_from_dict(a) for a in result.get("agents", [])],
    )


async def _run_and_save(
    engine: Engine,
    db: DB,
    prompt: str,
    domain: str = "default",
    budget: float = 0.05,
    models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    result = await engine.run(
        prompt=prompt,
        domain=domain,
        budget=budget,
        override_models=models,
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


@strawberry.type
class Query:
    @strawberry.field
    async def health(self, info: Info) -> str:
        return "ok"

    @strawberry.field
    async def history(self, info: Info, limit: int = 20) -> List[HistoryItem]:
        db: DB = info.context["db"]
        rows = await db.get_history(limit=limit)
        return [
            HistoryItem(
                query_id=str(row["query_id"]),
                prompt=str(row["prompt"]),
                domain=str(row["domain"]),
                consensus=str(row["consensus"]),
                disputed_flag=bool(row["disputed_flag"]),
                cost=str(row["cost"]),
            )
            for row in rows
        ]

    @strawberry.field
    async def model_scores(self, info: Info, domain: str = "default") -> List[ModelScore]:
        db: DB = info.context["db"]
        scores = await db.get_reputation(domain)
        return [
            ModelScore(model=model, score=float(score))
            for model, score in sorted(scores.items(), key=lambda item: item[0])
        ]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def ask(
        self,
        info: Info,
        prompt: str,
        domain: str = "default",
        budget: float = 0.05,
        models: Optional[List[str]] = None,
    ) -> AskResult:
        engine: Engine = info.context["engine"]
        db: DB = info.context["db"]
        result = await _run_and_save(
            engine=engine,
            db=db,
            prompt=prompt,
            domain=domain,
            budget=budget,
            models=models,
        )
        return _ask_result_from_dict(result)


schema = strawberry.Schema(query=Query, mutation=Mutation)


def graphql_app(engine: Engine, db: DB) -> GraphQLRouter:
    def get_context(request: Request) -> Dict[str, Any]:
        return {"engine": engine, "db": db}

    return GraphQLRouter(schema, context_getter=get_context)  # type: ignore

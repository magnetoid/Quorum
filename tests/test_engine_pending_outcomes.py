from __future__ import annotations

import pytest

from config import AppConfig
from core.engine import Engine
from adapters.base import AdapterResponse
from storage.db import DB


@pytest.mark.asyncio
async def test_engine_does_not_record_pending_outcomes_when_disputed(tmp_path):
    db = DB(db_path=str(tmp_path / "test.db"))
    await db.init_db()

    models = ["ollama/a", "ollama/b"]
    cfg = AppConfig(
        domains={"factual": models},
        personas={"default": "", "factual": ""},
    )
    engine = Engine(cfg, db)

    async def fake_ask(model: str, system: str, prompt: str):
        if model.endswith("/a"):
            return (model, AdapterResponse(content="apple", cost=0.0), 0.1)
        return (model, AdapterResponse(content="banana", cost=0.0), 0.1)
    engine._ask_model = fake_ask  # type: ignore[method-assign]

    result = await engine.run(
        prompt="x",
        domain="factual",
        budget=1.0,
        override_models=models,
    )

    assert result["disputed_flag"] is True
    assert await db.get_pending_outcomes(result["query_id"]) == []


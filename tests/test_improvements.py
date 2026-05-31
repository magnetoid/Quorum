"""Tests for the research-driven quick-win improvements:

1. Semantic-entropy uncertainty signal in the voting engine.
2. Selective-prediction abstention in the engine.
3. Opt-in embedding-kNN routing fallback.
"""
from __future__ import annotations

import pytest

from config import AppConfig
from core.engine import Engine
from core.router import Router
from core.voting import VotingEngine, _normalized_entropy
from adapters.base import AdapterResponse
from storage.db import DB


# ── 1. Entropy ───────────────────────────────────────────────────────────────


def test_normalized_entropy_bounds():
    assert _normalized_entropy([]) == 0.0
    assert _normalized_entropy([5.0]) == 0.0          # single cluster -> agreement
    assert _normalized_entropy([1.0, 1.0]) == pytest.approx(1.0)   # even 2-way split
    # A lopsided split is less uncertain than an even one.
    assert _normalized_entropy([9.0, 1.0]) < _normalized_entropy([1.0, 1.0])


def test_entropy_zero_when_unanimous():
    engine = VotingEngine()
    result = engine.aggregate(
        {"m1": "The answer is 42.", "m2": "The answer is 42.", "m3": "The answer is 42."},
        "factual",
    )
    assert result["entropy"] == 0.0
    assert not result["disputed_flag"]


def test_entropy_positive_when_split():
    engine = VotingEngine()
    result = engine.aggregate(
        {"m1": "Yes, definitely.", "m2": "No, never.", "m3": "Maybe, it depends."},
        "factual",
    )
    assert 0.0 < result["entropy"] <= 1.0


def test_entropy_present_on_all_paths():
    engine = VotingEngine()
    assert engine.aggregate({}, "factual")["entropy"] == 0.0                      # empty
    assert engine.aggregate({"m": "Error: x"}, "factual")["entropy"] == 0.0        # all-error
    assert engine.aggregate({"m": "hello"}, "factual")["entropy"] == 0.0           # sole


# ── 2. Abstention ────────────────────────────────────────────────────────────


def _disputing_engine(tmp_path):
    db = DB(db_path=str(tmp_path / "t.db"))
    cfg = AppConfig(domains={"factual": ["m/a", "m/b", "m/c"]}, personas={"default": "", "factual": ""})
    engine = Engine(cfg, db)

    answers = {"m/a": "Yes, absolutely.", "m/b": "No, certainly not.", "m/c": "It depends entirely."}

    async def fake_ask(model, system, prompt):
        return (model, AdapterResponse(content=answers[model], cost=0.0), 0.1)

    engine._ask_model = fake_ask  # type: ignore[method-assign]
    return db, engine


@pytest.mark.asyncio
async def test_engine_abstains_below_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("QUORUM_ABSTAIN_CONFIDENCE", "0.9")
    monkeypatch.setenv("QUORUM_DELIBERATION", "off")
    db, engine = _disputing_engine(tmp_path)
    await db.init_db()

    result = await engine.run("Is X true?", domain="factual", budget=1.0,
                              override_models=["m/a", "m/b", "m/c"])

    assert result["disputed_flag"] is True
    assert result["abstained"] is True
    assert "insufficient consensus" in result["consensus"].lower()
    # Abstained (disputed) results are not cached and earn no reputation deltas.
    assert await db.get_pending_outcomes(result["query_id"]) == []


@pytest.mark.asyncio
async def test_engine_does_not_abstain_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("QUORUM_ABSTAIN_CONFIDENCE", raising=False)
    monkeypatch.setenv("QUORUM_DELIBERATION", "off")
    db, engine = _disputing_engine(tmp_path)
    await db.init_db()

    result = await engine.run("Is X true?", domain="factual", budget=1.0,
                              override_models=["m/a", "m/b", "m/c"])

    assert result["disputed_flag"] is True
    assert result["abstained"] is False
    assert "Models disagreed" in result["consensus"]


# ── 3. Opt-in embedding-kNN routing ──────────────────────────────────────────


def test_semantic_routing_off_by_default(monkeypatch):
    monkeypatch.delenv("QUORUM_SEMANTIC_ROUTING", raising=False)
    router = Router(AppConfig())
    # Keyword-less prompt still defaults to the factual catch-all (old behavior).
    assert router.classify_domain("What is the capital of France?") == "factual"


def test_semantic_routing_keyword_still_wins(monkeypatch):
    monkeypatch.setenv("QUORUM_SEMANTIC_ROUTING", "on")
    router = Router(AppConfig())
    # Keyword path runs first and is unaffected by the kNN fallback.
    assert router.classify_domain("Help me debug this Python code") == "code"


def _patch_embeddings(monkeypatch, mapping_fn):
    """Patch voting.get_semantic_embeddings with a deterministic, torch-free stub
    and reset the router's exemplar cache. Returns a cleanup the test should call.

    These tests must not depend on a heavy/fragile embedding model, so we inject
    controlled vectors and exercise the kNN selection + floor logic directly.
    """
    import core.voting as voting
    from core.router import _exemplar_matrix
    monkeypatch.setenv("QUORUM_SEMANTIC_ROUTING", "on")
    monkeypatch.setattr(voting, "get_semantic_embeddings", mapping_fn)
    _exemplar_matrix.cache_clear()
    return _exemplar_matrix.cache_clear


def test_semantic_routing_selects_nearest_exemplar(monkeypatch):
    from core.router import _DOMAIN_EXEMPLARS
    domain_axis = {d: i for i, d in enumerate(_DOMAIN_EXEMPLARS)}
    dim = len(domain_axis)
    text_domain = {ex: d for d, exs in _DOMAIN_EXEMPLARS.items() for ex in exs}

    def embed(texts):
        # One orthonormal axis per domain. Unknown text (the probe) -> architecture.
        out = []
        for t in texts:
            vec = [0.0] * dim
            vec[domain_axis[text_domain.get(t, "architecture")]] = 1.0
            out.append(vec)
        return out

    cleanup = _patch_embeddings(monkeypatch, embed)
    try:
        router = Router(AppConfig())
        # No keyword matches; kNN routes to the nearest exemplar's domain, NOT factual.
        assert router.classify_domain("an utterly novel keyword-free request") == "architecture"
    finally:
        cleanup()


def test_semantic_routing_falls_back_to_factual_when_embeddings_unavailable(monkeypatch):
    # This mirrors the real behavior when sentence-transformers is missing/broken.
    cleanup = _patch_embeddings(monkeypatch, lambda texts: None)
    try:
        router = Router(AppConfig())
        assert router.classify_domain("an utterly novel keyword-free request") == "factual"
    finally:
        cleanup()

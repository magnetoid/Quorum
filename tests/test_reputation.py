"""Reputation feedback loop: pending outcomes → apply_feedback → reputation table.

Tests use a per-test SQLite path under tmp_path so they don't touch quorum.db."""
from __future__ import annotations

import pytest

from storage.db import DB


async def _setup_db(tmp_path) -> DB:
    db = DB(db_path=str(tmp_path / "test.db"))
    await db.init_db()
    return db


async def test_save_and_get_pending_outcomes(tmp_path):
    db = await _setup_db(tmp_path)
    deltas = [("model1", "code", 1.0), ("model2", "code", -1.0)]
    await db.save_pending_outcomes("q1", deltas)
    rows = await db.get_pending_outcomes("q1")
    assert sorted(rows) == sorted(deltas)


async def test_apply_feedback_positive_applies_deltas(tmp_path):
    db = await _setup_db(tmp_path)
    await db.save_pending_outcomes("q1", [
        ("model1", "code", 1.0),
        ("model2", "code", -1.0),
    ])
    assert await db.apply_feedback("q1", 1.0) is True
    assert await db.get_reputation("code") == {"model1": 1.0, "model2": -1.0}
    assert await db.get_pending_outcomes("q1") == []


async def test_apply_feedback_negative_flips_deltas(tmp_path):
    db = await _setup_db(tmp_path)
    await db.save_pending_outcomes("q1", [
        ("model1", "code", 1.0),
        ("model2", "code", -1.0),
    ])
    assert await db.apply_feedback("q1", -1.0) is True
    assert await db.get_reputation("code") == {"model1": -1.0, "model2": 1.0}


async def test_apply_feedback_zero_clears_without_updating(tmp_path):
    db = await _setup_db(tmp_path)
    await db.save_pending_outcomes("q1", [("model1", "code", 1.0)])
    assert await db.apply_feedback("q1", 0.0) is True
    assert await db.get_reputation("code") == {}
    assert await db.get_pending_outcomes("q1") == []


async def test_apply_feedback_unknown_id_returns_false(tmp_path):
    db = await _setup_db(tmp_path)
    assert await db.apply_feedback("nope", 1.0) is False


async def test_apply_feedback_scaled_by_magnitude(tmp_path):
    db = await _setup_db(tmp_path)
    await db.save_pending_outcomes("q1", [("model1", "code", 1.0)])
    await db.apply_feedback("q1", 0.5)
    rep = await db.get_reputation("code")
    assert rep["model1"] == pytest.approx(0.5)


async def test_repeated_feedback_accumulates(tmp_path):
    db = await _setup_db(tmp_path)
    await db.save_pending_outcomes("q1", [("model1", "code", 1.0)])
    await db.apply_feedback("q1", 1.0)
    await db.save_pending_outcomes("q2", [("model1", "code", 1.0)])
    await db.apply_feedback("q2", 1.0)
    rep = await db.get_reputation("code")
    assert rep["model1"] == pytest.approx(2.0)


async def test_feedback_per_domain_isolated(tmp_path):
    """A model's reputation in `code` doesn't leak into `legal`."""
    db = await _setup_db(tmp_path)
    await db.save_pending_outcomes("q1", [("model1", "code", 1.0)])
    await db.apply_feedback("q1", 1.0)
    assert await db.get_reputation("code") == {"model1": 1.0}
    assert await db.get_reputation("legal") == {}

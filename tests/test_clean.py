"""Tests for `quorum clean` table-clearing logic.

Verifies that each --flag clears its target table and reports the row count,
that --all clears all three tables, and that missing-DB is handled cleanly."""
from __future__ import annotations

import asyncio


from cli.clean import _clear_table, run_clean
from storage.db import DB


async def _seed(db_path: str):
    db = DB(db_path=db_path)
    await db.init_db()
    await db.save_history("q1", "p1", "code", "answer1", False, "$0.001")
    await db.save_history("q2", "p2", "code", "answer2", True, "$0.002")
    await db.save_pending_outcomes("q1", [("m1", "code", 1.0), ("m2", "code", -1.0)])
    await db.update_reputation("m1", "code", 1.0)


def test_clear_history_returns_row_count(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("QUORUM_DB_PATH", db_path)
    asyncio.run(_seed(db_path))
    n = asyncio.run(_clear_table("history"))
    assert n == 2
    # Other tables untouched
    db = DB(db_path=db_path)
    pending = asyncio.run(db.get_pending_outcomes("q1"))
    assert len(pending) == 2
    rep = asyncio.run(db.get_reputation("code"))
    assert rep == {"m1": 1.0}


def test_clear_pending_returns_row_count(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("QUORUM_DB_PATH", db_path)
    asyncio.run(_seed(db_path))
    n = asyncio.run(_clear_table("pending_outcomes"))
    assert n == 2
    db = DB(db_path=db_path)
    assert asyncio.run(db.get_pending_outcomes("q1")) == []


def test_clear_reputation_returns_row_count(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("QUORUM_DB_PATH", db_path)
    asyncio.run(_seed(db_path))
    n = asyncio.run(_clear_table("reputation"))
    assert n == 1
    db = DB(db_path=db_path)
    assert asyncio.run(db.get_reputation("code")) == {}


def test_clear_table_handles_missing_db(tmp_path, monkeypatch):
    """No DB file ⇒ no-op, returns 0, doesn't crash."""
    monkeypatch.setenv("QUORUM_DB_PATH", str(tmp_path / "doesnotexist.db"))
    n = asyncio.run(_clear_table("history"))
    assert n == 0


def test_run_clean_no_flags_returns_1(tmp_path, monkeypatch):
    """Calling without any flag prints help and returns non-zero."""
    monkeypatch.setenv("QUORUM_DB_PATH", str(tmp_path / "test.db"))
    code = run_clean()
    assert code == 1


def test_run_clean_all_yes_clears_everything(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("QUORUM_DB_PATH", db_path)
    asyncio.run(_seed(db_path))
    code = run_clean(all_flag=True, yes=True)
    assert code == 0
    db = DB(db_path=db_path)
    assert asyncio.run(db.get_pending_outcomes("q1")) == []
    assert asyncio.run(db.get_reputation("code")) == {}


def test_run_clean_single_flag_leaves_others_intact(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("QUORUM_DB_PATH", db_path)
    asyncio.run(_seed(db_path))
    code = run_clean(history=True, yes=True)
    assert code == 0
    db = DB(db_path=db_path)
    # reputation untouched
    assert asyncio.run(db.get_reputation("code")) == {"m1": 1.0}
    # pending untouched
    assert len(asyncio.run(db.get_pending_outcomes("q1"))) == 2

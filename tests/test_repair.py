"""Tests for `quorum repair` detection and fix flows.

Run each detector + fixer in isolation using tmp_path so we don't touch
the real .env / config.yaml / quorum.db."""
from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path

import pytest
import yaml

from cli import repair as r
from storage.db import DB


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    """Run each test from a tmp dir so the module-level Path constants
    (which are relative) resolve to tmp paths."""
    monkeypatch.chdir(tmp_path)
    # The repair module also reads QUORUM_DB_PATH, default 'quorum.db' in CWD.
    monkeypatch.delenv("QUORUM_DB_PATH", raising=False)
    # Patch module-level Path constants to the new cwd.
    monkeypatch.setattr(r, "ENV_PATH", Path(".env"))
    monkeypatch.setattr(r, "CONFIG_PATH", Path("config.yaml"))
    return tmp_path


def test_detect_missing_db(isolated_cwd):
    issue = r._check_db()
    assert issue.detected is True
    assert "missing" in issue.name.lower() or "missing" in issue.detail.lower()


def test_fix_missing_db_creates_tables(isolated_cwd):
    issue = r._check_db()
    assert issue.detected
    issue.fix()
    # All required tables now exist
    conn = sqlite3.connect("quorum.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    assert r.REQUIRED_TABLES.issubset(tables)


def test_detect_corrupted_db(isolated_cwd):
    # Write garbage that is not a valid SQLite file.
    Path("quorum.db").write_bytes(b"not a real sqlite db" * 50)
    issue = r._check_db()
    assert issue.detected is True
    assert "corrupt" in issue.name.lower()


def test_fix_corrupted_db_renames_and_recreates(isolated_cwd):
    Path("quorum.db").write_bytes(b"garbage" * 100)
    issue = r._check_db()
    assert issue.detected
    issue.fix()
    # Original was renamed
    corrupted = [p for p in Path(".").iterdir() if p.name.startswith("quorum.db.corrupted-")]
    assert len(corrupted) == 1
    # New DB has the required tables
    conn = sqlite3.connect("quorum.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    assert r.REQUIRED_TABLES.issubset(tables)


def test_detect_missing_db_tables(isolated_cwd):
    """Existing DB but only some tables — should be flagged."""
    conn = sqlite3.connect("quorum.db")
    conn.execute("CREATE TABLE reputation (model TEXT, domain TEXT, score REAL, PRIMARY KEY (model, domain))")
    conn.commit()
    conn.close()
    issue = r._check_db()
    assert issue.detected is True
    assert "table" in issue.name.lower()


def test_legacy_ollama_host_migrated(isolated_cwd):
    Path(".env").write_text("OLLAMA_HOST=http://localhost:11434\n")
    issue = r._check_env_legacy_keys()
    assert issue.detected is True
    issue.fix()
    new = Path(".env").read_text()
    assert "OLLAMA_BASE_URL=http://localhost:11434" in new
    assert "OLLAMA_HOST=" not in new


def test_no_env_file_is_not_an_issue(isolated_cwd):
    """Missing .env is fine — many users use shell env directly."""
    issue = r._check_env_legacy_keys()
    assert issue.detected is False


def test_missing_config_yaml_detected_unfixable(isolated_cwd):
    issue = r._check_config_yaml()
    assert issue.detected is True
    assert issue.fix is None  # No safe auto-fix


def test_malformed_config_yaml_renamed(isolated_cwd):
    Path("config.yaml").write_text("not: valid: yaml: at: all:\n  - x\n   - y\n  bad")
    issue = r._check_config_yaml()
    assert issue.detected is True
    assert issue.fix is not None
    issue.fix()
    assert not Path("config.yaml").exists()
    broken = [p for p in Path(".").iterdir() if p.name.startswith("config.yaml.broken-")]
    assert len(broken) == 1


def test_providers_in_sync_adds_missing(isolated_cwd):
    """A config.yaml missing some registered providers should get them appended."""
    minimal = {
        "tiers": {},
        "domains": {},
        "personas": {},
        "providers": {
            "ollama": {"enabled": True, "api_key_env": None},
        },
    }
    Path("config.yaml").write_text(yaml.safe_dump(minimal))
    issue = r._check_providers_in_sync()
    assert issue.detected is True
    issue.fix()
    after = yaml.safe_load(Path("config.yaml").read_text())
    # Every registered provider is now in config.yaml, disabled by default.
    from adapters import PROVIDERS
    assert set(after["providers"].keys()) == set(PROVIDERS.keys())
    # Original ollama entry preserved as enabled.
    assert after["providers"]["ollama"]["enabled"] is True


def test_run_repair_non_interactive_clean_state(isolated_cwd):
    """A fresh dir has multiple issues; -y should fix the fixable ones."""
    # No .env, no config.yaml, no quorum.db ⇒ several detected, some fixable.
    code = r.run_repair(non_interactive=True)
    # Returns 0 because no failure occurred (config.yaml missing is unfixable
    # but not a failure — it's a "skipped" item, surfaced to the user).
    assert code == 0
    # DB got created
    assert Path("quorum.db").exists()

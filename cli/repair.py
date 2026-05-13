"""System repair: `quorum repair`.

Detects and offers to fix common issues:
  - SQLite database missing or corrupted, or required tables missing
  - Legacy env keys (`OLLAMA_HOST` instead of `OLLAMA_BASE_URL`)
  - `config.yaml` missing, unparseable, or missing required sections
  - Provider entries in `config.yaml` out of sync with the adapter registry
    (new providers added to the codebase since this config was generated)

Each detected issue is shown in a Rich table, then the user is prompted
before any change is made. Non-destructive by default; corrupted files
are *moved aside* with a timestamped suffix, not deleted."""
from __future__ import annotations

import asyncio
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from adapters import PROVIDERS

console = Console()

ENV_PATH = Path(".env")
CONFIG_PATH = Path("config.yaml")
REQUIRED_TABLES = {"reputation", "history", "pending_outcomes"}
REQUIRED_CONFIG_SECTIONS = ("tiers", "domains", "personas")


@dataclass
class Issue:
    name: str
    detected: bool
    detail: str
    fix: Optional[Callable[[], None]] = None


# ── Detectors ───────────────────────────────────────────────────────────────


def _check_db() -> Issue:
    db_path = os.environ.get("QUORUM_DB_PATH", "quorum.db")
    path = Path(db_path)
    if not path.exists():
        return Issue(
            "Database missing",
            True,
            f"{db_path} not found — will be created on first use",
            fix=lambda: _init_db(db_path),
        )
    try:
        conn = sqlite3.connect(str(path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        return Issue(
            "Database corrupted",
            True,
            f"{db_path}: {e}",
            fix=lambda: _backup_and_recreate_db(db_path),
        )
    missing = REQUIRED_TABLES - tables
    if missing:
        return Issue(
            "Missing DB tables",
            True,
            f"Missing: {', '.join(sorted(missing))}",
            fix=lambda: _init_db(db_path),
        )
    return Issue("Database", False, f"{db_path} ({len(tables)} tables)")


def _check_env_legacy_keys() -> Issue:
    if not ENV_PATH.exists():
        return Issue("Env file", False, "(no .env — that's fine if you use shell env vars)")
    content = ENV_PATH.read_text()
    if "OLLAMA_HOST=" in content and "OLLAMA_BASE_URL=" not in content:
        return Issue(
            "Legacy OLLAMA_HOST in .env",
            True,
            "Adapter reads OLLAMA_BASE_URL; OLLAMA_HOST is ignored",
            fix=lambda: _migrate_env_key("OLLAMA_HOST", "OLLAMA_BASE_URL"),
        )
    return Issue("Env file", False, f"{ENV_PATH.resolve()}")


def _check_config_yaml() -> Issue:
    if not CONFIG_PATH.exists():
        return Issue(
            "config.yaml missing",
            True,
            "Required for `quorum ask` to load tiers, domains, personas",
            fix=None,  # No safe auto-fix; user must run setup.
        )
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    except yaml.YAMLError as e:
        return Issue(
            "config.yaml malformed",
            True,
            str(e).splitlines()[0],
            fix=lambda: _backup_file(CONFIG_PATH),
        )
    missing = [s for s in REQUIRED_CONFIG_SECTIONS if s not in data]
    if missing:
        return Issue(
            "config.yaml missing sections",
            True,
            f"Missing: {', '.join(missing)} — run `quorum setup` to regenerate",
            fix=None,
        )
    return Issue("config.yaml", False, str(CONFIG_PATH.resolve()))


def _check_providers_in_sync() -> Issue:
    if not CONFIG_PATH.exists():
        return Issue("Providers in config.yaml", False, "(config.yaml missing — see other issue)")
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    except yaml.YAMLError:
        return Issue("Providers in config.yaml", False, "(config.yaml malformed — see other issue)")
    cfg_providers = set((data.get("providers") or {}).keys())
    registry_providers = set(PROVIDERS.keys())
    missing = registry_providers - cfg_providers
    if not missing:
        return Issue("Providers in config.yaml", False, f"All {len(registry_providers)} in sync")
    return Issue(
        f"{len(missing)} new provider(s) missing from config.yaml",
        True,
        f"Missing: {', '.join(sorted(missing))} — will be added as disabled",
        fix=lambda: _add_missing_providers(missing),
    )


# ── Fixers ──────────────────────────────────────────────────────────────────


def _init_db(db_path: str) -> None:
    from storage.db import DB
    asyncio.run(DB(db_path=db_path).init_db())


def _backup_and_recreate_db(db_path: str) -> None:
    ts = int(time.time())
    backup = f"{db_path}.corrupted-{ts}"
    shutil.move(db_path, backup)
    console.print(f"  [yellow]Moved corrupted DB to {backup}[/yellow]")
    _init_db(db_path)


def _backup_file(path: Path) -> None:
    ts = int(time.time())
    backup = path.with_suffix(path.suffix + f".broken-{ts}")
    shutil.move(str(path), str(backup))
    console.print(f"  [yellow]Moved {path} to {backup}[/yellow]")


def _migrate_env_key(old: str, new: str) -> None:
    content = ENV_PATH.read_text()
    content = content.replace(f"{old}=", f"{new}=")
    ENV_PATH.write_text(content)


def _add_missing_providers(missing: set[str]) -> None:
    data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    providers = data.setdefault("providers", {})
    for name in missing:
        spec = PROVIDERS[name]
        providers[name] = {"enabled": False, "api_key_env": spec.get("api_key_env")}
        if "base_url" in spec:
            providers[name]["base_url"] = spec["base_url"]
    with CONFIG_PATH.open("w") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)


# ── Entry point ─────────────────────────────────────────────────────────────


def run_repair(non_interactive: bool = False) -> int:
    console.print(Panel.fit(
        "[bold green]Quorum repair[/bold green]\n"
        "[dim]Detects common config / database issues and offers to fix them.\n"
        "Non-destructive — corrupted files are renamed, never deleted.[/dim]",
        border_style="green",
    ))

    issues: List[Issue] = [
        _check_db(),
        _check_env_legacy_keys(),
        _check_config_yaml(),
        _check_providers_in_sync(),
    ]

    table = Table(title="Repair scan", show_lines=False)
    table.add_column("Check")
    table.add_column("", justify="center")
    table.add_column("Detail", overflow="fold")
    for i in issues:
        status = "[red]✗[/red]" if i.detected else "[green]✓[/green]"
        table.add_row(i.name, status, i.detail)
    console.print(table)

    detected = [i for i in issues if i.detected]
    if not detected:
        console.print("\n[green]✓ Nothing to repair.[/green]")
        return 0

    fixable = [i for i in detected if i.fix is not None]
    unfixable = [i for i in detected if i.fix is None]
    if unfixable:
        console.print("\n[yellow]These need manual action (run `quorum setup`):[/yellow]")
        for i in unfixable:
            console.print(f"  • {i.name} — {i.detail}")

    if not fixable:
        return 1

    console.print(f"\n[bold]{len(fixable)} fixable issue(s).[/bold]")
    fixed = 0
    failed = 0
    for issue in fixable:
        prompt = f"Fix '{issue.name}'?"
        if non_interactive or Confirm.ask(prompt, default=True):
            try:
                if issue.fix:
                    issue.fix()
                console.print(f"  [green]✓[/green] Fixed: {issue.name}")
                fixed += 1
            except Exception as e:
                console.print(f"  [red]✗[/red] Failed: {issue.name} — {type(e).__name__}: {e}")
                failed += 1
        else:
            console.print(f"  [dim]Skipped: {issue.name}[/dim]")

    console.print(f"\n[bold]Repair summary:[/bold] {fixed} fixed, {failed} failed, {len(fixable) - fixed - failed} skipped.")
    return 0 if failed == 0 else 1


def repair_command(
    yes: bool = typer.Option(False, "-y", "--yes", help="Apply all fixes without prompting."),
) -> None:
    raise typer.Exit(code=run_repair(non_interactive=yes))

"""Database and cache cleanup: `quorum clean`.

Selectively clears tables and Python caches. All operations are local and
reversible only by re-asking models; use with care.

Flags:
  --history     Clear `history` table (past queries shown by `quorum history`).
  --pending     Clear `pending_outcomes` (unconfirmed reputation deltas).
  --reputation  Reset `reputation` scores to empty.
  --pycache     Remove __pycache__ / .pytest_cache / .mypy_cache / .ruff_cache.
  --all         All of the above. Asks for confirmation.
  -y / --yes    Skip confirmations.

`quorum clean` with no flag is a no-op that prints usage."""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Callable, List, Tuple, Any

import aiosqlite
import typer
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

console = Console()

CACHE_DIRS = (".pytest_cache", ".mypy_cache", ".ruff_cache")
CODE_DIRS = (".", "core", "adapters", "cli", "server", "storage", "tests")


def _db_path() -> str:
    return os.environ.get("QUORUM_DB_PATH", "quorum.db")


async def _clear_table(table: str) -> int:
    """Delete all rows from `table`. Returns rows-removed count."""
    path = _db_path()
    if not Path(path).exists():
        return 0
    async with aiosqlite.connect(path) as db:
        async with db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
            row = await cursor.fetchone()
            n = int(row[0]) if row else 0
        await db.execute(f"DELETE FROM {table}")
        await db.commit()
    return n


def _clear_pycache() -> int:
    """Remove __pycache__ and tool caches. Returns directories removed."""
    n = 0
    for root in CODE_DIRS:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for path in root_path.rglob("__pycache__"):
            shutil.rmtree(path, ignore_errors=True)
            n += 1
    for cache_dir in CACHE_DIRS:
        p = Path(cache_dir)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            n += 1
    return n


def run_clean(
    history: bool = False,
    pending: bool = False,
    reputation: bool = False,
    pycache: bool = False,
    all_flag: bool = False,
    yes: bool = False,
) -> int:
    if all_flag:
        history = pending = reputation = pycache = True

    actions: List[Tuple[str, Callable[[], Any]]] = []
    if history:
        actions.append(("history records", lambda: asyncio.run(_clear_table("history"))))
    if pending:
        actions.append(("pending outcomes", lambda: asyncio.run(_clear_table("pending_outcomes"))))
    if reputation:
        actions.append(("reputation scores", lambda: asyncio.run(_clear_table("reputation"))))
    if pycache:
        actions.append(("Python cache (__pycache__, .pytest_cache, .mypy_cache, .ruff_cache)", _clear_pycache))

    if not actions:
        console.print(
            "[yellow]Nothing selected.[/yellow] Try one of:\n"
            "  [cyan]--history[/cyan]      clear past queries\n"
            "  [cyan]--pending[/cyan]      clear unconfirmed reputation deltas\n"
            "  [cyan]--reputation[/cyan]   reset reputation scores\n"
            "  [cyan]--pycache[/cyan]      clear Python tool caches\n"
            "  [cyan]--all[/cyan]          everything above\n"
            "Add [cyan]-y[/cyan] to skip the confirmation prompt."
        )
        return 1

    table = Table(title="Will clean", show_lines=False)
    table.add_column("Target")
    for name, _ in actions:
        table.add_row(f"• {name}")
    console.print(table)

    if not yes and not Confirm.ask("\nProceed?", default=False):
        console.print("[dim]Cancelled.[/dim]")
        return 0

    for name, fn in actions:
        try:
            n = fn()
            suffix = f" ({n} item(s))" if isinstance(n, int) else ""
            console.print(f"  [green]✓[/green] {name}{suffix}")
        except Exception as e:
            console.print(f"  [red]✗[/red] {name}: {type(e).__name__}: {e}")

    return 0


def clean_command(
    history: bool = typer.Option(False, "--history", help="Clear past query records."),
    pending: bool = typer.Option(False, "--pending", help="Clear unconfirmed reputation deltas."),
    reputation: bool = typer.Option(False, "--reputation", help="Reset reputation scores."),
    pycache: bool = typer.Option(False, "--pycache", help="Clear __pycache__ and tool caches."),
    all_flag: bool = typer.Option(False, "--all", help="Clean everything above."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt."),
) -> None:
    raise typer.Exit(code=run_clean(history, pending, reputation, pycache, all_flag, yes))

import typer
import asyncio
import os
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import load_config
from core.engine import Engine
from storage.db import DB
from cli.setup import setup_command
from cli.doctor import doctor_command

app = typer.Typer(help="Quorum: Consensus reasoning engine")
console = Console()

@app.command()
def ask(
    prompt: str = typer.Argument(..., help="The question to ask"),
    domain: str = typer.Option("default", help="Domain context (e.g. code, finance)"),
    budget: float = typer.Option(0.05, help="Budget for the query"),
    models: Optional[str] = typer.Option(None, help="Comma-separated list of models to use")
):
    """Ask a question and get a consensus from multiple LLMs."""
    try:
        config = load_config()
    except Exception as e:
        console.print(f"[red]Failed to load config: {e}[/red]")
        raise typer.Exit(1)

    # Validate domain — silently routing an unknown domain through the
    # keyword classifier is confusing, so warn loudly.
    if domain != "default" and domain not in config.domains:
        available = ", ".join(sorted(config.domains.keys()))
        console.print(
            f"[yellow]Unknown domain '{domain}'.[/yellow] "
            f"Known domains: {available}. [dim]Falling back to keyword classification.[/dim]"
        )
        domain = "default"

    db = DB()
    engine = Engine(config, db)
    
    async def _run():
        await db.init_db()
        model_list = [m.strip() for m in models.split(",")] if models else None
            
        result = await engine.run(prompt, domain, budget, model_list)
        
        # Save history
        await db.save_history(
            query_id=result["query_id"],
            prompt=prompt,
            domain=result["domain"],
            consensus=result["consensus"],
            disputed_flag=result["disputed_flag"],
            cost=result["cost"]
        )
        
        # Display output
        console.print(f"\n[bold blue]Domain:[/bold blue] {result['domain']}")
        console.print(f"[bold blue]Confidence:[/bold blue] {result['confidence']:.2f}")
        console.print(f"[bold blue]Cost:[/bold blue] {result['cost']}")
        
        if result["disputed_flag"]:
            console.print(Panel(result["disputed"], title="[red]Disputed Zone[/red]", expand=False, border_style="red"))
        
        console.print("\n[bold green]Consensus:[/bold green]")
        console.print(Panel(result["consensus"], expand=False, border_style="green"))
        
        console.print("\n[dim]Agent Responses:[/dim]")
        for agent in result["agents"]:
            console.print(f"- [bold]{agent['model']}[/bold]: {agent['vote']}")
            
        console.print(f"\n[dim]Query ID: {result['query_id']}[/dim]")

    asyncio.run(_run())

@app.command()
def history(limit: int = typer.Option(20, help="Number of recent queries to show.")):
    """View recent query history (read from the local SQLite store)."""
    db = DB()

    async def _run():
        await db.init_db()
        rows = await db.get_history(limit=limit)
        if not rows:
            console.print("[dim]No queries in history yet.[/dim]")
            return
        table = Table(title=f"Recent queries (last {len(rows)})", show_lines=False)
        table.add_column("Query ID", style="dim")
        table.add_column("Domain")
        table.add_column("Disputed", justify="center")
        table.add_column("Cost", justify="right")
        table.add_column("Prompt", overflow="fold")
        for row in rows:
            qid = row["query_id"]
            prompt_preview = row["prompt"][:80] + ("…" if len(row["prompt"]) > 80 else "")
            table.add_row(
                qid[:8] + "…",
                row["domain"],
                "yes" if row["disputed_flag"] else "no",
                row["cost"],
                prompt_preview,
            )
        console.print(table)

    asyncio.run(_run())


@app.command()
def models(
    stats: bool = typer.Option(False, "--stats", help="Show per-(model, domain) reputation."),
):
    """List configured providers; with --stats, show per-(model, domain) reputation."""
    try:
        cfg = load_config()
    except Exception as e:
        console.print(f"[red]Failed to load config: {e}[/red]")
        raise typer.Exit(1)

    if not stats:
        from adapters import PROVIDERS
        table = Table(title="Providers", show_lines=False)
        table.add_column("Provider", style="bold")
        table.add_column("Enabled", justify="center")
        table.add_column("API key")
        for name in PROVIDERS:
            pc = cfg.providers.get(name)
            enabled = "[green]✓[/green]" if (pc and pc.enabled) else "[dim]·[/dim]"
            key_var = (pc.api_key_env if pc else None) or PROVIDERS[name].get("api_key_env")
            if not key_var:
                key_status = "[dim](none required)[/dim]"
            elif os.environ.get(key_var):
                key_status = f"{key_var} [green](set)[/green]"
            else:
                key_status = f"{key_var} [yellow](missing)[/yellow]"
            table.add_row(name, enabled, key_status)
        console.print(table)
        console.print("\n[dim]Re-run with --stats to view per-(model, domain) reputation.[/dim]")
        return

    db = DB()

    async def _run():
        await db.init_db()
        domains = sorted(set(cfg.domains.keys()))
        any_data = False
        for d in domains:
            scores = await db.get_reputation(d)
            if not scores:
                continue
            any_data = True
            table = Table(title=f"Reputation — {d}", show_lines=False)
            table.add_column("Model", style="bold")
            table.add_column("Score", justify="right")
            for m, s in sorted(scores.items(), key=lambda kv: -kv[1]):
                colour = "green" if s > 0 else ("red" if s < 0 else "dim")
                table.add_row(m, f"[{colour}]{s:+.2f}[/{colour}]")
            console.print(table)
        if not any_data:
            console.print(
                "[dim]No reputation data yet. Try:[/dim]\n"
                "  [cyan]quorum ask \"...\"[/cyan]\n"
                "  [cyan]quorum feedback <query_id> --score 1[/cyan]"
            )

    asyncio.run(_run())


@app.command()
def feedback(
    query_id: str = typer.Argument(..., help="The query_id printed by `quorum ask`."),
    score: float = typer.Option(
        ...,
        help="Score in [-1.0, 1.0]. Positive confirms the consensus; negative flips it; 0 drops the pending outcome.",
    ),
):
    """Apply feedback for a past query, updating reputation for each council member."""
    if not -1.0 <= score <= 1.0:
        console.print(f"[red]Score must be between -1.0 and 1.0 (got {score}).[/red]")
        raise typer.Exit(1)
    db = DB()

    async def _run():
        await db.init_db()
        applied = await db.apply_feedback(query_id, score)
        if applied:
            console.print(
                f"[green]✓ Applied feedback for {query_id[:8]}… (score={score:+.2f}).[/green]"
            )
        else:
            console.print(
                f"[yellow]No pending outcomes for {query_id}.[/yellow]\n"
                "[dim]Either the id is wrong, the query was never run, or feedback was already applied.[/dim]"
            )

    asyncio.run(_run())

@app.command()
def serve():
    """Start the REST + MCP server."""
    import uvicorn
    console.print("[green]Starting FastAPI server on port 8000...[/green]")
    uvicorn.run("server.api:app", host="0.0.0.0", port=8000, reload=True)


@app.command()
def setup():
    """Interactive first-run wizard: detect Ollama, store API keys, run a health check."""
    setup_command()


@app.command()
def doctor():
    """Run health checks: Python, Ollama, API keys, config, per-provider ping."""
    doctor_command()


@app.command(name="mcp")
def mcp_cmd():
    """Run Quorum as an MCP server over stdio (for local agent integration).

    Wire it into Claude Code / Claude Desktop / Cursor by adding to that
    host's mcpServers config:
        { "quorum": { "command": "/abs/path/.venv/bin/quorum",
                      "args": ["mcp"] } }
    """
    from server.mcp import run_stdio
    run_stdio()


@app.command(name="config")
def config_cmd():
    """Interactive menu to toggle providers, set councils, budget, thresholds."""
    from cli.config_cmd import config_command
    config_command()


@app.command(name="repair")
def repair_cmd(
    yes: bool = typer.Option(False, "-y", "--yes", help="Apply all fixes without prompting."),
):
    """Detect and offer to fix common config / database issues."""
    from cli.repair import repair_command
    repair_command(yes=yes)


@app.command(name="clean")
def clean_cmd(
    history: bool = typer.Option(False, "--history", help="Clear past query records."),
    pending: bool = typer.Option(False, "--pending", help="Clear unconfirmed reputation deltas."),
    reputation: bool = typer.Option(False, "--reputation", help="Reset reputation scores."),
    pycache: bool = typer.Option(False, "--pycache", help="Clear __pycache__ and tool caches."),
    all_flag: bool = typer.Option(False, "--all", help="Clean everything above."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt."),
):
    """Clear history / pending outcomes / reputation / Python caches."""
    from cli.clean import clean_command
    clean_command(
        history=history,
        pending=pending,
        reputation=reputation,
        pycache=pycache,
        all_flag=all_flag,
        yes=yes,
    )


if __name__ == "__main__":
    app()

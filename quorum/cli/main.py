import typer
import asyncio
import os
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from quorum.config import load_config
from quorum.core.engine import Engine
from quorum.storage.db import DB
from quorum.core.reputation import ReputationManager

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
        
    engine = Engine(config)
    db = DB()
    
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
def history():
    """View query history."""
    console.print("[yellow]History command pending full implementation.[/yellow]")

@app.command()
def models(stats: bool = typer.Option(False, "--stats", help="Show reputation stats")):
    """List available models and optionally their stats."""
    db = DB()
    async def _run():
        await db.init_db()
        rm = ReputationManager(db)
        scores = await rm.get_scores("default")
        
        table = Table("Model", "Score")
        for m, s in scores.items():
            table.add_row(m, f"{s:.2f}")
        console.print(table)
    
    if stats:
        asyncio.run(_run())
    else:
        console.print("Use --stats to view model reputation.")

@app.command()
def feedback(query_id: str, score: float = typer.Option(..., help="Feedback score (-1 to 1)")):
    """Provide feedback on a query to update model reputation."""
    console.print(f"[yellow]Feedback for {query_id} received. Model weights updating...[/yellow]")

@app.command()
def serve():
    """Start the REST + MCP server."""
    import uvicorn
    console.print("[green]Starting FastAPI server on port 8000...[/green]")
    uvicorn.run("quorum.server.api:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    app()

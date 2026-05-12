import typer
import asyncio
import os
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from quorum.config import load_config
from quorum.engine import ConsensusEngine

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
        
    engine = ConsensusEngine(config)
    
    if models:
        model_list = [m.strip() for m in models.split(",")]
    else:
        # Resolve domain to models
        model_list = config.domains.get(domain, config.domains.get("factual", ["ollama/llama3.2"]))
        
    console.print(f"[bold blue]Querying models:[/bold blue] {', '.join(model_list)}")
    
    # Run async engine
    results = asyncio.run(engine.ask_parallel(model_list, domain, prompt))
    
    # Display results
    console.print("\n[bold green]Individual Responses:[/bold green]")
    for model, response in results["responses"].items():
        console.print(Panel(response, title=model, expand=False))
        
    console.print("\n[bold magenta]Consensus:[/bold magenta]")
    console.print(Panel(results["consensus"], title="Aggregated Result", expand=False, border_style="magenta"))

@app.command()
def serve():
    """Start the REST + MCP server (placeholder)."""
    console.print("[yellow]Server functionality is coming soon per project spec.[/yellow]")

if __name__ == "__main__":
    app()

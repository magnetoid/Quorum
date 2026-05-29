"""Interactive configuration: `quorum config`.

Rich-based menu for toggling providers on/off, editing API keys, choosing
the default council, and tuning budget + confidence thresholds. Saves
changes back to config.yaml + .env. Re-runnable any time."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, FloatPrompt, Prompt
from rich.table import Table

from adapters import PROVIDERS
from cli.setup import _read_env_file, _write_env_file

console = Console()

CONFIG_PATH = Path("config.yaml")
ENV_PATH = Path(".env")


def _load_yaml() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(data: Dict[str, Any]) -> None:
    with CONFIG_PATH.open("w") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)


def _ensure_providers(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if "providers" not in cfg or not isinstance(cfg.get("providers"), dict):
        cfg["providers"] = {}
    for name, spec in PROVIDERS.items():
        if name not in cfg["providers"]:
            cfg["providers"][name] = {
                "enabled": False,
                "api_key_env": spec.get("api_key_env"),
            }
    return cfg


def _menu_main() -> str:
    console.print()
    console.print(Panel.fit(
        "[bold green]QUORUM CONFIG[/bold green]\n"
        "[dim]Toggle providers, edit councils, set budget, tune voting thresholds.[/dim]",
        border_style="green",
    ))
    table = Table(show_header=False, box=None)
    table.add_column(style="bold cyan", width=4, justify="right")
    table.add_column(style="bold")
    table.add_column(style="dim")
    table.add_row("[1]", "Providers", "toggle on/off, edit API keys")
    table.add_row("[2]", "Default council", "models that run when no domain is given")
    table.add_row("[3]", "Domain councils", "per-domain model selection")
    table.add_row("[4]", "Budget", "per-query USD cap")
    table.add_row("[5]", "Confidence", "cluster + dispute thresholds")
    table.add_row("[s]", "Save & exit", "")
    table.add_row("[q]", "Quit without saving", "")
    console.print(table)
    return Prompt.ask("\nChoose", choices=["1", "2", "3", "4", "5", "s", "q"], default="s")


def _submenu_providers(cfg: Dict[str, Any], env: Dict[str, str]) -> None:
    while True:
        cfg = _ensure_providers(cfg)
        table = Table(title="Providers", show_lines=False)
        table.add_column("#", justify="right")
        table.add_column("Provider", style="bold")
        table.add_column("Enabled", justify="center")
        table.add_column("API key")
        names: List[str] = list(cfg["providers"].keys())
        for i, name in enumerate(names, 1):
            entry = cfg["providers"][name]
            enabled = "[green]ON[/green]" if entry.get("enabled") else "[dim]off[/dim]"
            env_var = entry.get("api_key_env")
            if env_var:
                val = env.get(env_var) or os.environ.get(env_var)
                key_status = f"{env_var} = …{val[-4:]}" if val else f"{env_var} [yellow](missing)[/yellow]"
            else:
                key_status = "[dim](none required)[/dim]"
            table.add_row(str(i), name, enabled, key_status)
        console.print(table)
        choice = Prompt.ask("\nProvider # to toggle  (k = edit a key, b = back)", default="b")
        if choice == "b":
            return
        if choice == "k":
            env_var = Prompt.ask("Env var to set", default="ANTHROPIC_API_KEY")
            new_val = Prompt.ask(f"Paste {env_var}", password=True, default="")
            if new_val.strip():
                env[env_var] = new_val.strip()
                _write_env_file(ENV_PATH, env)
                console.print(f"[green]✓ Saved {env_var} to .env[/green]")
            continue
        try:
            idx = int(choice) - 1
            name = names[idx]
            cfg["providers"][name]["enabled"] = not cfg["providers"][name].get("enabled", False)
        except (ValueError, IndexError):
            console.print("[red]Invalid choice.[/red]")


def _submenu_council(cfg: Dict[str, Any]) -> None:
    current = cfg.get("default_council") or []
    console.print(f"[dim]Current default council:[/dim] {', '.join(current) or '(uses tiers)'}")
    raw = Prompt.ask("Comma-separated model IDs (blank to leave unchanged)", default=",".join(current))
    if raw.strip():
        cfg["default_council"] = [m.strip() for m in raw.split(",") if m.strip()]


def _submenu_domains(cfg: Dict[str, Any]) -> None:
    domains = cfg.get("domains", {}) or {}
    table = Table(title="Domain councils", show_lines=False)
    table.add_column("Domain", style="bold")
    table.add_column("Models")
    for d, models in domains.items():
        table.add_row(d, ", ".join(models))
    console.print(table)
    d = Prompt.ask("Domain to edit (or 'b' for back)", default="b")
    if d == "b":
        return
    raw = Prompt.ask(f"Models for {d} (comma-separated)", default=",".join(domains.get(d, [])))
    if raw.strip():
        domains[d] = [m.strip() for m in raw.split(",") if m.strip()]
        cfg["domains"] = domains


def _submenu_budget(cfg: Dict[str, Any]) -> None:
    budget = cfg.get("budget", {}) or {}
    cur = float(budget.get("default_per_query", 0.05))
    new = FloatPrompt.ask("Default per-query budget (USD)", default=cur)
    cfg["budget"] = {**budget, "default_per_query": new}


def _submenu_confidence(cfg: Dict[str, Any]) -> None:
    voting = cfg.get("voting", {}) or {}
    cluster = FloatPrompt.ask(
        "Cluster threshold (Jaccard, 0.0–1.0)",
        default=float(voting.get("cluster_threshold", 0.25)),
    )
    dispute = FloatPrompt.ask(
        "Dispute confidence threshold (0.0–1.0)",
        default=float(voting.get("dispute_confidence", 0.66)),
    )
    cfg["voting"] = {"cluster_threshold": cluster, "dispute_confidence": dispute}


def run_config() -> int:
    cfg = _load_yaml()
    cfg = _ensure_providers(cfg)
    env = _read_env_file(ENV_PATH)
    dirty = False

    while True:
        choice = _menu_main()
        if choice == "1":
            _submenu_providers(cfg, env)
            dirty = True
        elif choice == "2":
            _submenu_council(cfg)
            dirty = True
        elif choice == "3":
            _submenu_domains(cfg)
            dirty = True
        elif choice == "4":
            _submenu_budget(cfg)
            dirty = True
        elif choice == "5":
            _submenu_confidence(cfg)
            dirty = True
        elif choice == "s":
            if dirty:
                _save_yaml(cfg)
                console.print(f"[green]✓ Saved {CONFIG_PATH.resolve()}[/green]")
            else:
                console.print("[dim]No changes to save.[/dim]")
            return 0
        elif choice == "q":
            if dirty and not Confirm.ask("Discard unsaved changes?", default=False):
                continue
            console.print("[dim]Quit without saving.[/dim]")
            return 0


def config_command() -> None:
    import typer
    raise typer.Exit(code=run_config())

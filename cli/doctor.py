"""Health check: `quorum doctor`.

Reports on Python, Ollama reachability + installed models, API key presence,
configured tiers/domains/personas, and a per-provider ping. Exits 0 if all
critical checks pass; non-zero otherwise."""
from __future__ import annotations

import asyncio
import os
import platform
import sys

import httpx
import typer
from rich.console import Console
from rich.table import Table

from adapters.base import BaseAdapter
from config import AppConfig, load_config

console = Console()


def _check_python() -> tuple[bool, str]:
    v = sys.version_info
    ok = v.major > 3 or (v.major == 3 and v.minor >= 11)
    return ok, f"{v.major}.{v.minor}.{v.micro} on {platform.system()} {platform.machine()}"


def _check_ollama(base_url: str) -> tuple[str, str]:
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        r.raise_for_status()
        names = [m.get("name", "") for m in (r.json().get("models") or [])]
        return "ok", f"reachable @ {base_url}, {len(names)} model(s): {', '.join(names) or '(none installed)'}"
    except httpx.HTTPError as e:
        return "warn", f"unreachable @ {base_url} ({type(e).__name__})"


def _check_key(var: str) -> tuple[str, str]:
    val = os.environ.get(var, "")
    if not val:
        return "warn", f"{var} not set"
    return "ok", f"{var} set (…{val[-4:]})"


def _badge(status: str) -> str:
    return {
        "ok":   "[green]✓[/green]",
        "warn": "[yellow]–[/yellow]",
        "fail": "[red]✗[/red]",
    }.get(status, "?")


async def _ping(model_id: str, adapter: BaseAdapter, system: str, prompt: str) -> tuple[str, str]:
    resp = await adapter.generate(model_id, system, prompt)
    if resp.error:
        return "fail", resp.error
    text = (resp.content or "").strip().splitlines()[0][:60] if resp.content else "(empty)"
    return "ok", f"{text}  [{resp.input_tokens}/{resp.output_tokens} tok, ${resp.cost:.6f}]"


def _adapter_for(model: str, config: AppConfig) -> tuple[str, BaseAdapter] | None:
    """Return (provider_name, adapter) for `model`, or None if unsupported / no creds / import fails."""
    try:
        if model.startswith("ollama/"):
            from adapters.ollama import OllamaAdapter
            return "ollama", OllamaAdapter(config)
        if "claude" in model:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                return None
            from adapters.anthropic import AnthropicAdapter
            return "anthropic", AnthropicAdapter(config)
        if "gpt" in model or "o3" in model:
            if not os.environ.get("OPENAI_API_KEY"):
                return None
            from adapters.openai import OpenAIAdapter
            return "openai", OpenAIAdapter(config)
        if "gemini" in model or "mistral" in model:
            if not os.environ.get("OPENROUTER_API_KEY"):
                return None
            from adapters.openrouter import OpenRouterAdapter
            return "openrouter", OpenRouterAdapter(config)
    except ImportError:
        return None
    return None


def run_doctor() -> int:
    failed = 0

    try:
        config = load_config()
    except Exception as e:
        console.print(f"[red]✗ Failed to load config.yaml: {e}[/red]")
        return 1

    # ── Environment ───────────────────────────────────────────────
    env_table = Table(title="Environment", show_lines=False)
    env_table.add_column("Check")
    env_table.add_column("")
    env_table.add_column("Detail")

    py_ok, py_detail = _check_python()
    env_table.add_row("Python ≥ 3.11", _badge("ok" if py_ok else "fail"), py_detail)
    if not py_ok:
        failed += 1

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    oll_status, oll_detail = _check_ollama(base_url)
    env_table.add_row("Ollama", _badge(oll_status), oll_detail)

    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        s, d = _check_key(var)
        env_table.add_row(var, _badge(s), d)

    console.print(env_table)

    # ── Configuration ─────────────────────────────────────────────
    cfg_table = Table(title="Configuration", show_lines=False)
    cfg_table.add_column("Item")
    cfg_table.add_column("Value")
    cfg_table.add_row("Tiers", ", ".join(config.tiers.keys()) or "(none)")
    cfg_table.add_row("Domains", ", ".join(sorted(config.domains.keys())) or "(none)")
    cfg_table.add_row("Personas", ", ".join(sorted(config.personas.keys())) or "(none)")
    cfg_table.add_row("Default budget", f"${config.budget.default_per_query:.4f}")
    console.print(cfg_table)

    # ── Per-provider ping ─────────────────────────────────────────
    # Pick one model per provider that has credentials, ping each.
    probes: list[tuple[str, BaseAdapter]] = []
    seen_providers: set[str] = set()
    candidates: list[str] = []
    for tier in config.tiers.values():
        candidates.extend(tier.models)
    for model in candidates:
        bound = _adapter_for(model, config)
        if not bound:
            continue
        provider, adapter = bound
        if provider in seen_providers:
            continue
        seen_providers.add(provider)
        probes.append((model, adapter))

    if not probes:
        console.print("[yellow]No reachable providers — skipping per-adapter ping.[/yellow]")
        return 1

    ping_table = Table(title="Adapter ping", show_lines=False)
    ping_table.add_column("Model")
    ping_table.add_column("")
    ping_table.add_column("Detail")

    system = "Reply with a single word."
    prompt = "Reply with just: ok"

    async def _all() -> list[tuple[str, str]]:
        return await asyncio.gather(*(_ping(m, a, system, prompt) for m, a in probes))

    try:
        results = asyncio.run(_all())
    except Exception as e:
        console.print(f"[red]✗ Ping execution error: {type(e).__name__}: {e}[/red]")
        return 1

    for (model_id, _), (status, detail) in zip(probes, results):
        ping_table.add_row(model_id, _badge(status), detail)
        if status == "fail":
            failed += 1
    console.print(ping_table)

    return 0 if failed == 0 else 1


def doctor_command() -> None:
    raise typer.Exit(code=run_doctor())

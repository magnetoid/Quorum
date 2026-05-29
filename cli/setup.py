"""Interactive setup wizard: `quorum setup`.

Five steps:
  1. Local Ollama detection + recommended-pull suggestions
  2. Provider picker — enable any of 17 providers, paste API keys inline
  3. Persist to .env (keys) and config.yaml (enabled flags)
  4. Health check (delegates to `quorum doctor`)
  5. Done banner

Re-runnable any time. Idempotent: existing .env keys are preserved, current
enable/disable state from config.yaml is shown as the starting point."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import httpx
import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from adapters import PROVIDERS

console = Console()

ENV_PATH = Path(".env")
ENV_EXAMPLE_PATH = Path(".env.example")
CONFIG_PATH = Path("config.yaml")

RECOMMENDED_OLLAMA = ["llama3.2", "qwen2.5-coder"]
COMMON_DEFAULTS = ("ollama", "anthropic", "openai", "openrouter")


# ── .env helpers (also imported by cli.config_cmd, keep stable) ─────────────


def _read_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _write_env_file(path: Path, env: Dict[str, str]) -> None:
    lines = ["# Quorum environment. Generated/updated by `quorum setup`.\n"]
    for k, v in env.items():
        lines.append(f"{k}={v}\n")
    path.write_text("".join(lines))


# ── config.yaml helpers ─────────────────────────────────────────────────────


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


# ── Step renderers ──────────────────────────────────────────────────────────


def _step(n: int, title: str) -> None:
    console.print()
    console.rule(f"[bold green]Step {n}[/bold green] · {title}", align="left")


def _banner() -> None:
    console.print(Panel.fit(
        "[bold green]Quorum setup[/bold green]\n"
        "[dim]Configures Ollama, picks providers, persists API keys, and runs\n"
        "a health check. Re-runnable any time:[/dim] [cyan]quorum setup[/cyan]",
        border_style="green",
    ))


def _probe_ollama(base_url: str) -> tuple[bool, list[str]]:
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        r.raise_for_status()
        names = [m.get("name", "") for m in (r.json().get("models") or [])]
        return True, [n for n in names if n]
    except (httpx.HTTPError, ValueError):
        return False, []


# ── Step 1: Ollama ──────────────────────────────────────────────────────────


def _step_ollama(env: Dict[str, str]) -> None:
    _step(1, "Local Ollama (free tier)")
    base_url = (
        env.get("OLLAMA_BASE_URL")
        or env.get("OLLAMA_HOST")
        or os.environ.get("OLLAMA_BASE_URL")
        or "http://localhost:11434"
    )
    base_url = Prompt.ask("Ollama base URL", default=base_url)
    env["OLLAMA_BASE_URL"] = base_url
    env.pop("OLLAMA_HOST", None)  # migrate away from legacy key

    reachable, models = _probe_ollama(base_url)
    if reachable:
        if models:
            console.print(f"  [green]✓[/green] Ollama reachable — {len(models)} model(s):")
            for m in models:
                console.print(f"      [cyan]{m}[/cyan]")
        else:
            console.print("  [green]✓[/green] Ollama reachable, but no models installed.")
        missing = [m for m in RECOMMENDED_OLLAMA if not any(m in n for n in models)]
        if missing:
            console.print("  [dim]Suggested local models you don't have yet:[/dim]")
            for m in missing:
                console.print(f"      [cyan]ollama pull {m}[/cyan]")
    else:
        console.print(f"  [yellow]![/yellow] Could not reach Ollama at {base_url}.")
        console.print("  [dim]    Install Ollama from https://ollama.com, start it, then re-run setup.[/dim]")
        console.print("  [dim]    Once running, pull recommended models:[/dim]")
        for m in RECOMMENDED_OLLAMA:
            console.print(f"      [cyan]ollama pull {m}[/cyan]")


# ── Step 2: Pick providers ──────────────────────────────────────────────────


PROVIDER_URLS = {
    "ANTHROPIC_API_KEY":   "https://console.anthropic.com/settings/keys",
    "OPENAI_API_KEY":      "https://platform.openai.com/api-keys",
    "OPENROUTER_API_KEY":  "https://openrouter.ai/keys",
    "GEMINI_API_KEY":      "https://aistudio.google.com/app/apikey",
    "COHERE_API_KEY":      "https://dashboard.cohere.com/api-keys",
    "GROQ_API_KEY":        "https://console.groq.com/keys",
    "TOGETHER_API_KEY":    "https://api.together.xyz/settings/api-keys",
    "DEEPSEEK_API_KEY":    "https://platform.deepseek.com/api_keys",
    "FIREWORKS_API_KEY":   "https://fireworks.ai/account/api-keys",
    "MISTRAL_API_KEY":     "https://console.mistral.ai/api-keys",
    "XAI_API_KEY":         "https://console.x.ai/",
    "PERPLEXITY_API_KEY":  "https://www.perplexity.ai/settings/api",
    "ANYSCALE_API_KEY":    "https://app.endpoints.anyscale.com/credentials",
    "CEREBRAS_API_KEY":    "https://cloud.cerebras.ai/platform/keys",
    "HF_API_KEY":          "https://huggingface.co/settings/tokens",
    "AZURE_OPENAI_API_KEY":"https://portal.azure.com/  (your Azure OpenAI resource)",
}


def _render_provider_table(cfg: Dict[str, Any], env: Dict[str, str]) -> list[str]:
    table = Table(show_lines=False, padding=(0, 1))
    table.add_column("#", justify="right", style="bold cyan")
    table.add_column("Provider", style="bold")
    table.add_column("State", justify="center")
    table.add_column("API key", overflow="fold")
    names: list[str] = list(cfg["providers"].keys())
    for i, name in enumerate(names, 1):
        entry = cfg["providers"][name]
        state = "[green]ON[/green]" if entry.get("enabled") else "[dim]off[/dim]"
        env_var = entry.get("api_key_env")
        if env_var:
            val = env.get(env_var) or os.environ.get(env_var)
            key = f"{env_var} = …{val[-4:]}" if val else f"{env_var} [yellow](missing)[/yellow]"
        else:
            key = "[dim](free / local — no key needed)[/dim]"
        table.add_row(str(i), name, state, key)
    console.print(table)
    return names


def _step_pick_providers(cfg: Dict[str, Any], env: Dict[str, str]) -> None:
    _step(2, "Pick providers and paste keys")
    console.print(
        "[dim]Type a number to toggle a provider on/off. Type 'k <num>' to paste\n"
        "an API key (auto-enables that provider). Type 'a' to enable the four\n"
        "common defaults (Ollama + Anthropic + OpenAI + OpenRouter). Type\n"
        "'done' (or just Enter) to move on.[/dim]\n"
    )

    while True:
        names = _render_provider_table(cfg, env)
        action = Prompt.ask(
            "\n[bold]Action[/bold]  [#=toggle | k <#>=set key | a=enable defaults | done]",
            default="done",
        ).strip().lower()

        if action in ("done", "d", "q", "exit", ""):
            return

        if action == "a":
            for n in COMMON_DEFAULTS:
                if n in cfg["providers"]:
                    cfg["providers"][n]["enabled"] = True
            console.print(f"[green]✓ Enabled defaults: {', '.join(COMMON_DEFAULTS)}[/green]")
            continue

        if action.startswith("k"):
            rest = action[1:].strip()
            try:
                idx = int(rest) - 1
                name = names[idx]
            except (ValueError, IndexError):
                console.print("[red]Invalid index. Try 'k 3' or similar.[/red]")
                continue
            env_var = cfg["providers"][name].get("api_key_env")
            if not env_var:
                console.print(f"  [dim]{name} doesn't need a key.[/dim]")
                cfg["providers"][name]["enabled"] = True
                continue
            console.print(f"  [dim]Get a key: {PROVIDER_URLS.get(env_var, '(see provider docs)')}[/dim]")
            new_val = Prompt.ask(f"  Paste {env_var}", password=True, default="")
            if new_val.strip():
                env[env_var] = new_val.strip()
                cfg["providers"][name]["enabled"] = True
                console.print(f"  [green]✓ Saved {env_var} and enabled {name}[/green]")
            else:
                console.print("  [dim]Skipped.[/dim]")
            continue

        try:
            idx = int(action) - 1
            name = names[idx]
            cfg["providers"][name]["enabled"] = not cfg["providers"][name].get("enabled", False)
        except (ValueError, IndexError):
            console.print(
                "[red]Unknown action.[/red] Use a number (toggle), 'k <num>' "
                "(set key), 'a' (defaults), or 'done'."
            )


# ── Steps 3 & 4: persist + doctor ───────────────────────────────────────────


def _step_persist(cfg: Dict[str, Any], env: Dict[str, str]) -> None:
    _step(3, "Persist configuration")
    env.setdefault("QUORUM_CONFIG", "./config.yaml")
    env.setdefault("QUORUM_DB_PATH", "./quorum.db")
    _write_env_file(ENV_PATH, env)
    _save_yaml(cfg)
    console.print(f"  [green]✓[/green] Wrote {ENV_PATH.resolve()}")
    console.print(f"  [green]✓[/green] Wrote {CONFIG_PATH.resolve()}")


def _step_doctor(env: Dict[str, str]) -> int:
    _step(4, "Health check")
    for k, v in env.items():
        if v:
            os.environ[k] = v
    from cli.doctor import run_doctor
    return run_doctor()


# ── Entry points ────────────────────────────────────────────────────────────


def run_setup() -> int:
    _banner()

    env = _read_env_file(ENV_PATH) or _read_env_file(ENV_EXAMPLE_PATH)
    cfg = _ensure_providers(_load_yaml())

    _step_ollama(env)
    _step_pick_providers(cfg, env)
    _step_persist(cfg, env)
    code = _step_doctor(env)

    console.print()
    if code == 0:
        console.print(Panel.fit(
            "[bold green]✓ Quorum is ready.[/bold green]\n"
            "[dim]Try:[/dim]  [cyan]quorum ask \"what is 2+2?\"[/cyan]",
            border_style="green",
        ))
    else:
        console.print(Panel.fit(
            "[bold yellow]Setup finished with warnings.[/bold yellow]\n"
            "[dim]See the health check above. Re-run anytime:[/dim]\n"
            "  [cyan]quorum setup[/cyan]   or   [cyan]quorum doctor[/cyan]   or   [cyan]quorum repair[/cyan]",
            border_style="yellow",
        ))
    return code


def setup_command() -> None:
    raise typer.Exit(code=run_setup())


# Back-compat: legacy single-key prompt helper. Still used by older callers if any.
def _ask_api_key(env: Dict[str, str], var: str, label: str, url: str, default_yes: bool = False) -> None:
    current = env.get(var) or os.environ.get(var) or ""
    if current:
        masked = "…" + current[-4:] if len(current) > 6 else "(set)"
        console.print(f"  [green]✓[/green] {label} key already set ({masked})")
        if Confirm.ask("    Replace it?", default=False):
            new_val = Prompt.ask(f"    Paste {var}", password=True, default="")
            if new_val.strip():
                env[var] = new_val.strip()
        return
    console.print(f"  [dim]{label} keys: {url}[/dim]")
    if Confirm.ask(f"  Add a {label} API key now?", default=default_yes):
        new_val = Prompt.ask(f"    Paste {var}", password=True, default="")
        if new_val.strip():
            env[var] = new_val.strip()

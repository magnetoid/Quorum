"""Smoke tests for every registered adapter.

Two checks per provider:
1. The adapter class constructs without raising, regardless of env state.
2. With its API key unset, generate() returns AdapterResponse(error=...) —
   it should never throw.

No real network calls are made; the missing-key path short-circuits."""
from __future__ import annotations

import pytest

from adapters import PROVIDERS, build_adapter
from adapters.base import AdapterResponse
from config import AppConfig


def _empty_config() -> AppConfig:
    return AppConfig()


@pytest.mark.parametrize("provider", list(PROVIDERS.keys()))
def test_adapter_constructs(provider):
    cfg = _empty_config()
    adapter = build_adapter(provider, cfg)
    assert adapter is not None
    assert hasattr(adapter, "generate")


@pytest.mark.parametrize(
    "provider",
    [p for p, spec in PROVIDERS.items() if spec.get("api_key_env")],
)
async def test_adapter_missing_key_returns_error(provider, monkeypatch):
    spec = PROVIDERS[provider]
    env_var = spec["api_key_env"]
    monkeypatch.delenv(env_var, raising=False)
    if env_var == "GEMINI_API_KEY":
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    cfg = _empty_config()
    adapter = build_adapter(provider, cfg)
    # Defensive: some adapters cache the key at __init__; null it post-hoc too.
    if hasattr(adapter, "api_key"):
        adapter.api_key = ""

    resp = await adapter.generate(f"{provider}/test-model", "system", "prompt")
    assert isinstance(resp, AdapterResponse)
    assert resp.error, f"Expected error from {provider} when {env_var} unset"

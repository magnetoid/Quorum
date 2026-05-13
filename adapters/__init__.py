"""Adapter registry.

Maps provider name → factory metadata. Used by `core.engine` to dispatch a
model id to a provider, by `cli.doctor` to know which providers to ping, and
by `cli.config_cmd` to render the toggle UI.

Add a new provider by appending to PROVIDERS. For OpenAI-schema endpoints
that's a single dict entry — no new adapter file needed."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import AdapterResponse, BaseAdapter

PROVIDERS: Dict[str, Dict[str, Any]] = {
    # Direct adapters (custom request/response shapes)
    "ollama": {
        "factory": "ollama",
        "model_prefix": "ollama/",
        "api_key_env": None,
    },
    "anthropic": {
        "factory": "anthropic",
        "model_prefix": "claude",  # legacy substring; engine handles both
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "factory": "openai",
        "model_prefix": "gpt",
        "api_key_env": "OPENAI_API_KEY",
    },
    "openrouter": {
        "factory": "openrouter",
        "model_prefix": "openrouter/",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    "gemini": {
        "factory": "gemini",
        "model_prefix": "gemini/",
        "api_key_env": "GEMINI_API_KEY",
    },
    "cohere": {
        "factory": "cohere",
        "model_prefix": "cohere/",
        "api_key_env": "COHERE_API_KEY",
    },
    # OpenAI-compatible providers (one shared adapter)
    "groq": {
        "factory": "openai_compat",
        "model_prefix": "groq/",
        "api_key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "together": {
        "factory": "openai_compat",
        "model_prefix": "together/",
        "api_key_env": "TOGETHER_API_KEY",
        "base_url": "https://api.together.xyz/v1",
    },
    "deepseek": {
        "factory": "openai_compat",
        "model_prefix": "deepseek/",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1",
    },
    "fireworks": {
        "factory": "openai_compat",
        "model_prefix": "fireworks/",
        "api_key_env": "FIREWORKS_API_KEY",
        "base_url": "https://api.fireworks.ai/inference/v1",
    },
    "mistral": {
        "factory": "openai_compat",
        "model_prefix": "mistral/",
        "api_key_env": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
    },
    "xai": {
        "factory": "openai_compat",
        "model_prefix": "xai/",
        "api_key_env": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
    },
    "perplexity": {
        "factory": "openai_compat",
        "model_prefix": "perplexity/",
        "api_key_env": "PERPLEXITY_API_KEY",
        "base_url": "https://api.perplexity.ai",
    },
    "anyscale": {
        "factory": "openai_compat",
        "model_prefix": "anyscale/",
        "api_key_env": "ANYSCALE_API_KEY",
        "base_url": "https://api.endpoints.anyscale.com/v1",
    },
    "cerebras": {
        "factory": "openai_compat",
        "model_prefix": "cerebras/",
        "api_key_env": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
    },
    "hf": {
        "factory": "openai_compat",
        "model_prefix": "hf/",
        "api_key_env": "HF_API_KEY",
        "base_url": "https://api-inference.huggingface.co/v1",
    },
    "azure": {
        "factory": "openai_compat",
        "model_prefix": "azure/",
        "api_key_env": "AZURE_OPENAI_API_KEY",
        "base_url": "https://YOUR-RESOURCE.openai.azure.com/openai/v1",
    },
}


def build_adapter(provider: str, config) -> BaseAdapter:
    """Construct the adapter for `provider`. Lazy imports keep startup cheap
    and let users run with only some provider SDKs/keys installed."""
    spec = PROVIDERS[provider]
    factory = spec["factory"]
    overrides = {}
    if hasattr(config, "providers") and config.providers and provider in config.providers:
        pc = config.providers[provider]
        overrides = {"base_url": getattr(pc, "base_url", None)}

    if factory == "ollama":
        from .ollama import OllamaAdapter
        return OllamaAdapter(config)
    if factory == "anthropic":
        from .anthropic import AnthropicAdapter
        return AnthropicAdapter(config)
    if factory == "openai":
        from .openai import OpenAIAdapter
        return OpenAIAdapter(config)
    if factory == "openrouter":
        from .openrouter import OpenRouterAdapter
        return OpenRouterAdapter(config)
    if factory == "gemini":
        from .gemini import GeminiAdapter
        return GeminiAdapter(config)
    if factory == "cohere":
        from .cohere import CohereAdapter
        return CohereAdapter(config)
    if factory == "openai_compat":
        from .openai_compat import OpenAICompatAdapter
        return OpenAICompatAdapter(
            config=config,
            provider=provider,
            base_url=overrides.get("base_url") or spec["base_url"],
            api_key_env=spec["api_key_env"],
            model_prefix=spec["model_prefix"],
        )
    raise ValueError(f"Unknown adapter factory: {factory}")


def provider_for_model(model: str) -> Optional[str]:
    """Map a model id to a provider name. Tries prefix match first
    (`groq/llama-3.3-70b` → groq), then legacy substring match for
    backwards-compat with un-prefixed names like `claude-sonnet`."""
    # Prefix match (preferred)
    for name, spec in PROVIDERS.items():
        prefix = spec["model_prefix"]
        if prefix.endswith("/") and model.startswith(prefix):
            return name
    # Legacy substring fallback
    if "claude" in model:
        return "anthropic"
    if "gpt" in model or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
        return "openai"
    if "gemini" in model:
        return "gemini"
    if "command" in model or "cohere" in model:
        return "cohere"
    return None


__all__ = [
    "AdapterResponse",
    "BaseAdapter",
    "PROVIDERS",
    "build_adapter",
    "provider_for_model",
]

"""Generic OpenAI-compatible chat adapter.

Most newer LLM providers expose a `/v1/chat/completions` endpoint with the
same request/response schema as OpenAI's. This adapter parameterises host
and credential so a single class covers Groq, Together, DeepSeek, Fireworks,
Mistral, xAI, Perplexity, Anyscale, Azure OpenAI, HuggingFace Inference,
and Cerebras. Model IDs use a `provider/model` prefix that gets stripped
before the API call."""
from __future__ import annotations

import os

import httpx

from .base import AdapterResponse, BaseAdapter
from config import AppConfig


class OpenAICompatAdapter(BaseAdapter):
    def __init__(
        self,
        config: AppConfig,
        provider: str,
        base_url: str,
        api_key_env: str,
        model_prefix: str = "",
        timeout: float = 60.0,
    ):
        self.config = config
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.api_key = os.getenv(api_key_env, "")
        self.model_prefix = model_prefix
        self.timeout = timeout

    def _api_model(self, model: str) -> str:
        if self.model_prefix and model.startswith(self.model_prefix):
            return model[len(self.model_prefix):]
        return model

    async def generate(self, model: str, system_prompt: str, prompt: str) -> AdapterResponse:
        if not self.api_key:
            return AdapterResponse(content="", error=f"Error: {self.api_key_env} not set")

        api_model = self._api_model(model)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": api_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                usage = data.get("usage", {}) or {}
                input_tokens = int(usage.get("prompt_tokens", 0) or 0)
                output_tokens = int(usage.get("completion_tokens", 0) or 0)

                pricing = self.config.pricing.get(model)
                cost = 0.0
                if pricing:
                    cost = (input_tokens * pricing.input + output_tokens * pricing.output) / 1000.0

                return AdapterResponse(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                )
            except Exception as e:
                return AdapterResponse(content="", error=f"Error from {self.provider} ({model}): {e}")

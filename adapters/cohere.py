"""Cohere Chat adapter (v2 API).

Cohere v2 uses an OpenAI-style messages array but a different response shape
(`message.content` is a list of typed parts, usage is under
`usage.billed_units`)."""
from __future__ import annotations

import os

import httpx

from .base import AdapterResponse, BaseAdapter
from config import AppConfig


class CohereAdapter(BaseAdapter):
    BASE_URL = "https://api.cohere.com/v2/chat"

    def __init__(self, config: AppConfig, timeout: float = 60.0):
        self.config = config
        self.api_key = os.getenv("COHERE_API_KEY", "")
        self.timeout = timeout

    async def generate(self, model: str, system_prompt: str, prompt: str) -> AdapterResponse:
        if not self.api_key:
            return AdapterResponse(content="", error="Error: COHERE_API_KEY not set")

        api_model = model[len("cohere/"):] if model.startswith("cohere/") else model
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.BASE_URL,
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
                msg = data.get("message", {}) or {}
                parts = msg.get("content", []) or []
                content = "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()

                usage = (data.get("usage", {}) or {}).get("billed_units", {}) or {}
                input_tokens = int(usage.get("input_tokens", 0) or 0)
                output_tokens = int(usage.get("output_tokens", 0) or 0)

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
                return AdapterResponse(content="", error=f"Error from Cohere ({model}): {e}")

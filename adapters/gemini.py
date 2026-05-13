"""Google Generative AI adapter (Gemini family).

Gemini's REST shape differs from OpenAI: `:generateContent` endpoint with
`systemInstruction` + `contents` arrays, and `usageMetadata` for tokens."""
from __future__ import annotations

import os

import httpx

from .base import AdapterResponse, BaseAdapter
from config import AppConfig


from typing import Dict, Any, List

class GeminiAdapter(BaseAdapter):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, config: AppConfig, timeout: float = 60.0):
        self.config = config
        self.api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        self.timeout = timeout

    async def generate(self, model: str, system_prompt: str, prompt: str) -> AdapterResponse:
        if not self.api_key:
            return AdapterResponse(content="", error="Error: GEMINI_API_KEY (or GOOGLE_API_KEY) not set")

        api_model = model[len("gemini/"):] if model.startswith("gemini/") else model
        # Send the key in an HTTP header (`x-goog-api-key`) rather than in
        # the URL query string, so it doesn't leak into access logs, proxy
        # traces, or browser history. Both forms are supported by the API;
        # header is the safe choice.
        url = f"{self.BASE_URL}/models/{api_model}:generateContent"
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        body: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
                cands = data.get("candidates", []) or []
                content = ""
                if cands:
                    parts = cands[0].get("content", {}).get("parts", []) or []
                    content = "".join(p.get("text", "") for p in parts).strip()

                usage = data.get("usageMetadata", {}) or {}
                input_tokens = int(usage.get("promptTokenCount", 0) or 0)
                output_tokens = int(usage.get("candidatesTokenCount", 0) or 0)

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
                return AdapterResponse(content="", error=f"Error from Gemini ({model}): {e}")

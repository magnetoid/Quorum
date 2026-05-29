"""Generic OpenAI-compatible chat adapter.

Most newer LLM providers expose a `/v1/chat/completions` endpoint with the
same request/response schema as OpenAI's. This adapter parameterises host
and credential so a single class covers Groq, Together, DeepSeek, Fireworks,
Mistral, xAI, Perplexity, Anyscale, Azure OpenAI, HuggingFace Inference,
and Cerebras. Model IDs use a `provider/model` prefix that gets stripped
before the API call.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import httpx

from .base import AdapterResponse, BaseAdapter
from config import AppConfig

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def _safe_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %.2f", name, raw, default)
        return default


def _safe_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


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
        self.timeout = _safe_float_env("QUORUM_PROVIDER_TIMEOUT", timeout)
        self.max_retries = max(0, _safe_int_env("QUORUM_PROVIDER_RETRIES", 2))
        self.backoff_base = max(0.0, _safe_float_env("QUORUM_PROVIDER_BACKOFF_BASE", 0.5))
        self.max_connections = max(1, _safe_int_env("QUORUM_PROVIDER_MAX_CONNECTIONS", 100))
        self.max_keepalive = max(1, _safe_int_env("QUORUM_PROVIDER_MAX_KEEPALIVE", 20))
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    def _api_model(self, model: str) -> str:
        if self.model_prefix and model.startswith(self.model_prefix):
            return model[len(self.model_prefix) :]
        return model

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None and not self._client.is_closed:
            return self._client
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    timeout=self.timeout,
                    limits=httpx.Limits(
                        max_connections=self.max_connections,
                        max_keepalive_connections=self.max_keepalive,
                    ),
                )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _payload(api_model: str, system_prompt: str, prompt: str) -> Dict[str, Any]:
        return {
            "model": api_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }

    def _retry_delay(self, attempt: int, response: Optional[httpx.Response] = None) -> float:
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    return min(float(retry_after), 10.0)
                except ValueError:
                    pass
        return min(self.backoff_base * (2 ** attempt), 10.0)

    async def _post_with_retries(
        self,
        client: httpx.AsyncClient,
        api_model: str,
        system_prompt: str,
        prompt: str,
    ) -> httpx.Response:
        last_exc: Optional[Exception] = None
        url = f"{self.base_url}/chat/completions"

        for attempt in range(self.max_retries + 1):
            response: Optional[httpx.Response] = None
            try:
                response = await client.post(
                    url,
                    headers=self._headers(),
                    json=self._payload(api_model, system_prompt, prompt),
                )
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response
                last_exc = httpx.HTTPStatusError(
                    f"Retryable status code {response.status_code}",
                    request=response.request,
                    response=response,
                )
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if isinstance(exc, httpx.HTTPStatusError):
                    status = exc.response.status_code
                    if status not in _RETRYABLE_STATUS_CODES:
                        raise
            except Exception:
                raise

            if attempt < self.max_retries:
                delay = self._retry_delay(attempt, response)
                logger.warning(
                    "Retrying %s request for %s after %.2fs (attempt %s/%s): %s",
                    self.provider,
                    api_model,
                    delay,
                    attempt + 1,
                    self.max_retries,
                    last_exc,
                )
                await asyncio.sleep(delay)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("provider request failed without an exception")

    async def generate(self, model: str, system_prompt: str, prompt: str) -> AdapterResponse:
        if not self.api_key:
            return AdapterResponse(content="", error=f"Error: {self.api_key_env} not set")

        api_model = self._api_model(model)
        client = await self._get_client()
        try:
            response = await self._post_with_retries(client, api_model, system_prompt, prompt)
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

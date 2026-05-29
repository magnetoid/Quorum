"""Optional Redis response cache for Quorum.

Enabled only when REDIS_URL is set. The cache stores full engine results keyed
by normalized prompt/domain/model selection, reducing duplicate provider calls.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


class ResponseCache:
    def __init__(self) -> None:
        self.redis_url = os.getenv("REDIS_URL", "").strip()
        self.ttl_seconds = max(1, _env_int("QUORUM_CACHE_TTL_SECONDS", 3600))
        self.prefix = os.getenv("QUORUM_CACHE_PREFIX", "quorum:response:v1")
        self._client = None
        self._disabled = not bool(self.redis_url)

    @property
    def enabled(self) -> bool:
        return not self._disabled

    async def _get_client(self):
        if self._disabled:
            return None
        if self._client is not None:
            return self._client
        try:
            from redis.asyncio import Redis  # type: ignore
        except Exception as e:
            logger.info("Redis cache disabled: redis package unavailable: %s", e)
            self._disabled = True
            return None
        try:
            self._client = Redis.from_url(self.redis_url, decode_responses=True)
            await self._client.ping()
            return self._client
        except Exception as e:
            logger.warning("Redis cache disabled: connection failed: %s", e)
            self._disabled = True
            self._client = None
            return None

    def key(
        self,
        prompt: str,
        domain: str = "default",
        budget: float = 0.05,
        override_models: Optional[list[str]] = None,
    ) -> str:
        payload = {
            "prompt": prompt.strip(),
            "domain": domain,
            "budget": round(float(budget), 6),
            "models": sorted(override_models or []),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return f"{self.prefix}:{digest}"

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        client = await self._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            if isinstance(data, dict):
                data["cache_hit"] = True
                return data
        except Exception as e:
            logger.warning("Redis cache read failed: %s", e)
        return None

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        client = await self._get_client()
        if client is None:
            return
        try:
            payload = dict(value)
            payload["cache_hit"] = False
            await client.set(key, json.dumps(payload, ensure_ascii=False), ex=self.ttl_seconds)
        except Exception as e:
            logger.warning("Redis cache write failed: %s", e)

    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass

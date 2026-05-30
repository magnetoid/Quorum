"""Prompt response cache (exact-match, Redis-backed, optional).

This is an **exact-match** cache: it keys on a stable SHA-256 hash of the
``(domain, prompt)`` pair. Despite the historical ``SemanticCache`` name it is
*not* a semantic (vector-similarity) cache — true embedding-similarity caching
needs a vector index (e.g. RediSearch) and is tracked on the roadmap. The class
is named ``PromptCache``; ``SemanticCache`` remains as a backwards-compatible
alias.

Redis is an **optional** dependency. If the ``redis`` package is not installed,
or ``REDIS_URL`` is unset/unreachable, the cache transparently no-ops so the
rest of the engine keeps working. Install caching support with::

    pip install "quorum[cache]"

Environment controls:

    REDIS_URL                     redis://host:port/db   (caching off if unset)
    QUORUM_CACHE_TTL_SECONDS      default: 3600
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional, cast

logger = logging.getLogger(__name__)


def _stable_key(domain: str, prompt: str) -> str:
    """Deterministic cache key.

    Python's builtin ``hash()`` is randomized per-process (PYTHONHASHSEED), so
    keys built from it never match across restarts or uvicorn workers. SHA-256
    gives a stable key that survives process boundaries.
    """
    digest = hashlib.sha256(f"{domain}\x00{prompt}".encode("utf-8")).hexdigest()
    return f"quorum:cache:{domain}:{digest}"


class PromptCache:
    """Exact-match prompt cache backed by Redis (optional, degrades to no-op)."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.client: Optional[Any] = None
        self.ttl = int(os.getenv("QUORUM_CACHE_TTL_SECONDS", "3600"))

        if not self.redis_url:
            return

        try:
            import redis  # lazy import keeps redis an optional dependency
        except ImportError:
            logger.warning(
                "REDIS_URL is set but the 'redis' package is not installed; "
                "caching disabled. Install it with: pip install \"quorum[cache]\""
            )
            return

        try:
            client = redis.from_url(self.redis_url)
            client.ping()
            self.client = client
            logger.info("Connected to Redis for prompt caching.")
        except Exception as e:
            logger.warning("Failed to connect to Redis: %s", e)
            self.client = None

    def get(self, prompt: str, domain: str) -> Optional[Dict[str, Any]]:
        """Return a cached result for an exact (domain, prompt) match, or None."""
        if not self.client:
            return None
        try:
            data = self.client.get(_stable_key(domain, prompt))
            if data:
                logger.info("Prompt cache hit (exact match).")
                result = json.loads(cast(bytes, data).decode("utf-8"))
                result["cached"] = True
                return result
        except Exception as e:
            logger.warning("Cache retrieval failed: %s", e)
        return None

    def set(self, prompt: str, domain: str, result: Dict[str, Any]) -> None:
        """Store a result under the stable (domain, prompt) key with TTL."""
        if not self.client:
            return
        try:
            # Strip volatile, per-request fields before caching.
            clean_result = {
                k: v for k, v in result.items() if k not in ("query_id", "cached")
            }
            self.client.setex(
                _stable_key(domain, prompt), self.ttl, json.dumps(clean_result)
            )
        except Exception as e:
            logger.warning("Cache storage failed: %s", e)


# Backwards-compatible alias for older imports.
SemanticCache = PromptCache

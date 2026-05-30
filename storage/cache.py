import json
import os
import logging
from typing import Any, Dict, Optional, cast
import redis

logger = logging.getLogger(__name__)

class SemanticCache:
    """Redis-backed cache using prompt embeddings for semantic matching."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.client: Optional[redis.Redis] = None
        self.ttl = int(os.getenv("QUORUM_CACHE_TTL_SECONDS", "3600"))
        self.threshold = float(os.getenv("QUORUM_CACHE_THRESHOLD", "0.98"))
        
        if self.redis_url:
            try:
                self.client = redis.from_url(self.redis_url)
                self.client.ping()
                logger.info("Connected to Redis for semantic caching.")
            except Exception as e:
                logger.warning("Failed to connect to Redis: %s", e)
                self.client = None

    def get(self, prompt: str, domain: str, prompt_vector: list[float]) -> Optional[Dict[str, Any]]:
        """Try to find a semantically similar result in the cache."""
        if not self.client:
            return None
        
        try:
            # For v1, we use exact match first for performance.
            cache_key = f"quorum:cache:{domain}:{hash(prompt)}"
            data = self.client.get(cache_key)
            if data:
                logger.info("Semantic cache hit (exact match) for prompt.")
                result = json.loads(cast(bytes, data).decode("utf-8"))
                result["cached"] = True
                return result
        except Exception as e:
            logger.warning("Cache retrieval failed: %s", e)
        return None

    def set(self, prompt: str, domain: str, prompt_vector: list[float], result: Dict[str, Any]):
        """Store result in cache."""
        if not self.client:
            return
        
        try:
            cache_key = f"quorum:cache:{domain}:{hash(prompt)}"
            # Remove volatile fields before caching
            clean_result = {k: v for k, v in result.items() if k not in ("query_id", "cached")}
            self.client.setex(cache_key, self.ttl, json.dumps(clean_result))
        except Exception as e:
            logger.warning("Cache storage failed: %s", e)

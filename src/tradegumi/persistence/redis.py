"""Redis cache layer for TradeGumi hot runtime state.

Keeps latest prices, loop state, watchlist, active signals, and strategy
summary caches in Redis with TTLs.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("TRADEGUMI_REDIS_URL", "")

DEFAULT_TTLS = {
    "loop_state": 10,
    "latest_prices": 10,
    "watchlist": 300,
    "active_signals": 300,
    "strategy_summary": 60,
}


class RedisCache:
    """Wrapper around redis-py with JSON serde and TTL helpers."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or REDIS_URL
        self._client: Optional[Any] = None
        if self.url:
            try:
                import redis as _redis
                self._redis = _redis
            except ImportError as exc:
                log.warning("redis-py not installed; RedisCache will be a no-op")
                self._redis = None
        else:
            self._redis = None

    def _get_client(self):
        if self._client is None and self._redis is not None:
            self._client = self._redis.from_url(self.url, decode_responses=True)
        return self._client

    def _key(self, name: str) -> str:
        return f"tradegumi:{name}"

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            payload = json.dumps(value, default=str)
            if ttl:
                client.setex(self._key(key), ttl, payload)
            else:
                client.set(self._key(key), payload)
            return True
        except Exception as exc:
            log.warning("Redis set failed for %s: %s", key, exc)
            return False

    def get(self, key: str) -> Optional[Any]:
        client = self._get_client()
        if client is None:
            return None
        try:
            payload = client.get(self._key(key))
            if payload is None:
                return None
            return json.loads(payload)
        except Exception as exc:
            log.warning("Redis get failed for %s: %s", key, exc)
            return None

    def delete(self, key: str) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            client.delete(self._key(key))
            return True
        except Exception as exc:
            log.warning("Redis delete failed for %s: %s", key, exc)
            return False

    def publish(self, channel: str, message: Any) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            payload = json.dumps(message, default=str)
            client.publish(self._key(channel), payload)
            return True
        except Exception as exc:
            log.warning("Redis publish failed for %s: %s", channel, exc)
            return False

    def cache_strategy_summary(self, filters: dict[str, Any], summary: dict[str, Any], ttl: int = 60) -> bool:
        key = f"strategy_summary:{json.dumps(filters, sort_keys=True, default=str)}"
        return self.set(key, summary, ttl)

    def get_cached_strategy_summary(self, filters: dict[str, Any]) -> Optional[dict[str, Any]]:
        key = f"strategy_summary:{json.dumps(filters, sort_keys=True, default=str)}"
        return self.get(key)

    def invalidate_strategy_summary(self) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            for k in client.scan_iter(match=self._key("strategy_summary:*")):
                client.delete(k)
            return True
        except Exception as exc:
            log.warning("Redis invalidate_strategy_summary failed: %s", exc)
            return False


# Singleton
_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance

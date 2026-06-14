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

    def subscribe(self, channel: str):
        """Return a Redis ``PubSub`` subscribed to the prefixed channel, or None.

        The caller owns the returned object: it must read messages (e.g. via
        ``get_message``/``listen``) and ``close()`` it when done.  Returns
        ``None`` when Redis is unavailable so callers degrade to a no-op (the
        worker keeps trading on its last-applied config) rather than crashing.
        """
        client = self._get_client()
        if client is None:
            return None
        try:
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(self._key(channel))
            return pubsub
        except Exception as exc:
            log.warning("Redis subscribe failed for %s: %s", channel, exc)
            return None

    def cache_strategy_summary(self, filters: dict[str, Any], summary: dict[str, Any], ttl: int = 60) -> bool:
        key = f"strategy_summary:{json.dumps(filters, sort_keys=True, default=str)}"
        return self.set(key, summary, ttl)

    def get_cached_strategy_summary(self, filters: dict[str, Any]) -> Optional[dict[str, Any]]:
        key = f"strategy_summary:{json.dumps(filters, sort_keys=True, default=str)}"
        return self.get(key)

    def invalidate_strategy_summary(self, symbol: Optional[str] = None, strategy: Optional[str] = None, signal_type: Optional[str] = None) -> bool:
        """Invalidate cached strategy summaries that could include a new write.

        Summary cache keys embed the full filter dict (start/end/symbol/strategy/
        signal_type/decision/first_blocker).  A subset-permutation guess never
        matches those keys, so instead scan the cached keys, parse each embedded
        filter, and delete any whose symbol/strategy/signal_type filter is either
        unset (matches all) or equal to the written value.  With no filters, all
        summary keys are invalidated.
        """
        client = self._get_client()
        if client is None:
            return False

        def _compatible(cached: Any, value: Optional[str]) -> bool:
            # A cached summary includes the new write if it does not filter this
            # dimension (None) or filters to the same value.  When the caller
            # does not constrain a dimension (value is None), treat as a match.
            return cached is None or value is None or cached == value

        prefix = self._key("strategy_summary:")
        try:
            for full_key in client.scan_iter(match=self._key("strategy_summary:*")):
                raw = full_key[len(prefix):] if full_key.startswith(prefix) else None
                if raw is None:
                    continue
                try:
                    cached_filters = json.loads(raw)
                except (TypeError, ValueError):
                    # Unparseable key — drop it to stay safe.
                    client.delete(full_key)
                    continue
                if (
                    _compatible(cached_filters.get("symbol"), symbol)
                    and _compatible(cached_filters.get("strategy"), strategy)
                    and _compatible(cached_filters.get("signal_type"), signal_type)
                ):
                    client.delete(full_key)
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


# ── Cross-process channels/keys (worker / api / dashboard split) ───────────────
# These back the data plane that replaces the in-memory state the worker and API
# shared when they ran in one process.  All names are passed through
# ``RedisCache._key`` and so are stored under the ``tradegumi:`` prefix.
HEARTBEAT_KEY = "heartbeat:worker"
COMMAND_CHANNEL = "commands"
DESIRED_CONFIG_KEY = "desired_config"

# The heartbeat TTL must be >= the staleness threshold the healthcheck uses, so
# the key never expires between the worker's once-per-loop refreshes.  A TTL
# shorter than the loop interval would make worker health flap.
WORKER_HEARTBEAT_TTL_SECONDS = int(os.getenv("TRADEGUMI_WORKER_HEARTBEAT_TTL_SECONDS", "150"))


def set_heartbeat(payload: dict[str, Any], ttl: Optional[int] = None) -> bool:
    """Publish the worker liveness heartbeat to Redis with a TTL.

    Parameters
    ----------
    payload:
        Heartbeat contents, conventionally ``{"ts", "loop_count", "mode"}``.
    ttl:
        Override the default ``WORKER_HEARTBEAT_TTL_SECONDS``.

    Returns ``False`` (no-op) when Redis is unavailable.
    """
    return get_cache().set(HEARTBEAT_KEY, payload, ttl=ttl or WORKER_HEARTBEAT_TTL_SECONDS)


def get_heartbeat() -> Optional[dict[str, Any]]:
    """Return the latest worker heartbeat, or ``None`` if missing/expired."""
    return get_cache().get(HEARTBEAT_KEY)


def publish_command(command: dict[str, Any]) -> bool:
    """Publish an operator command on the command channel (fast path).

    Durable delivery (so a command issued while the worker is down is still
    applied) is the caller's responsibility via :func:`set_desired_config`.
    Returns ``False`` when the publish could not be delivered — callers MUST NOT
    report success in that case (FR-010).
    """
    return get_cache().publish(COMMAND_CHANNEL, command)


def subscribe_commands():
    """Subscribe to the command channel; returns a PubSub or ``None``."""
    return get_cache().subscribe(COMMAND_CHANNEL)


def set_desired_config(config: dict[str, Any]) -> bool:
    """Persist the desired worker config (last-write-wins, no TTL).

    The worker reconciles against this on startup and each loop so a config
    command survives a worker restart (recovery path for the command channel).
    """
    return get_cache().set(DESIRED_CONFIG_KEY, config)


def get_desired_config() -> Optional[dict[str, Any]]:
    """Return the durable desired worker config, or ``None`` if unset."""
    return get_cache().get(DESIRED_CONFIG_KEY)

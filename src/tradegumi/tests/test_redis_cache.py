"""Tests for the Redis cache layer and runtime-state snapshotting.

These use an in-memory fake client, so no Redis server is required.
"""

import json

import pytest

from tradegumi.persistence.redis import RedisCache
from tradegumi import api_server


class FakeRedis:
    """Minimal in-memory stand-in for the redis-py client used by RedisCache."""

    def __init__(self):
        self.store: dict[str, str] = {}

    def set(self, key, value):
        self.store[key] = value

    def setex(self, key, ttl, value):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)

    def scan_iter(self, match=None):
        if match and match.endswith("*"):
            prefix = match[:-1]
            return [k for k in list(self.store) if k.startswith(prefix)]
        return [k for k in list(self.store) if match is None or k == match]


def _cache_with_fake():
    cache = RedisCache(url="redis://fake")
    fake = FakeRedis()
    cache._client = fake  # bypass lazy connect
    return cache, fake


def _summary_filters(**overrides):
    base = {
        "start": "2026-06-01",
        "end": "2026-06-07",
        "symbol": None,
        "strategy": None,
        "signal_type": None,
        "decision": None,
        "first_blocker": None,
    }
    base.update(overrides)
    return base


class TestStrategySummaryCache:
    def test_round_trip(self):
        cache, _ = _cache_with_fake()
        filters = _summary_filters(symbol="EURUSD")
        cache.cache_strategy_summary(filters, {"total_evaluated": 5})
        assert cache.get_cached_strategy_summary(filters) == {"total_evaluated": 5}

    def test_invalidate_matches_full_filter_keys(self):
        cache, fake = _cache_with_fake()
        cache.cache_strategy_summary(_summary_filters(symbol="EURUSD", strategy="CTI", signal_type="pullback"), {"x": 1})
        cache.cache_strategy_summary(_summary_filters(symbol="GBPUSD", strategy="CTI", signal_type="pullback"), {"x": 2})
        cache.cache_strategy_summary(_summary_filters(), {"x": 3})  # all-symbols summary

        assert cache.invalidate_strategy_summary(symbol="EURUSD") is True

        prefix = "tradegumi:strategy_summary:"
        remaining = [json.loads(k[len(prefix):]) for k in fake.store]
        symbols = {f.get("symbol") for f in remaining}
        # EURUSD-specific and the all-symbols (None) summary are gone; GBPUSD stays.
        assert symbols == {"GBPUSD"}

    def test_invalidate_all_when_no_filters(self):
        cache, fake = _cache_with_fake()
        cache.cache_strategy_summary(_summary_filters(symbol="EURUSD"), {"x": 1})
        cache.cache_strategy_summary(_summary_filters(symbol="GBPUSD"), {"x": 2})
        assert cache.invalidate_strategy_summary() is True
        assert fake.store == {}

    def test_invalidate_is_noop_without_client(self):
        cache = RedisCache(url="")  # no client
        assert cache.invalidate_strategy_summary(symbol="EURUSD") is False


class TestRuntimeStateSnapshot:
    def test_json_safe_state_drops_non_serializable(self):
        client = object()
        safe = api_server._json_safe_state({"running": True, "loop_count": 2, "client": client})
        assert safe == {"running": True, "loop_count": 2}

    def test_set_runtime_state_keeps_live_client_and_snapshots_full_state(self, monkeypatch):
        api_server._runtime_state.clear()
        captured = {}

        class FakeCache:
            def set(self, key, value, ttl=None):
                captured["key"] = key
                captured["value"] = value
                return True

        monkeypatch.setattr("tradegumi.persistence.redis.get_cache", lambda: FakeCache())

        client = object()
        api_server.set_runtime_state({"running": True, "client": client, "loop_count": 3})

        # In-process state retains the live (non-serializable) client object.
        assert api_server.get_runtime_state()["client"] is client
        # Redis snapshot excludes the client but keeps serializable fields.
        assert captured["key"] == "loop_state"
        assert "client" not in captured["value"]
        assert captured["value"] == {"running": True, "loop_count": 3}

        # A later partial update is merged: the snapshot reflects the FULL state.
        api_server.set_runtime_state({"loop_count": 4})
        assert captured["value"] == {"running": True, "loop_count": 4}
        api_server._runtime_state.clear()

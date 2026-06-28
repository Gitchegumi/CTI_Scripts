"""Graceful-degradation tests: Redis/broker outages don't fault analytics (US3)."""

import pytest


@pytest.fixture(autouse=True)
def _auth_off(no_auth):
    return no_auth


@pytest.fixture
def redis_down(monkeypatch):
    """Make every Redis access raise, simulating a cache/heartbeat outage."""
    def boom(*a, **k):
        raise RuntimeError("redis unavailable")
    monkeypatch.setattr("tradegumi.persistence.redis.get_cache", boom)
    monkeypatch.setattr("tradegumi.persistence.redis.get_heartbeat", boom)


def test_status_serves_with_redis_down(client, redis_down):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json()["worker_live"] is False


def test_journal_read_serves_with_redis_down(client, redis_down, monkeypatch):
    monkeypatch.setattr("tradegumi.journal.read_journal", lambda: [{"signal_id": "s1"}])
    resp = client.get("/api/data/journal")
    assert resp.status_code == 200
    assert resp.json() == [{"signal_id": "s1"}]


def test_strategy_summary_serves_with_redis_down(client, redis_down, monkeypatch):
    monkeypatch.setattr("tradegumi.persistence.get_db", lambda: object())
    monkeypatch.setattr("tradegumi.strategy_metrics.get_summary", lambda *a, **k: {"rows": 1})
    resp = client.get("/api/strategy-metrics/summary?start=2026-06-01&end=2026-06-28")
    assert resp.status_code == 200
    assert resp.json() == {"rows": 1}


def test_broker_endpoints_503_when_client_unavailable(client, monkeypatch):
    monkeypatch.setattr("tradegumi.api.routes.trades.get_api_execution_client", lambda: None)
    resp = client.get("/api/positions")
    assert resp.status_code == 503
    assert resp.json() == {"error": "client not available"}


def test_worker_live_false_on_stale_heartbeat(monkeypatch):
    """worker_live degrades to False when the heartbeat is stale rather than raising."""
    import tradegumi.api.deps as deps
    monkeypatch.setattr(
        "tradegumi.persistence.redis.get_heartbeat", lambda: {"ts": 0.0}
    )
    assert deps.worker_live() is False

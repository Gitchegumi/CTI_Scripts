"""Parity tests for strategy-metrics endpoints (US1)."""

import pytest


@pytest.fixture(autouse=True)
def _auth_off(no_auth):
    return no_auth


@pytest.fixture(autouse=True)
def _fake_db(monkeypatch):
    """Stub the durable backend so analytics routes don't touch Postgres."""
    monkeypatch.setattr("tradegumi.persistence.get_db", lambda: object())


def test_strategies_success(client, monkeypatch):
    monkeypatch.setattr("tradegumi.strategy_registry.get_strategies", lambda: ["a", "b"])
    resp = client.get("/api/strategies")
    assert resp.status_code == 200
    assert resp.json() == ["a", "b"]


def test_strategies_error_is_500(client, monkeypatch):
    def boom():
        raise RuntimeError("registry down")
    monkeypatch.setattr("tradegumi.strategy_registry.get_strategies", boom)
    resp = client.get("/api/strategies")
    assert resp.status_code == 500
    assert resp.json() == {"error": "registry down"}


def test_summary_requires_start_end(client):
    resp = client.get("/api/strategy-metrics/summary")
    assert resp.status_code == 400
    assert resp.json() == {"error": "start and end are required"}


def test_summary_success_passes_filters(client, monkeypatch):
    captured = {}

    def fake_summary(start, end, **kwargs):
        captured["start"] = start
        captured["end"] = end
        captured.update(kwargs)
        return {"rows": 3}

    monkeypatch.setattr("tradegumi.strategy_metrics.get_summary", fake_summary)
    resp = client.get("/api/strategy-metrics/summary?start=2026-06-01&end=2026-06-28&symbol=EURUSD")
    assert resp.status_code == 200
    assert resp.json() == {"rows": 3}
    assert captured["start"] == "2026-06-01"
    assert captured["symbol"] == "EURUSD"


def test_summary_value_error_is_400(client, monkeypatch):
    def bad(*a, **k):
        raise ValueError("bad date")
    monkeypatch.setattr("tradegumi.strategy_metrics.get_summary", bad)
    resp = client.get("/api/strategy-metrics/summary?start=x&end=y")
    assert resp.status_code == 400
    assert resp.json() == {"error": "bad date"}


def test_lifecycle_events_requires_metric(client, monkeypatch):
    monkeypatch.setattr("tradegumi.strategy_metrics.get_lifecycle_events", lambda *a, **k: [])
    resp = client.get("/api/strategy-metrics/lifecycle-events?start=a&end=b")
    assert resp.status_code == 400
    assert resp.json() == {"error": "metric is required"}


def test_compare_requires_all_ranges(client):
    resp = client.get("/api/strategy-metrics/compare?base_start=a")
    assert resp.status_code == 400
    assert "required" in resp.json()["error"]

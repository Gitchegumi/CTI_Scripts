"""Parity tests for the status and data-read endpoints (US1)."""

import pytest


@pytest.fixture(autouse=True)
def _auth_off(no_auth):
    """Status/data endpoints are open; ensure auth is disabled."""
    return no_auth


def test_status_reports_worker_live_and_defaults(client, monkeypatch):
    monkeypatch.setattr("tradegumi.api.routes.status.get_runtime_state", lambda: {})
    monkeypatch.setattr("tradegumi.api.routes.status.worker_live", lambda: True)

    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    # Same key surface as the previous server.
    for key in (
        "mode", "challenge_type", "program", "phase", "daily_loss_pct",
        "max_dd_pct", "running", "worker_live", "loop_count",
        "last_signal_time", "market_data", "tiers",
    ):
        assert key in body
    assert body["worker_live"] is True
    assert body["running"] is False


def test_status_mirrors_worker_config_block(client, monkeypatch):
    state = {"config": {"mode": "live", "phase": 2}, "running": True, "loop_count": 7}
    monkeypatch.setattr("tradegumi.api.routes.status.get_runtime_state", lambda: state)
    monkeypatch.setattr("tradegumi.api.routes.status.worker_live", lambda: False)

    body = client.get("/api/status").json()
    assert body["mode"] == "live"
    assert body["phase"] == 2
    assert body["running"] is True
    assert body["loop_count"] == 7


def test_loop_state_default_when_no_snapshot_or_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr("tradegumi.api.routes.data.get_runtime_state", lambda: {})
    monkeypatch.setattr("tradegumi.api.routes.data.DATA_DIR", tmp_path)

    body = client.get("/api/data/loop_state").json()
    assert body["symbols"] == []
    assert "provider" in body


def test_watchlist_and_signals_defaults(client, monkeypatch, tmp_path):
    monkeypatch.setattr("tradegumi.api.routes.data.DATA_DIR", tmp_path)

    wl = client.get("/api/data/watchlist").json()
    assert wl == {"tier1": [], "tier2": [], "below": [], "ranked": []}

    sig = client.get("/api/data/signals").json()
    assert sig == []


def test_trade_correlations_default_and_bad_json(client, monkeypatch, tmp_path):
    monkeypatch.setattr("tradegumi.api.routes.data.DATA_DIR", tmp_path)
    assert client.get("/api/data/trade_correlations").json() == []

    (tmp_path / "trade_correlations.json").write_text("not json", encoding="utf-8")
    assert client.get("/api/data/trade_correlations").json() == []


def test_prices_empty_without_symbols(client):
    resp = client.get("/api/prices")
    assert resp.status_code == 200
    assert resp.json() == []


def test_unknown_path_returns_legacy_not_found(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.json() == {"error": "not found"}

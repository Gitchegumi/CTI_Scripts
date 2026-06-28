"""Mutation parity tests: journal, manual trades, purge (US2)."""

import pytest

from tradegumi.manual_trades import TradePermissionError, TradeNotFoundError


@pytest.fixture(autouse=True)
def _auth_off(no_auth):
    return no_auth


@pytest.fixture(autouse=True)
def _no_source_history(monkeypatch):
    monkeypatch.setattr("tradegumi.api.routes.trades.source_trade_history", lambda count=1000: [])


# ── Journal mutations ──────────────────────────────────────────────────────

def test_grade_requires_fields(client):
    resp = client.post("/api/journal/grade", json={"signal_id": "s1"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "signal_id and grade are required"}


def test_grade_success(client, monkeypatch):
    monkeypatch.setattr("tradegumi.journal.grade_by_signal_id", lambda sid, grade, notes: True)
    resp = client.post("/api/journal/grade", json={"signal_id": "s1", "grade": "a", "notes": "n"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_grade_not_found(client, monkeypatch):
    monkeypatch.setattr("tradegumi.journal.grade_by_signal_id", lambda *a, **k: False)
    resp = client.post("/api/journal/grade", json={"signal_id": "s1", "grade": "A"})
    assert resp.status_code == 404
    assert resp.json() == {"error": "Signal not found or invalid grade"}


def test_invalidate_requires_signal_id(client):
    resp = client.post("/api/journal/invalidate", json={})
    assert resp.status_code == 400
    assert resp.json() == {"error": "signal_id is required"}


# ── Manual trade create / update / delete ──────────────────────────────────

def test_create_requires_symbol_and_direction(client):
    resp = client.post("/api/trades/manual", json={"symbol": "", "direction": "long"})
    assert resp.status_code == 400
    assert "symbol and direction" in resp.json()["error"]


def test_create_success_201(client, monkeypatch):
    monkeypatch.setattr("tradegumi.manual_trades.create_trade", lambda **k: {"id": "m1", "symbol": k["symbol"]})
    resp = client.post("/api/trades/manual", json={"symbol": "eurusd", "direction": "long", "entry_price": 1.1})
    assert resp.status_code == 201
    assert resp.json() == {"id": "m1", "symbol": "EURUSD"}


def test_create_permission_denied_403(client, monkeypatch):
    def deny(**k):
        raise TradePermissionError("not allowed in this mode")
    monkeypatch.setattr("tradegumi.manual_trades.create_trade", deny)
    resp = client.post("/api/trades/manual", json={"symbol": "EURUSD", "direction": "long", "entry_price": 1.1})
    assert resp.status_code == 403
    assert resp.json() == {"error": "not allowed in this mode"}


def test_update_not_found_404(client, monkeypatch):
    def missing(*a, **k):
        raise TradeNotFoundError("no such trade")
    monkeypatch.setattr("tradegumi.manual_trades.update_trade_record", missing)
    resp = client.put("/api/trades/manual/abc", json={"notes": "x"})
    assert resp.status_code == 404
    assert resp.json() == {"error": "no such trade"}


def test_delete_success(client, monkeypatch):
    monkeypatch.setattr("tradegumi.manual_trades.delete_trade_record", lambda *a, **k: None)
    resp = client.delete("/api/trades/manual/abc")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_post_to_manual_id_is_405(client):
    resp = client.post("/api/trades/manual/abc", json={})
    assert resp.status_code == 405
    assert resp.json() == {"error": "Method not allowed — use PUT or DELETE"}


# ── Purge ──────────────────────────────────────────────────────────────────

def test_purge_targets_must_be_list(client):
    resp = client.request("POST", "/api/purge", json={"targets": "signals"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "targets must be a list or omitted"}


def test_purge_success(client, monkeypatch):
    monkeypatch.setattr("tradegumi.purge.purge_all", lambda targets=None: {"signals": 3})
    resp = client.request("POST", "/api/purge", json={"targets": ["signals"]})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "results": {"signals": 3}}


# ── Legacy path alias ──────────────────────────────────────────────────────

def test_manual_trades_alias_resolves(client, monkeypatch):
    monkeypatch.setattr("tradegumi.manual_trades.get_all_trades", lambda **k: [{"id": "alias"}])
    resp = client.get("/api/manual-trades")
    assert resp.status_code == 200
    assert resp.json() == [{"id": "alias"}]

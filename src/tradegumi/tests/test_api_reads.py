"""Parity tests for read-only trades and journal-read endpoints (US1)."""

import pytest


@pytest.fixture(autouse=True)
def _auth_off(no_auth):
    """Run reads with auth disabled so protected reads succeed (no-op auth)."""
    return no_auth


@pytest.fixture(autouse=True)
def _no_source_history(monkeypatch):
    monkeypatch.setattr("tradegumi.api.routes.trades.source_trade_history", lambda count=1000: [])


def test_positions_503_without_client(client, monkeypatch):
    monkeypatch.setattr("tradegumi.api.routes.trades.get_api_execution_client", lambda: None)
    resp = client.get("/api/positions")
    assert resp.status_code == 503
    assert resp.json() == {"error": "client not available"}


def test_positions_success(client, monkeypatch):
    class P:
        id = "1"; symbol = "EURUSD"; side = "buy"; volume = 1.0
        open_price = 1.1; current_price = 1.2; stop_loss = None
        take_profit = None; unrealized_pl = 10.0; net_profit = 9.0
    fake_client = type("C", (), {"get_open_positions": lambda self: [P()]})()
    monkeypatch.setattr("tradegumi.api.routes.trades.get_api_execution_client", lambda: fake_client)
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    rows = resp.json()
    assert rows[0]["symbol"] == "EURUSD"
    assert rows[0]["unrealized_pl"] == 10.0


def test_trades_history_success(client, monkeypatch):
    monkeypatch.setattr(
        "tradegumi.manual_trades.get_dashboard_trade_history",
        lambda **kwargs: [{"id": "t1"}],
    )
    resp = client.get("/api/trades/history")
    assert resp.status_code == 200
    assert resp.json() == [{"id": "t1"}]


def test_manual_list_success(client, monkeypatch):
    monkeypatch.setattr("tradegumi.manual_trades.get_all_trades", lambda **k: [{"id": "m1"}])
    resp = client.get("/api/trades/manual")
    assert resp.status_code == 200
    assert resp.json() == [{"id": "m1"}]


def test_manual_stats_success(client, monkeypatch):
    monkeypatch.setattr("tradegumi.manual_trades.get_summary_stats", lambda **k: {"count": 2})
    resp = client.get("/api/trades/manual/stats")
    assert resp.status_code == 200
    assert resp.json() == {"count": 2}


def test_data_journal_read(client, monkeypatch):
    monkeypatch.setattr("tradegumi.journal.read_journal", lambda: [{"signal_id": "s1"}])
    resp = client.get("/api/data/journal")
    assert resp.status_code == 200
    assert resp.json() == [{"signal_id": "s1"}]


def test_journal_export_empty_range_404(client, monkeypatch):
    monkeypatch.setattr("tradegumi.journal.SignalJournalExportSelection", lambda **k: object())
    export = type("E", (), {"record_count": 0})()
    monkeypatch.setattr("tradegumi.journal.build_journal_export", lambda sel: export)
    resp = client.get("/api/journal/export")
    assert resp.status_code == 404
    assert "No Signal Journal records" in resp.json()["error"]


def test_journal_export_returns_csv(client, monkeypatch):
    monkeypatch.setattr("tradegumi.journal.SignalJournalExportSelection", lambda **k: object())
    export = type("E", (), {
        "record_count": 2,
        "csv_text": "a,b\n1,2\n",
        "content_type": "text/csv; charset=utf-8",
        "content_disposition": 'attachment; filename="journal.csv"',
    })()
    monkeypatch.setattr("tradegumi.journal.build_journal_export", lambda sel: export)
    resp = client.get("/api/journal/export")
    assert resp.status_code == 200
    assert resp.text == "a,b\n1,2\n"
    assert resp.headers["content-disposition"].startswith("attachment")

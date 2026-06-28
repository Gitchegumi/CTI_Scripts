"""Authentication-behavior tests across protected/open endpoints (US2)."""

import pytest

# Representative protected endpoints (require X-API-Key when JOURNAL_TOKEN set).
PROTECTED = [
    ("get", "/api/journal/export"),
    ("get", "/api/trades/history"),
    ("get", "/api/trades/manual"),
    ("get", "/api/trades/manual/export"),
    ("get", "/api/trades/manual/stats"),
    ("delete", "/api/journal"),
    ("post", "/api/purge"),
]

# Representative open endpoints (never require the key).
OPEN = [
    ("get", "/api/status"),
    ("post", "/api/journal/grade"),
    ("post", "/api/config/mode"),
    ("post", "/api/action/rescan"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_rejects_without_key(client, with_token, method, path):
    resp = getattr(client, method)(path)
    assert resp.status_code == 401
    assert resp.json() == {"error": "Unauthorized"}


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_passes_auth_with_key(client, with_token, method, path):
    # With a valid key the auth gate is cleared; the handler then runs (it may
    # fail downstream on unmocked deps, but it MUST NOT be a 401).
    resp = getattr(client, method)(path, headers={"X-API-Key": with_token})
    assert resp.status_code != 401


@pytest.mark.parametrize("method,path", OPEN)
def test_open_endpoints_ignore_missing_key(client, with_token, monkeypatch, method, path):
    # Stub the command channel so config/action endpoints don't hit Redis.
    monkeypatch.setattr(
        "tradegumi.commands.build_command",
        lambda cmd_type, payload, source="api": {"command_id": "x", "type": cmd_type},
    )
    monkeypatch.setattr("tradegumi.commands.publish", lambda cmd: True)
    monkeypatch.setattr("tradegumi.journal.grade_by_signal_id", lambda *a, **k: True)
    monkeypatch.setattr("tradegumi.api.routes.status.get_runtime_state", lambda: {})
    monkeypatch.setattr("tradegumi.api.routes.status.worker_live", lambda: False)
    kwargs = {} if method == "get" else {"json": {"signal_id": "s1", "grade": "A"}}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code != 401


def test_no_token_means_auth_disabled(client, no_auth, monkeypatch):
    monkeypatch.setattr("tradegumi.api.routes.trades.source_trade_history", lambda count=1000: [])
    monkeypatch.setattr("tradegumi.manual_trades.get_all_trades", lambda **k: [])
    # Protected endpoint reachable without any key when JOURNAL_TOKEN is unset.
    resp = client.get("/api/trades/manual")
    assert resp.status_code == 200

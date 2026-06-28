"""Command-channel behavior tests for config/action endpoints (US2)."""

import pytest

from tradegumi import commands


@pytest.fixture(autouse=True)
def _auth_off(no_auth):
    return no_auth


def _accept_build(monkeypatch, command_id="cmd-123"):
    monkeypatch.setattr(
        "tradegumi.commands.build_command",
        lambda cmd_type, payload, source="api": {"command_id": command_id, "type": cmd_type},
    )


def test_config_mode_accepted(client, monkeypatch):
    _accept_build(monkeypatch)
    monkeypatch.setattr("tradegumi.commands.publish", lambda cmd: True)
    resp = client.post("/api/config/mode", json={"mode": "demo"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "accepted", "command_id": "cmd-123"}


def test_config_mode_undelivered_is_503(client, monkeypatch):
    _accept_build(monkeypatch)
    monkeypatch.setattr("tradegumi.commands.publish", lambda cmd: False)
    resp = client.post("/api/config/mode", json={"mode": "demo"})
    assert resp.status_code == 503
    body = resp.json()
    assert body["error"] == "command not delivered — command channel unavailable"
    assert body["type"] == "set_mode"


def test_config_invalid_command_is_400(client, monkeypatch):
    def bad(cmd_type, payload, source="api"):
        raise commands.CommandError("invalid mode")
    monkeypatch.setattr("tradegumi.commands.build_command", bad)
    # publish must never be called on an invalid command.
    monkeypatch.setattr("tradegumi.commands.publish", lambda cmd: pytest.fail("published invalid"))
    resp = client.post("/api/config/mode", json={"mode": "???"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "invalid mode"}


def test_action_rescan_accepted(client, monkeypatch):
    _accept_build(monkeypatch, command_id="rescan-1")
    monkeypatch.setattr("tradegumi.commands.publish", lambda cmd: True)
    resp = client.post("/api/action/rescan")
    assert resp.status_code == 200
    assert resp.json()["command_id"] == "rescan-1"


def test_action_restart_sets_flag(client, monkeypatch):
    captured = {}
    monkeypatch.setattr("tradegumi.api.routes.config_actions.get_runtime_state", lambda: {})
    monkeypatch.setattr(
        "tradegumi.api.routes.config_actions.set_runtime_state",
        lambda state: captured.update(state),
    )
    resp = client.post("/api/action/restart")
    assert resp.status_code == 200
    assert resp.json() == {"status": "restart_requested"}
    assert captured.get("restart_requested") is True


def test_empty_body_still_reaches_validation(client, monkeypatch):
    # An empty/malformed body degrades to {} so the worker command builder runs.
    _accept_build(monkeypatch)
    monkeypatch.setattr("tradegumi.commands.publish", lambda cmd: True)
    resp = client.post("/api/config/mode", content=b"", headers={"content-type": "application/json"})
    assert resp.status_code == 200

"""Tests for the operator command channel (specs/019-split-runtime-containers US4).

Covers validation, the publish path (desired-config + pub/sub), application to
the worker's live config, desired-config reconciliation, and the cross-process
round trip — including a command issued while the worker is "down" being applied
on startup reconciliation (SC-005, FR-010). No live Redis required.
"""
import pytest

from tradegumi import commands, config


@pytest.fixture
def restore_config():
    """Snapshot and restore the config dimensions commands mutate."""
    saved = (
        config.TRADEGUMI_MODE,
        config.CTI_PROGRAM,
        config.CTI_PHASE,
        config.CTI_CHALLENGE_TYPE,
    )
    yield
    (
        config.TRADEGUMI_MODE,
        config.CTI_PROGRAM,
        config.CTI_PHASE,
        config.CTI_CHALLENGE_TYPE,
    ) = saved


class FakeStore:
    """In-memory stand-in for the Redis durable + pub/sub helpers."""

    def __init__(self, publish_ok=True, desired_ok=True):
        self.desired = {}
        self.published = []
        self.publish_ok = publish_ok
        self.desired_ok = desired_ok

    def install(self, monkeypatch):
        monkeypatch.setattr("tradegumi.persistence.redis.get_desired_config", lambda: dict(self.desired))
        monkeypatch.setattr("tradegumi.persistence.redis.publish_command", self._publish)
        monkeypatch.setattr("tradegumi.persistence.redis.set_desired_config", self._set_desired)
        return self

    def _publish(self, cmd):
        self.published.append(cmd)
        return self.publish_ok

    def _set_desired(self, cfg):
        if not self.desired_ok:
            return False
        self.desired = dict(cfg)
        return True


# ── validation ────────────────────────────────────────────────────────────────

def test_validate_rejects_unknown_type():
    with pytest.raises(commands.CommandError):
        commands.validate_command("set_everything", {})


@pytest.mark.parametrize("payload", [{"mode": "demo"}, {"mode": "ALERT_ONLY"}])
def test_validate_mode_ok(payload):
    assert commands.validate_command(commands.SET_MODE, payload)["mode"] in commands.VALID_MODES


def test_validate_mode_invalid():
    with pytest.raises(commands.CommandError):
        commands.validate_command(commands.SET_MODE, {"mode": "turbo"})


def test_validate_phase_invalid():
    with pytest.raises(commands.CommandError):
        commands.validate_command(commands.SET_PHASE, {"phase": 9})


def test_validate_rescan_ignores_payload():
    assert commands.validate_command(commands.RESCAN, {"junk": 1}) == {}


def test_build_command_envelope():
    cmd = commands.build_command(commands.SET_MODE, {"mode": "demo"})
    assert cmd["type"] == commands.SET_MODE
    assert cmd["payload"] == {"mode": "demo"}
    assert cmd["command_id"] and cmd["issued_at"]


# ── publish ───────────────────────────────────────────────────────────────────

def test_publish_updates_desired_and_publishes(monkeypatch):
    store = FakeStore().install(monkeypatch)
    cmd = commands.build_command(commands.SET_MODE, {"mode": "demo"})
    assert commands.publish(cmd) is True
    assert store.desired["mode"] == "demo"
    assert store.published and store.published[0]["type"] == commands.SET_MODE


def test_publish_returns_false_when_pubsub_fails(monkeypatch):
    """A dropped publish must report failure so the API never claims success."""
    store = FakeStore(publish_ok=False).install(monkeypatch)
    cmd = commands.build_command(commands.SET_PHASE, {"phase": 2})
    assert commands.publish(cmd) is False


def test_publish_rescan_does_not_touch_desired_config(monkeypatch):
    store = FakeStore().install(monkeypatch)
    cmd = commands.build_command(commands.RESCAN, {})
    assert commands.publish(cmd) is True
    assert store.desired == {}  # rescan is an action, not durable state


# ── apply ─────────────────────────────────────────────────────────────────────

def test_apply_set_mode(restore_config):
    config.TRADEGUMI_MODE = "alert_only"
    assert commands.apply_command({"type": commands.SET_MODE, "payload": {"mode": "demo"}}) is True
    assert config.TRADEGUMI_MODE == "demo"


def test_apply_rescan_sets_force_rescan(monkeypatch):
    captured = {}
    monkeypatch.setattr("tradegumi.api_server.get_runtime_state", lambda: {})
    monkeypatch.setattr("tradegumi.api_server.set_runtime_state", lambda s: captured.update(s))
    assert commands.apply_command({"type": commands.RESCAN, "payload": {}}) is True
    assert captured.get("force_rescan") is True


# ── reconcile / round trip ─────────────────────────────────────────────────────

def test_reconcile_applies_diffs(monkeypatch, restore_config):
    config.TRADEGUMI_MODE = "alert_only"
    config.CTI_PHASE = 1
    monkeypatch.setattr(
        "tradegumi.persistence.redis.get_desired_config",
        lambda: {"mode": "demo", "phase": 2},
    )
    changed = commands.reconcile_desired_config()
    assert set(changed) == {"mode", "phase"}
    assert config.TRADEGUMI_MODE == "demo"
    assert config.CTI_PHASE == 2
    # Idempotent: a second reconcile changes nothing.
    assert commands.reconcile_desired_config() == []


def test_command_issued_while_worker_down_applied_on_startup(monkeypatch, restore_config):
    """SC-005/FR-010: a command published while the worker is down is applied
    when the worker later reconciles desired config at startup."""
    store = FakeStore().install(monkeypatch)
    config.TRADEGUMI_MODE = "alert_only"

    # API publishes while the worker is not running.
    assert commands.publish(commands.build_command(commands.SET_MODE, {"mode": "demo"})) is True

    # Worker starts later and reconciles → the command takes effect.
    changed = commands.reconcile_desired_config()
    assert "mode" in changed
    assert config.TRADEGUMI_MODE == "demo"

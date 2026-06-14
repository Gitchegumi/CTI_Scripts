"""Operator command channel between the API and the worker.

After the runtime split (specs/019-split-runtime-containers) the API and worker
are separate processes, so config changes the API accepts must be delivered to
the worker. The API publishes commands on a Redis pub/sub channel (fast path)
**and** records the desired config in a durable Redis key (recovery path). The
worker drains the channel each loop for low-latency application and reconciles
against the durable key on startup and each loop, so a command issued while the
worker was briefly down is still applied (FR-005, FR-010).

Only operator control is carried here — mode / program / phase / challenge_type
changes and ``rescan``. Order placement is never a command; it stays worker-only
(Constitution III, Risk-First).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)

# ── Command types ─────────────────────────────────────────────────────────────
SET_MODE = "set_mode"
SET_PROGRAM = "set_program"
SET_PHASE = "set_phase"
SET_CHALLENGE_TYPE = "set_challenge_type"
RESCAN = "rescan"

VALID_MODES = ("alert_only", "demo", "live")
VALID_PROGRAMS = ("challenge", "instant")
VALID_PHASES = (1, 2, 3)
VALID_CHALLENGE_TYPES = ("1-step", "2-step", "instant")

# Which durable desired-config dimension each config command maps to.
_DIM_FOR_TYPE = {
    SET_MODE: "mode",
    SET_PROGRAM: "program",
    SET_PHASE: "phase",
    SET_CHALLENGE_TYPE: "challenge_type",
}


class CommandError(ValueError):
    """Raised when a command is malformed or carries an invalid value.

    The API maps this to a 400 and never publishes the command.
    """


# ── API side: validate / build / publish ──────────────────────────────────────

def validate_command(cmd_type: str, payload: Optional[dict]) -> dict:
    """Validate a command type + payload; return the normalized payload.

    Raises :class:`CommandError` on an unknown type or invalid value.
    """
    payload = payload or {}
    if cmd_type == RESCAN:
        return {}
    if cmd_type == SET_MODE:
        mode = str(payload.get("mode", "")).lower()
        if mode not in VALID_MODES:
            raise CommandError(f"invalid mode; use one of {VALID_MODES}")
        return {"mode": mode}
    if cmd_type == SET_PROGRAM:
        program = str(payload.get("program", "")).lower()
        if program not in VALID_PROGRAMS:
            raise CommandError(f"invalid program; use one of {VALID_PROGRAMS}")
        return {"program": program}
    if cmd_type == SET_CHALLENGE_TYPE:
        challenge_type = str(payload.get("challenge_type", "")).lower()
        if challenge_type not in VALID_CHALLENGE_TYPES:
            raise CommandError(f"invalid challenge_type; use one of {VALID_CHALLENGE_TYPES}")
        return {"challenge_type": challenge_type}
    if cmd_type == SET_PHASE:
        try:
            phase = int(payload.get("phase"))
        except (TypeError, ValueError):
            raise CommandError("invalid phase; use 1, 2, or 3")
        if phase not in VALID_PHASES:
            raise CommandError("invalid phase; use 1, 2, or 3")
        return {"phase": phase}
    raise CommandError(f"unknown command type: {cmd_type}")


def build_command(cmd_type: str, payload: Optional[dict], source: str = "api") -> dict:
    """Build a validated command envelope (raises :class:`CommandError`)."""
    normalized = validate_command(cmd_type, payload)
    return {
        "command_id": str(uuid.uuid4()),
        "type": cmd_type,
        "payload": normalized,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }


def publish(cmd: dict) -> bool:
    """Publish a built command: persist desired config, then publish to pub/sub.

    Returns ``True`` only if both the durable desired-config write (for config
    commands) and the pub/sub publish were accepted by Redis. Callers MUST treat
    ``False`` as "not delivered" and respond accordingly — never silently report
    success (FR-010).
    """
    from tradegumi.persistence.redis import (
        get_desired_config,
        publish_command,
        set_desired_config,
    )

    ok_durable = True
    dimension = _DIM_FOR_TYPE.get(cmd["type"])
    if dimension is not None:
        desired = get_desired_config() or {}
        desired[dimension] = cmd["payload"][dimension]
        ok_durable = set_desired_config(desired)

    ok_publish = publish_command(cmd)
    return bool(ok_durable and ok_publish)


# ── Worker side: apply / reconcile / drain ────────────────────────────────────

def apply_command(cmd: dict) -> bool:
    """Apply a single command to the worker's live config. Returns True if applied.

    Config changes take effect without a restart (Constitution V). ``rescan`` is
    signaled through runtime state (``force_rescan``), which the main loop honors.
    """
    from tradegumi import config

    cmd_type = cmd.get("type")
    payload = cmd.get("payload") or {}
    try:
        if cmd_type == SET_MODE:
            config.TRADEGUMI_MODE = payload["mode"]
        elif cmd_type == SET_PROGRAM:
            config.CTI_PROGRAM = payload["program"]
        elif cmd_type == SET_PHASE:
            config.CTI_PHASE = int(payload["phase"])
        elif cmd_type == SET_CHALLENGE_TYPE:
            config.CTI_CHALLENGE_TYPE = payload["challenge_type"]
        elif cmd_type == RESCAN:
            from tradegumi.api_server import get_runtime_state, set_runtime_state
            set_runtime_state({**get_runtime_state(), "force_rescan": True})
        else:
            log.warning("Ignoring unknown command type: %s", cmd_type)
            return False
        return True
    except Exception as exc:
        log.warning("Failed to apply command %s: %s", cmd_type, exc)
        return False


def reconcile_desired_config() -> list[str]:
    """Apply desired-config dimensions that differ from the worker's live config.

    Returns the dimensions changed. Idempotent (a no-op when already in sync).
    This is the recovery path for config commands missed over pub/sub — e.g.
    issued while the worker was down or briefly disconnected from Redis.

    Note: while a desired-config dimension is set it overrides the corresponding
    ``.env`` value across worker restarts; clear the Redis ``desired_config`` key
    to fall back to ``.env``.
    """
    from tradegumi import config
    from tradegumi.persistence.redis import get_desired_config

    desired = get_desired_config() or {}
    changed: list[str] = []
    if "mode" in desired and desired["mode"] != config.TRADEGUMI_MODE:
        config.TRADEGUMI_MODE = desired["mode"]
        changed.append("mode")
    if "program" in desired and desired["program"] != config.CTI_PROGRAM:
        config.CTI_PROGRAM = desired["program"]
        changed.append("program")
    if "phase" in desired and int(desired["phase"]) != config.CTI_PHASE:
        config.CTI_PHASE = int(desired["phase"])
        changed.append("phase")
    if "challenge_type" in desired and desired["challenge_type"] != config.CTI_CHALLENGE_TYPE:
        config.CTI_CHALLENGE_TYPE = desired["challenge_type"]
        changed.append("challenge_type")
    return changed


def drain_commands(pubsub: Any) -> list[dict]:
    """Return all pending command messages from a PubSub, non-blocking.

    Malformed messages are discarded with a warning. Any transport error returns
    what was collected so far; the worker still reconciles config from the
    durable key, so a momentary Redis blip does not lose config changes.
    """
    messages: list[dict] = []
    if pubsub is None:
        return messages
    try:
        while True:
            raw = pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
            if not raw:
                break
            if raw.get("type") != "message":
                continue
            data = raw.get("data")
            try:
                messages.append(json.loads(data))
            except (TypeError, ValueError):
                log.warning("Discarding malformed command message: %r", data)
    except Exception as exc:
        log.debug("Command drain error: %s", exc)
    return messages

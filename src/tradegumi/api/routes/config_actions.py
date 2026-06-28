"""Config/action router — operator control and maintenance.

Configuration changes and ``rescan`` are validated and published to the worker
over the Redis command channel; an undelivered command returns ``503`` and is
never reported as success (FR-006). ``restart`` flips a runtime-state flag, and
``purge`` (auth required) runs durable maintenance. None of these place orders.
"""
from __future__ import annotations

import logging as log
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from tradegumi.api.deps import get_runtime_state, read_json_body, require_auth, set_runtime_state

router = APIRouter()


def _publish_command(cmd_type: str, payload: Optional[dict]):
    """Validate and publish an operator command to the worker.

    Returns an ``accepted`` body with a ``command_id`` on success, raises
    ``HTTPException(400)`` for an invalid command, and returns a ``503`` body
    when the command channel is unavailable — never a silent success (FR-006).
    Each outcome is logged for observability (Constitution IV); the worker logs
    application of the command.
    """
    from tradegumi import commands
    try:
        cmd = commands.build_command(cmd_type, payload, source="api")
    except commands.CommandError as exc:
        log.info("API: rejected command %s: %s", cmd_type, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    if commands.publish(cmd):
        log.info("API: command %s accepted (id=%s)", cmd_type, cmd["command_id"])
        return {"status": "accepted", "command_id": cmd["command_id"]}
    log.warning("API: command %s not delivered — command channel unavailable", cmd_type)
    return JSONResponse(
        {"error": "command not delivered — command channel unavailable", "type": cmd_type},
        status_code=503,
    )


@router.post("/api/config/mode")
async def set_mode(request: Request):
    """Publish a mode change to the worker."""
    body = await read_json_body(request)
    return _publish_command("set_mode", {"mode": body.get("mode", "")})


@router.post("/api/config/challenge_type")
async def set_challenge_type(request: Request):
    """Publish a challenge-type change to the worker."""
    body = await read_json_body(request)
    return _publish_command("set_challenge_type", {"challenge_type": body.get("challenge_type", "")})


@router.post("/api/config/program")
async def set_program(request: Request):
    """Publish a program change to the worker."""
    body = await read_json_body(request)
    return _publish_command("set_program", {"program": body.get("program", "")})


@router.post("/api/config/phase")
async def set_phase(request: Request):
    """Publish a phase change to the worker."""
    body = await read_json_body(request)
    return _publish_command("set_phase", {"phase": body.get("phase")})


@router.post("/api/action/rescan")
def action_rescan():
    """Publish a rescan command to the worker."""
    return _publish_command("rescan", {})


@router.post("/api/action/restart")
def action_restart() -> dict:
    """Request a worker loop restart via the runtime-state flag."""
    state = get_runtime_state()
    state["restart_requested"] = True
    set_runtime_state(state)
    log.info("API: Restart requested via API")
    return {"status": "restart_requested"}


@router.post("/api/purge", dependencies=[Depends(require_auth)])
async def purge(request: Request) -> dict:
    """Run a durable purge of the requested targets (auth required)."""
    body = await read_json_body(request)
    targets = body.get("targets")
    if targets is not None and not isinstance(targets, list):
        raise HTTPException(status_code=400, detail="targets must be a list or omitted")
    from tradegumi.purge import purge_all
    try:
        results = purge_all(targets=targets)
        log.info("API: Purge executed — targets=%s, results=%s", targets, results)
        return {"ok": True, "results": results}
    except Exception as e:
        log.error("API: Purge failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

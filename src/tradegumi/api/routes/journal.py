"""Signal Journal router — reads, grading mutations, export, and purge.

Read (`/api/data/journal`) and the grade/invalidate/notes/reset POST mutations
are open; export (`GET /api/journal/export`) and purge (`DELETE /api/journal`)
require the API token. Behavior mirrors the previous stdlib server.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response

from tradegumi.api.deps import query_param, read_json_body, require_auth

router = APIRouter()


@router.get("/api/data/journal")
def get_journal():
    """Return all Signal Journal records (open)."""
    from tradegumi.journal import read_journal
    return read_journal()


@router.get("/api/journal/export", dependencies=[Depends(require_auth)])
def export_journal(request: Request):
    """Export selected Signal Journal records as CSV (auth required)."""
    try:
        from tradegumi.journal import SignalJournalExportSelection, build_journal_export
        selection = SignalJournalExportSelection(
            grade=query_param(request, "grade"),
            start=query_param(request, "start"),
            end=query_param(request, "end"),
            symbol=query_param(request, "symbol"),
            status=query_param(request, "status"),
            final_decision=query_param(request, "final_decision"),
            strategy=query_param(request, "strategy"),
            mode=query_param(request, "mode"),
            graded_state=query_param(request, "graded_state"),
        )
        export = build_journal_export(selection)
        if export.record_count == 0:
            raise HTTPException(
                status_code=404,
                detail="No Signal Journal records match the selected export range.",
            )
        return Response(
            content=export.csv_text,
            media_type=export.content_type,
            headers={"Content-Disposition": export.content_disposition},
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/journal/grade")
async def grade_journal(request: Request) -> dict:
    """Grade a signal by id (open). 400 on missing fields, 404 if not found."""
    body = await read_json_body(request)
    signal_id = body.get("signal_id", "").strip()
    grade = body.get("grade", "").strip().upper()
    notes = body.get("notes", "").strip()
    if not signal_id or not grade:
        raise HTTPException(status_code=400, detail="signal_id and grade are required")
    from tradegumi.journal import grade_by_signal_id
    if grade_by_signal_id(signal_id, grade, notes):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Signal not found or invalid grade")


@router.post("/api/journal/invalidate")
async def invalidate_journal(request: Request) -> dict:
    """Invalidate a signal by id (open)."""
    body = await read_json_body(request)
    signal_id = body.get("signal_id", "").strip()
    notes = body.get("notes", "").strip()
    if not signal_id:
        raise HTTPException(status_code=400, detail="signal_id is required")
    from tradegumi.journal import invalidate_signal
    if invalidate_signal(signal_id, notes):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Signal not found")


@router.post("/api/journal/notes")
async def notes_journal(request: Request) -> dict:
    """Set notes for a signal by id (open)."""
    body = await read_json_body(request)
    signal_id = body.get("signal_id", "").strip()
    notes = body.get("notes", "").strip()
    if not signal_id:
        raise HTTPException(status_code=400, detail="signal_id is required")
    from tradegumi.journal import set_notes_by_signal_id
    if set_notes_by_signal_id(signal_id, notes):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Signal not found")


@router.post("/api/journal/reset")
async def reset_journal(request: Request) -> dict:
    """Reset a signal to pending by id (open)."""
    body = await read_json_body(request)
    signal_id = body.get("signal_id", "").strip()
    if not signal_id:
        raise HTTPException(status_code=400, detail="signal_id is required")
    from tradegumi.journal import reset_signal_to_pending
    if reset_signal_to_pending(signal_id):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Signal not found")


@router.delete("/api/journal", dependencies=[Depends(require_auth)])
def purge_journal(request: Request):
    """Purge journal entries by grade (auth required)."""
    try:
        from tradegumi.journal import purge_journal_entries
        return purge_journal_entries(query_param(request, "grade"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

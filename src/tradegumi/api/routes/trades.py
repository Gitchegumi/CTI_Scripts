"""Trades router — broker-sourced reads and operator manual trades.

Broker-backed reads (`/api/positions`, `/api/trades`) are open but return
``503`` when no read-only client is available. ``/api/trades/history`` and all
``/api/trades/manual*`` endpoints require the API token. The API places NO
orders — it only reads from the broker (Constitution III, FR-004). The
deprecated ``/api/manual-trades*`` paths are rewritten to these routes by the
app's alias middleware.
"""
from __future__ import annotations

from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request, HTTPException

from tradegumi import config
from tradegumi.api.deps import (
    get_api_execution_client,
    query_param,
    read_json_body,
    require_auth,
    source_trade_history,
)
from tradegumi.manual_trades import _now_iso as manual_now_iso

router = APIRouter()


@router.get("/api/positions")
def get_positions():
    """Return open broker positions; ``503`` if no read-only client."""
    client = get_api_execution_client()
    if not client:
        raise HTTPException(status_code=503, detail="client not available")
    try:
        positions = client.get_open_positions()
        return [{
            "id": p.id,
            "symbol": p.symbol,
            "side": p.side,
            "volume": p.volume,
            "open_price": p.open_price,
            "current_price": p.current_price,
            "stop_loss": p.stop_loss,
            "take_profit": p.take_profit,
            "unrealized_pl": p.unrealized_pl,
            "net_profit": p.net_profit,
        } for p in positions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/trades/history", dependencies=[Depends(require_auth)])
def get_trades_history(request: Request):
    """Return merged dashboard trade history (auth required)."""
    try:
        from tradegumi.manual_trades import get_dashboard_trade_history
        count = int(query_param(request, "count") or query_param(request, "limit") or 50)
        source_trades = source_trade_history(count=max(count, 1000))
        history_params = {
            "bot_mode": config.TRADEGUMI_MODE,
            "symbol": query_param(request, "symbol"),
            "tag": query_param(request, "tag"),
            "start_date": query_param(request, "start_date"),
            "end_date": query_param(request, "end_date"),
            "count": count,
        }
        try:
            history = get_dashboard_trade_history(source_trades=source_trades, **history_params)
        except Exception as merge_error:
            import logging as log
            log.warning("API: source trade history could not be merged for dashboard: %s", merge_error)
            history = get_dashboard_trade_history(source_trades=[], **history_params)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/trades")
def get_broker_trades(request: Request):
    """Return raw broker trade history (open); ``503`` if no read-only client."""
    client = get_api_execution_client()
    if not client:
        raise HTTPException(status_code=503, detail="client not available")
    count = 50
    count_param = query_param(request, "count")
    if count_param:
        count = int(count_param)
    try:
        trades = client.get_trade_history(count=count)
        return [{
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "volume": t.volume,
            "open_price": t.open_price,
            "close_price": t.close_price,
            "open_time": t.open_time,
            "close_time": t.close_time,
            "realized_pl": t.realized_pl,
            "financing": t.financing,
            "pnl": t.pnl,
        } for t in trades]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/trades/manual", dependencies=[Depends(require_auth)])
def list_manual_trades(request: Request):
    """List manual trades with optional filters (auth required)."""
    try:
        from tradegumi.manual_trades import get_all_trades
        limit = int(query_param(request, "limit") or 100)
        source_trades = source_trade_history(count=max(limit, 1000))
        return get_all_trades(
            symbol=query_param(request, "symbol"),
            status=query_param(request, "status"),
            start_date=query_param(request, "start_date"),
            end_date=query_param(request, "end_date"),
            tag=query_param(request, "tag"),
            limit=limit,
            bot_mode=config.TRADEGUMI_MODE,
            source_trades=source_trades,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/trades/manual/export", dependencies=[Depends(require_auth)])
def export_manual_trades(request: Request):
    """Export manual-trade agent data (auth required)."""
    try:
        from tradegumi.manual_trades import export_agent_data
        limit = int(query_param(request, "limit") or 1000)
        source_trades = source_trade_history(count=max(limit, 1000))
        return export_agent_data(
            source_trades=source_trades,
            bot_mode=config.TRADEGUMI_MODE,
            symbol=query_param(request, "symbol"),
            status=query_param(request, "status"),
            tag=query_param(request, "tag"),
            start_date=query_param(request, "start_date"),
            end_date=query_param(request, "end_date"),
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/trades/manual/stats", dependencies=[Depends(require_auth)])
def manual_trade_stats():
    """Return manual-trade summary statistics (auth required)."""
    try:
        from tradegumi.manual_trades import get_summary_stats
        source_trades = source_trade_history(count=1000)
        return get_summary_stats(
            source_trades=source_trades,
            bot_mode=config.TRADEGUMI_MODE,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/trades/manual", status_code=201, dependencies=[Depends(require_auth)])
async def create_manual_trade(request: Request):
    """Create a new manual trade (auth required); ``201`` on success."""
    body = await read_json_body(request)
    try:
        from tradegumi.manual_trades import TradePermissionError, create_trade
        symbol = body.get("symbol", "").strip().upper()
        direction = body.get("direction", "").lower()
        entry_price = float(body.get("entry_price", 0))
        exit_price = body.get("exit_price")
        if exit_price is not None:
            exit_price = float(exit_price)
        entry_time = body.get("entry_time", manual_now_iso())
        exit_time = body.get("exit_time")
        notes = body.get("notes", "")
        tags = body.get("tags", [])
        volume = body.get("volume")
        if volume is not None:
            volume = float(volume)
        fees = float(body.get("fees", 0) or 0)

        if not symbol or direction not in ("long", "short"):
            raise HTTPException(status_code=400, detail="symbol and direction (long/short) are required")

        if exit_price is not None and not exit_time:
            exit_time = manual_now_iso()

        return create_trade(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time,
            exit_price=exit_price,
            exit_time=exit_time,
            notes=notes,
            tags=tags,
            volume=volume,
            fees=fees,
            bot_mode=config.TRADEGUMI_MODE,
        )
    except HTTPException:
        raise
    except TradePermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/trades/manual/{trade_id:path}")
def manual_trade_post_not_allowed(trade_id: str):
    """Reject POST to a specific manual-trade id with the legacy 405 message."""
    raise HTTPException(status_code=405, detail="Method not allowed — use PUT or DELETE")


@router.put("/api/trades/manual/{trade_id:path}", dependencies=[Depends(require_auth)])
async def update_manual_trade(trade_id: str, request: Request):
    """Update a manual trade by id (auth required)."""
    body = await read_json_body(request)
    trade_identity = unquote(trade_id)
    try:
        from tradegumi.manual_trades import (
            TradeNotFoundError,
            TradePermissionError,
            update_trade_record,
        )
        return update_trade_record(
            trade_identity,
            body,
            bot_mode=config.TRADEGUMI_MODE,
            source_trades=source_trade_history(count=1000),
        )
    except TradePermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except TradeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/trades/manual/{trade_id:path}", dependencies=[Depends(require_auth)])
def delete_manual_trade(trade_id: str) -> dict:
    """Delete a manual trade by id (auth required)."""
    trade_identity = unquote(trade_id)
    try:
        from tradegumi.manual_trades import (
            TradeNotFoundError,
            TradePermissionError,
            delete_trade_record,
        )
        delete_trade_record(trade_identity, bot_mode=config.TRADEGUMI_MODE)
        return {"ok": True}
    except TradePermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except TradeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

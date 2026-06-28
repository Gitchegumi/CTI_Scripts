"""Strategy-metrics router — `/api/strategies` and `/api/strategy-metrics/*`.

Read-only durable analytics served from Postgres. All endpoints are open (no
auth). Required date-range parameters return ``400`` when missing; value errors
map to ``400`` and unexpected failures to ``500`` (parity with the previous
server).
"""
from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException

from tradegumi.api.deps import query_param

router = APIRouter()


@router.get("/api/strategies")
def get_strategies_route():
    """Return the registered strategies; ``500`` on unexpected failure."""
    try:
        from tradegumi.strategy_registry import get_strategies
        return get_strategies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/strategy-metrics/summary")
def strategy_metrics_summary(request: Request):
    """Return the strategy-metrics summary for a date range."""
    try:
        from tradegumi.strategy_metrics import get_summary
        from tradegumi.persistence import get_db
        db = get_db()
        start = query_param(request, "start")
        end = query_param(request, "end")
        if not start or not end:
            raise HTTPException(status_code=400, detail="start and end are required")
        return get_summary(
            start,
            end,
            symbol=query_param(request, "symbol"),
            strategy=query_param(request, "strategy"),
            signal_type=query_param(request, "signal_type"),
            decision=query_param(request, "decision"),
            first_blocker=query_param(request, "first_blocker"),
            db=db,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/strategy-metrics/opportunities")
def strategy_metrics_opportunities(request: Request):
    """Return strategy opportunities (with near-miss filters) for a date range."""
    try:
        from tradegumi.strategy_metrics import get_opportunities
        from tradegumi.persistence import get_db
        db = get_db()
        start = query_param(request, "start")
        end = query_param(request, "end")
        near_miss_param = query_param(request, "near_miss")
        limit = int(query_param(request, "limit") or 100)
        offset = int(query_param(request, "offset") or 0)
        near_miss = None
        if near_miss_param is not None:
            near_miss = near_miss_param.lower() == "true"
        if not start or not end:
            raise HTTPException(status_code=400, detail="start and end are required")
        return get_opportunities(
            start,
            end,
            symbol=query_param(request, "symbol"),
            decision=query_param(request, "decision"),
            strategy=query_param(request, "strategy"),
            signal_type=query_param(request, "signal_type"),
            first_blocker=query_param(request, "first_blocker"),
            near_miss=near_miss,
            near_miss_reason=query_param(request, "near_miss_reason"),
            criterion=query_param(request, "criterion"),
            limit=limit,
            offset=offset,
            db=db,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/strategy-metrics/lifecycle-events")
def strategy_metrics_lifecycle_events(request: Request):
    """Return lifecycle events for a metric over a date range."""
    try:
        from tradegumi.strategy_metrics import get_lifecycle_events
        start = query_param(request, "start")
        end = query_param(request, "end")
        metric = query_param(request, "metric")
        limit = int(query_param(request, "limit") or 100)
        offset = int(query_param(request, "offset") or 0)
        if not start or not end:
            raise HTTPException(status_code=400, detail="start and end are required")
        if not metric:
            raise HTTPException(status_code=400, detail="metric is required")
        return get_lifecycle_events(
            start,
            end,
            metric,
            symbol=query_param(request, "symbol"),
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/strategy-metrics/compare")
def strategy_metrics_compare(request: Request):
    """Compare two periods of strategy metrics."""
    try:
        from tradegumi.strategy_metrics import compare_periods
        from tradegumi.persistence import get_db
        db = get_db()
        base_start = query_param(request, "base_start")
        base_end = query_param(request, "base_end")
        compare_start = query_param(request, "compare_start")
        compare_end = query_param(request, "compare_end")
        if not all([base_start, base_end, compare_start, compare_end]):
            raise HTTPException(
                status_code=400,
                detail="base_start, base_end, compare_start, and compare_end are required",
            )
        return compare_periods(
            base_start,
            base_end,
            compare_start,
            compare_end,
            symbol=query_param(request, "symbol"),
            db=db,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/strategy-metrics/export")
def strategy_metrics_export(request: Request):
    """Export the strategy-metrics summary (optionally with opportunities)."""
    try:
        from tradegumi.strategy_metrics import export_summary
        from tradegumi.persistence import get_db
        db = get_db()
        start = query_param(request, "start")
        end = query_param(request, "end")
        include = (query_param(request, "include_opportunities") or "false").lower() == "true"
        if not start or not end:
            raise HTTPException(status_code=400, detail="start and end are required")
        return export_summary(
            start,
            end,
            symbol=query_param(request, "symbol"),
            strategy=query_param(request, "strategy"),
            signal_type=query_param(request, "signal_type"),
            decision=query_param(request, "decision"),
            first_blocker=query_param(request, "first_blocker"),
            include_opportunities=include,
            db=db,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""FastAPI application factory for the TradeGumi API service.

``create_app()`` builds the ASGI app served by Uvicorn (see
``tradegumi.api_main``). It mounts the per-concern routers, reproduces the
legacy CORS behavior, rewrites the deprecated ``/api/manual-trades`` path
aliases, and installs exception handlers that keep error bodies shaped like the
previous stdlib server (``{"error": ...}`` — never FastAPI's ``{"detail": ...}``
or a raw ``422``). Interactive docs (``/docs``, ``/redoc``, ``/openapi.json``)
are intentionally enabled as the single additive surface (FR-020); they do not
alter any ``/api/*`` behavior. See specs/023-fastapi-api-migration.
"""
from __future__ import annotations

import logging as log

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from tradegumi.api.routes import (
    config_actions,
    data,
    journal,
    status,
    strategy_metrics,
    trades,
)

# Default exception details Starlette emits that we must translate back to the
# legacy lowercase phrasing for byte-compatible-enough parity.
_DEFAULT_404_DETAILS = {None, "Not Found"}
_DEFAULT_405_DETAILS = {None, "Method Not Allowed"}


def _rewrite_manual_trades_path(path: str) -> str:
    """Map the deprecated ``/api/manual-trades*`` paths to the canonical ones.

    Reproduces the previous handler's ``_route_path`` rewrite so any client
    still using the older path resolves to the same manual-trades handler
    (FR-014).
    """
    if path == "/api/manual-trades":
        return "/api/trades/manual"
    if path.startswith("/api/manual-trades/"):
        return "/api/trades/manual/" + path[len("/api/manual-trades/"):]
    return path


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    Wires CORS, the path-alias middleware, parity exception handlers, and every
    concern router. Safe to call multiple times (e.g. per test) — it holds no
    process-global state of its own.
    """
    app = FastAPI(
        title="TradeGumi API",
        version="1.0.0",
        description=(
            "Analytics and operator-control API for the TradeGumi signal engine. "
            "Read-only with respect to broker execution — order placement is "
            "worker-only. Mirrors the endpoints previously served by the stdlib "
            "API server."
        ),
    )

    # CORS: reproduce the legacy `_send_cors`/`do_OPTIONS` behavior so the
    # dashboard can call the API from its own origin (FR-013).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def manual_trades_alias(request: Request, call_next):
        """Rewrite deprecated ``/api/manual-trades*`` request paths in-place.

        Mutates the ASGI scope before routing so the alias resolves to the
        canonical ``/api/trades/manual*`` route (FR-014).
        """
        rewritten = _rewrite_manual_trades_path(request.scope.get("path", ""))
        if rewritten != request.scope.get("path"):
            request.scope["path"] = rewritten
            raw = rewritten.encode("utf-8")
            request.scope["raw_path"] = raw
        return await call_next(request)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Render HTTP errors as the legacy ``{"error": <detail>}`` shape.

        Translates Starlette's default 404/405 phrasing back to the previous
        server's lowercase messages so unmatched routes return
        ``{"error": "not found"}`` / ``{"error": "Method not allowed"}`` rather
        than FastAPI's ``{"detail": ...}`` (parity, FR-002).
        """
        detail = exc.detail
        if exc.status_code == 404 and detail in _DEFAULT_404_DETAILS:
            detail = "not found"
        elif exc.status_code == 405 and detail in _DEFAULT_405_DETAILS:
            detail = "Method not allowed"
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Map request-validation failures to a legacy ``400 {"error": ...}``.

        The previous server never emitted ``422``/``{"detail": [...]}``; this
        safety net keeps that contract for any validation the routes do not
        handle explicitly (research Decision 4).
        """
        errors = exc.errors()
        message = "invalid request"
        if errors:
            first = errors[0]
            loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
            message = f"{loc}: {first.get('msg')}".strip(": ") or message
        return JSONResponse({"error": message}, status_code=400)

    for router in (
        status.router,
        data.router,
        strategy_metrics.router,
        journal.router,
        trades.router,
        config_actions.router,
    ):
        app.include_router(router)

    log.debug("TradeGumi FastAPI app created")
    return app

# API Endpoint Contract & Parity Inventory

**Feature**: 023-fastapi-api-migration
**Date**: 2026-06-28
**Source of truth**: current behavior of `src/tradegumi/api_server.py`

This is the authoritative parity checklist. Every row MUST behave identically
after migration (structural/semantic parity per spec Q1). "Auth" = endpoint
currently calls `_require_auth()` (rejects with `401 {"error":"Unauthorized"}`
when `JOURNAL_TOKEN` is set). Router = target module under `src/tradegumi/api/routes/`.

## GET

| Path | Auth | Success | Notable errors | Router |
|------|------|---------|----------------|--------|
| `/api/status` | no | 200 merged config+runtime incl. `worker_live` | — | status |
| `/api/data/loop_state` | no | 200 runtime snapshot (or file) | — | data |
| `/api/data/watchlist` | no | 200 watchlist (default `{symbols:[],mode,provider}`) | — | data |
| `/api/data/signals` | no | 200 signals (default tiers obj) | — | data |
| `/api/strategies` | no | 200 strategy list | 500 `{error}` | strategy_metrics |
| `/api/strategy-metrics/summary` | no | 200 summary | 400 missing start/end; 400 bad; 500 | strategy_metrics |
| `/api/strategy-metrics/opportunities` | no | 200 | 400 missing start/end; 400 bad; 500 | strategy_metrics |
| `/api/strategy-metrics/lifecycle-events` | no | 200 | 400 missing start/end; 400 missing metric; 400 bad; 500 | strategy_metrics |
| `/api/strategy-metrics/compare` | no | 200 | 400 missing base/compare ranges; 400 bad; 500 | strategy_metrics |
| `/api/strategy-metrics/export` | no | 200 export | 400 missing start/end; 400 bad; 500 | strategy_metrics |
| `/api/data/journal` | no | 200 journal list | — | journal |
| `/api/journal/export` | **yes** | 200 text/CSV export | 404 empty range; 400 bad; 500 | journal |
| `/api/data/trade_correlations` | no | 200 (default `[]`) | — | data |
| `/api/prices` | no | 200 observations | — | data |
| `/api/positions` | no | 200 positions | 503 client not available; 500 | trades |
| `/api/trades/history` | **yes** | 200 history | 503 client not available; 500 | trades |
| `/api/trades/manual` | **yes** | 200 manual trades | 500 | trades |
| `/api/trades/manual/export` | **yes** | 200 export | 500 | trades |
| `/api/trades/manual/stats` | **yes** | 200 stats | 500 | trades |
| _unmatched GET_ | — | — | 404 `{error:"not found"}` | app handler |

## POST

| Path | Auth | Success | Notable errors | Router |
|------|------|---------|----------------|--------|
| `/api/config/mode` | no | 200 `{status:accepted,command_id}` | 400 bad cmd; 503 undelivered | config_actions |
| `/api/config/challenge_type` | no | accepted | 400; 503 | config_actions |
| `/api/config/program` | no | accepted | 400; 503 | config_actions |
| `/api/config/phase` | no | accepted | 400; 503 | config_actions |
| `/api/journal/grade` | no | 200 `{ok:true}` | 400 missing signal_id/grade; 404 not found/invalid | journal |
| `/api/journal/invalidate` | no | 200 `{ok:true}` | 400 missing signal_id; 404 | journal |
| `/api/journal/notes` | no | 200 `{ok:true}` | 400 missing signal_id; 404 | journal |
| `/api/journal/reset` | no | 200 `{ok:true}` | 400 missing signal_id; 404 | journal |
| `/api/trades/manual` | **yes** | 200/201 created record | 400/403/404/500 per manual_trades | trades |
| `/api/trades/manual/...` (POST) | — | — | 405 `{error:"Method not allowed — use PUT or DELETE"}` | trades |
| `/api/action/rescan` | no | 200 `{status:accepted,command_id}` | 400; 503 undelivered | config_actions |
| `/api/action/restart` | no | 200 `{status:restart_requested}` | — | config_actions |
| `/api/purge` | **yes** | 200 `{ok:true,results}` | 400 targets-not-list; 500 | config_actions |
| _unmatched POST_ | — | — | 404 `{error:"not found"}` | app handler |

## PUT

| Path | Auth | Success | Notable errors | Router |
|------|------|---------|----------------|--------|
| `/api/trades/manual/:id` | **yes** | 200 updated record | 403 permission; 404 not found; 400 invalid; 500 | trades |
| _unmatched PUT_ | — | — | 404 `{error:"not found"}` | app handler |

## DELETE

| Path | Auth | Success | Notable errors | Router |
|------|------|---------|----------------|--------|
| `/api/journal?grade=…` | **yes** | 200 purge result | 400 bad; 500 | journal |
| `/api/trades/manual/:id` | **yes** | 200 `{ok:true}` | 403 permission; 404 not found; 500 | trades |
| _unmatched DELETE_ | — | — | 404 `{error:"not found"}` | app handler |

## OPTIONS

| Path | Behavior |
|------|----------|
| any | 204 + CORS headers (`Allow-Origin:*`, `Allow-Methods: GET,POST,PUT,DELETE,OPTIONS`, `Allow-Headers: Content-Type,X-API-Key`) |

## Path aliases (FR-014)

| Legacy path | Canonical | Notes |
|-------------|-----------|-------|
| `/api/manual-trades` | `/api/trades/manual` | exact-match rewrite |
| `/api/manual-trades/<rest>` | `/api/trades/manual/<rest>` | prefix rewrite |

## Cross-cutting requirements

- **CORS**: `Access-Control-Allow-Origin: *` on all responses; preflight via OPTIONS (FR-013).
- **Auth body**: 401 responses use `{"error": "Unauthorized"}` (not FastAPI default `{"detail": ...}`).
- **Validation body**: 400 responses use `{"error": "<message>"}` with the same messages; **no raw 422** (Decision 4).
- **Not found / method not allowed**: preserve `{"error":"not found"}` (404) and `{"error":"Method not allowed"}` (405) bodies, not FastAPI defaults.
- **No order placement**: there is NO endpoint that places a broker order, and none MUST be added (FR-004, Constitution III).
- **Docs (FR-020, new)**: `/docs`, `/redoc`, `/openapi.json` exposed, ungated; they MUST NOT change any `/api/*` behavior.

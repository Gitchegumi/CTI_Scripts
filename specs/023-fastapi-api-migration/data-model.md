# Phase 1 Data Model: FastAPI Migration

**Feature**: 023-fastapi-api-migration
**Date**: 2026-06-28

This is a transport/framework refactor: it introduces **no new persisted
entities and no schema changes**. Postgres tables, Redis keys, and the JSON
state files keep their current shapes. The "entities" below are the request/
response and dependency objects the API operates on — they define the parity
contract and the shared-dependency surface, not new storage.

## Shared Dependencies (provided to routes)

These replace the module-level helpers and per-handler imports in
`api_server.py`. Each is a FastAPI dependency in `api/deps.py`, reused across
routers (FR-015).

| Dependency | Provides | Source | Failure behavior |
|------------|----------|--------|------------------|
| `get_db` | Postgres backend handle | `tradegumi.persistence.get_db()` | Checked at startup (fail-fast, FR-008); per-request errors → 500 `{"error": ...}` |
| `get_cache` / runtime-state | Redis cache + `loop_state` snapshot + heartbeat | `tradegumi.persistence.redis` | Missing/stale → empty/`{}`/`worker_live=False`; never raises (FR-009) |
| `require_auth` | Asserts `X-API-Key == JOURNAL_TOKEN` | `config.JOURNAL_TOKEN` | Mismatch → 401 `{"error":"Unauthorized"}`; unset token → no-op (FR-011) |
| `get_api_execution_client` | **Read-only** broker client | `config.TRADEGUMI_MODE` → Oanda/MatchTrader | `None` when unbuildable → broker endpoints 503 (FR-010). MUST NOT place orders (FR-004) |
| `worker_live` | Worker liveness flag | Redis heartbeat freshness | Any error → `False` (FR-007) |

## Request/Response Objects (parity contract)

### Live Status (`/api/status`)
- **Response**: merged current config + runtime snapshot, including `worker_live`
  (from heartbeat, FR-007). Same keys as today. Degrades hot fields when the
  Redis snapshot is stale/absent without failing.

### Operator Command (config/action POSTs)
- **Request**: JSON body with the action-specific field (`mode`,
  `challenge_type`, `program`, `phase`) or empty (`rescan`).
- **Validation**: built via `commands.build_command(...)`; invalid → `400`
  `{"error": ...}`.
- **Response (accepted)**: `{"status": "accepted", "command_id": <id>}`.
- **Response (undelivered)**: `503` `{"error": "command not delivered — command
  channel unavailable", "type": <cmd_type>}` — never a false success (FR-006).
- `/api/action/restart` keeps its current local behavior:
  `{"status": "restart_requested"}` (sets `restart_requested` in runtime state).

### Signal Journal Entry (`/api/data/journal`, `/api/journal/*`, `DELETE /api/journal`)
- **Read** (`/api/data/journal`): list of journal records (open).
- **Mutations** (`grade`, `invalidate`, `notes`, `reset` — POST, open): require
  `signal_id` (+ `grade` for grade); missing → `400 {"error": ...}`; not found /
  invalid grade → `404`; success → `{"ok": true}`.
- **Export** (`GET /api/journal/export`, protected): text/CSV export; empty range
  → `404 {"error": ...}`; bad params → `400`.
- **Purge by grade** (`DELETE /api/journal`, protected): `{ "grade": <param> }`.

### Manual Trade Record (`/api/trades/manual*`, alias `/api/manual-trades*`)
- **List** (GET, protected), **Create** (POST, protected),
  **Update** (PUT `/:id`, protected), **Delete** (DELETE `/:id`, protected),
  **Export** (GET `/export`, protected), **Stats** (GET `/stats`, protected).
- Errors map to existing codes: permission → `403`, not found → `404`,
  validation → `400`, else `500` — all `{"error": ...}`. Success → record JSON or
  `{"ok": true}`.

### Strategy Metrics / Analytics (`/api/strategies`, `/api/strategy-metrics/*`)
- **Read-only** Postgres aggregates (open). Date-range params required where the
  current code requires them; missing → `400 {"error": ...}`; bad values → `400`;
  internal error → `500`. Response shapes unchanged
  (`summary`, `opportunities`, `lifecycle-events`, `compare`, `export`).

### Broker-sourced Data (`/api/positions`, `/api/trades/history`, `/api/prices`)
- **Read-only**; require the execution client. Client absent → `503
  {"error": "client not available"}` (FR-010). `/api/trades/history` is protected.

### File/State Reads (`/api/data/loop_state|watchlist|signals`, `/api/data/trade_correlations`)
- Served from the read-only data volume / runtime snapshot; missing file →
  documented empty default (`[]` / `{...}`) exactly as today.

## State Transitions

No new state machines. The only state mutations the API mediates are the
**existing** ones, unchanged:
- Journal entry: `pending → graded/invalidated/notes-updated → reset(pending)`
  (delegated to `tradegumi.journal`).
- Operator command: `built → published(accepted) | rejected(400) | undelivered(503)`.
- Manual trade: `created → updated → deleted` (delegated to
  `tradegumi.manual_trades`, subject to its permission rules).

## Invariants (must hold post-migration)

1. The API exposes **no** order-placement route (Constitution III, FR-004).
2. Per-endpoint auth split (protected vs open) is preserved exactly (FR-011).
3. Every endpoint's status codes + parsed response structure match the current
   implementation (FR-002, structural parity).
4. Startup fails fast iff Postgres is unreachable; Redis/broker outages degrade
   (FR-008–FR-010).
5. Legacy `/api/manual-trades*` paths resolve to the manual-trades handlers
   (FR-014).

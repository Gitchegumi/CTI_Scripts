# Phase 0 Research: FastAPI Migration of the TradeGumi API Service

**Feature**: 023-fastapi-api-migration
**Date**: 2026-06-28

This document resolves the open technical decisions implied by the spec and
plan. The two product-level ambiguities (response-body strictness, docs surface)
were already resolved in the spec's Clarifications session; the items below are
the implementation decisions the framework cutover forces.

---

## Decision 1 — Serialization model that preserves structural parity

**Decision**: Use FastAPI's default `JSONResponse` (compact JSON) and return
plain `dict`/`list` payloads from route handlers, relying on structural/semantic
parity (spec Q1 → A). Do **not** reproduce the legacy `json.dumps(..., indent=2)`
pretty-printing. Use `default=str`-equivalent behavior by ensuring non-JSON-native
values (datetimes, Decimals) are stringified the same way the current code does;
where a handler today calls `json.dumps(data, default=str)`, the migrated handler
must coerce the same fields so values (not whitespace) match.

**Rationale**: The clarification fixed parity at the parsed-structure level. The
dashboard consumes responses via `res.json()`, so whitespace and `Content-Length`
are irrelevant. Avoiding a custom pretty-printing renderer keeps the code simple
and idiomatic.

**Watch-out**: The current code serializes with `default=str`, so any datetime/
Decimal currently emitted as a string must still be a string after migration.
Parity tests assert on parsed values, so a field silently becoming a number/object
will be caught.

**Alternatives considered**:
- *Custom response class reproducing `indent=2`*: rejected — adds code for a
  byte-level guarantee the spec explicitly waived.

---

## Decision 2 — Sync route handlers (no async rewrite of I/O)

**Decision**: Define route handlers as **synchronous** (`def`, not `async def`).
FastAPI runs sync handlers in a threadpool, so the existing blocking psycopg/
redis-py/`requests`-based broker calls work unchanged without an async rewrite.

**Rationale**: All downstream libraries (psycopg 3 used synchronously, redis-py,
the `requests`/cloudscraper broker clients) are blocking. Rewriting to async would
be a large, risky change outside the parity scope and would touch the execution
clients (explicitly out of scope). Sync-in-threadpool preserves behavior and
concurrency semantics close to the current threaded `HTTPServer`.

**Alternatives considered**:
- *Async handlers + run_in_executor wrapping*: rejected — more code, no benefit at
  operator-tooling request volume.
- *Async DB/redis drivers*: rejected — out of scope; would rework persistence.

---

## Decision 3 — Authentication as a reusable dependency

**Decision**: Implement auth as a FastAPI dependency (`require_auth`) that reads
the `X-API-Key` header, compares against `config.JOURNAL_TOKEN`, and raises
`HTTPException(401, {"error": "Unauthorized"})` on mismatch. When
`JOURNAL_TOKEN` is unset, the dependency is a no-op (auth disabled), matching
`_check_auth()` today. Apply it only to the endpoints that currently call
`_require_auth()` (see contract for the exact per-endpoint list); leave currently
open endpoints open.

**Rationale**: Preserves FR-011 (per-endpoint parity of protected vs. open) and
centralizes the token check as a shared dependency (FR-015). The error body must
be `{"error": "Unauthorized"}` to match the current response shape, so a custom
exception handler / explicit `JSONResponse` is used rather than FastAPI's default
`{"detail": ...}` envelope.

**Per-endpoint auth inventory** (from `api_server.py`): protected =
`GET /api/journal/export`, `GET /api/trades/history`, `GET /api/trades/manual`,
`GET /api/trades/manual/export`, `GET /api/trades/manual/stats`,
`PUT /api/trades/manual/:id`, `DELETE /api/journal`,
`DELETE /api/trades/manual/:id`, `POST /api/trades/manual`, `POST /api/purge`.
Open (no auth today): `/api/status`, `/api/data/*`, `/api/prices`,
`/api/positions`, `/api/strategies`, `/api/strategy-metrics/*`, all
`/api/config/*`, `/api/action/*`, and all `/api/journal/*` POSTs (grade,
invalidate, notes, reset). This split MUST be preserved exactly.

---

## Decision 4 — Validation & error-envelope compatibility (avoid 422)

**Decision**: Do **not** rely on FastAPI/Pydantic automatic request-body
validation for parity-critical fields, because its failure mode is `422` with a
`{"detail": [...]}` envelope. Instead, read the JSON body loosely (as the current
`_read_body()` does — empty/invalid body → `{}`) and reproduce the existing
explicit checks that return `400` with `{"error": "..."}` (e.g. "signal_id and
grade are required", "start and end are required", "targets must be a list or
omitted"). Pydantic models MAY be used internally for clarity, but the
validation-failure response must be mapped to the legacy `400 {"error": ...}`
shape, never raw `422`.

**Rationale**: FR-002 and FR-015 require error responses compatible with today's
behavior. The current API never emits `422` and never the `{"detail": ...}`
envelope. Parity tests assert the legacy status codes and `{"error": ...}` bodies.

**Alternatives considered**:
- *Native Pydantic validation with default 422*: rejected — breaks parity.
- *Global 422→400 exception handler reshaping `detail`→`error`*: viable as a
  safety net, but explicit checks are clearer and match the exact messages.

---

## Decision 5 — CORS, OPTIONS, and headers

**Decision**: Add `CORSMiddleware` with `allow_origins=["*"]`,
`allow_methods=["GET","POST","PUT","DELETE","OPTIONS"]`, and
`allow_headers=["Content-Type","X-API-Key"]`, reproducing the current
`_send_cors()` headers and the `do_OPTIONS` 204 preflight response.
`Access-Control-Allow-Origin: *` must appear on normal responses too (the current
code sets it on every `_send_json`/`_send_text`); `CORSMiddleware` covers this for
allowed origins.

**Rationale**: FR-013 — the dashboard calls the API from its own origin/proxy and
relies on these headers and preflight handling.

---

## Decision 6 — Startup fail-fast and lifecycle

**Decision**: Keep `api_main.main()` as the module entrypoint
(`python -m tradegumi.api_main`, unchanged in `entrypoint.api.sh`). Retain the
explicit Postgres reachability check (`get_db()`) that raises before serving
(FR-008). Boot Uvicorn programmatically (`uvicorn.run(create_app(), host=..,
port=API_PORT)` or `uvicorn.Server`) so SIGTERM/SIGINT still trigger a clean
shutdown. The Postgres check stays in `api_main` (before Uvicorn starts) — not in
a FastAPI `lifespan` startup hook — so failure prevents the server from binding at
all, exactly as today.

**Rationale**: Preserves the fail-fast guarantee and the existing graceful-
shutdown semantics while swapping the transport. Redis/broker remain optional at
startup (degrade, not fail) per FR-009/FR-010.

**Alternatives considered**:
- *Postgres check inside FastAPI `lifespan`*: workable, but Uvicorn would already
  be binding/logging; keeping it in `api_main` matches current "refuse to start"
  behavior most precisely.

---

## Decision 7 — Auto-generated docs (FR-020)

**Decision**: Leave FastAPI's default docs enabled — `/docs` (Swagger UI),
`/redoc`, and `/openapi.json` — as the single intentional surface addition
(spec Q2 → B). Set a clear app `title`/`version`/`description`. No auth gate on
docs (Option B chosen, not C). Unknown non-doc paths still return the existing
`404 {"error": "not found"}` via a custom 404 handler so non-API 404s keep the
legacy body.

**Rationale**: Matches the clarification. Provides route discovery for developers
(FR-015 intent) without altering any `/api/*` behavior.

**Watch-out**: FastAPI's default 404 for unmatched routes returns
`{"detail": "Not Found"}`. A custom exception handler (or explicit catch-all) is
needed so unmatched `/api/*` paths return `{"error": "not found"}` (and
`{"error": "Method not allowed"}` / 405 where the current code does) to preserve
parity.

---

## Decision 8 — Path aliasing for legacy manual-trades routes

**Decision**: Reproduce `_route_path()`'s rewrite of `/api/manual-trades` →
`/api/trades/manual` (and the `/api/manual-trades/...` prefix form). Implement by
registering the canonical `/api/trades/manual*` routes and adding alias routes (or
a small middleware) that map the legacy `/api/manual-trades*` paths to the same
handlers.

**Rationale**: FR-014 — internal aliases the current service honors must keep
resolving identically so any client still using the older path keeps working.

---

## Decision 9 — Dependencies & packaging

**Decision**: Add `fastapi` and `uvicorn[standard]` to the main Poetry
dependencies in `src/pyproject.toml`; add `httpx` to the dev group (FastAPI
`TestClient` needs it). The `Dockerfile` `python` target installs via
`poetry install`, so no Dockerfile structural change is required beyond the new
deps being in the lockfile. Port 8199, the healthcheck (`GET /api/status`), and
`entrypoint.api.sh` are unchanged.

**Rationale**: FR-019 — packaging/entrypoint updated so the rebuilt service runs
in its existing container. `requirements.txt` at repo root is a legacy/secondary
manifest (the image build uses Poetry); update it only if it is still consumed —
verified during implementation.

**Watch-out**: `uvicorn[standard]` pulls `uvloop`/`httptools`; on the
`python:3.13-slim` base these build cleanly with the already-installed
`build-essential`. Confirm the Poetry lock resolves on 3.13.

---

## Decision 10 — Test strategy for parity, auth, and command-channel failure

**Decision**: Use FastAPI `TestClient` (Starlette/httpx). Three test groups
(FR-017):
1. **Endpoint parity** — for each endpoint, assert status code + parsed response
   structure for success and the documented error cases; cover GET/POST/PUT/
   DELETE/OPTIONS and the 404/405 fallbacks. Mock the Postgres backend, Redis
   cache, and execution client via the FastAPI dependency-override mechanism.
2. **Auth behavior** — with `JOURNAL_TOKEN` set: protected endpoints return 401
   `{"error": "Unauthorized"}` without the header and succeed with it; open
   endpoints ignore the header. With `JOURNAL_TOKEN` unset: auth is a no-op.
3. **Command-channel failure** — with `commands.publish` returning falsey,
   `/api/config/*` and `/api/action/rescan` return `503` with the "command not
   delivered" body and never report success; invalid commands return `400`.

**Rationale**: Dependency overrides make parity tests fast and hermetic and prove
the no-order-placement and degrade-not-crash guarantees (SC-004, SC-005).

---

## Resolved unknowns summary

| Unknown | Resolution |
|---------|------------|
| Response formatting strictness | Structural parity; default compact JSON (Decision 1) |
| Sync vs async handlers | Sync handlers in threadpool (Decision 2) |
| Auth mechanism placement | Shared `require_auth` dependency; legacy 401 body (Decision 3) |
| Validation error envelope | Manual checks → legacy `400 {"error"}`; no raw 422 (Decision 4) |
| CORS/preflight | `CORSMiddleware` reproducing existing headers (Decision 5) |
| Fail-fast + lifecycle | Postgres check in `api_main` before Uvicorn (Decision 6) |
| Docs surface | `/docs`,`/redoc`,`/openapi.json` enabled, ungated (Decision 7) |
| Legacy path aliasing | Alias `/api/manual-trades*`→`/api/trades/manual*` (Decision 8) |
| Packaging | Add fastapi+uvicorn (main), httpx (dev); container unchanged (Decision 9) |
| Test approach | TestClient + dependency overrides; 3 groups (Decision 10) |

No `NEEDS CLARIFICATION` items remain.

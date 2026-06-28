# Implementation Plan: Refactor Python API Service to FastAPI

**Branch**: `023-fastapi-api-migration` | **Date**: 2026-06-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/023-fastapi-api-migration/spec.md`

## Summary

Replace the standalone TradeGumi API service's hand-rolled
`http.server.BaseHTTPRequestHandler` (`src/tradegumi/api_server.py`, ~950 lines,
one monolithic routing method per HTTP verb) with a FastAPI application served by
Uvicorn, while preserving every existing endpoint's paths, status codes, and
parsed response structure (structural/semantic parity per the spec
clarifications). The new app is organized into per-concern route modules (status,
data, config/actions, journal, trades, strategy-metrics, purge) wired through
shared FastAPI dependencies for the Postgres backend, Redis cache/state,
journal/auth-token handling, and the read-only execution client. Order placement
stays worker-only; the API keeps its read-only broker access. The worker process,
Redis command channel, Postgres durability, the dashboard, and the
`tradegumi-api` container's external contract are all unchanged. The one
intentional addition is FastAPI's auto-generated interactive docs and OpenAPI
schema (FR-020).

## Technical Context

**Language/Version**: Python ^3.13 (Poetry-managed, `src/pyproject.toml`; image base `python:3.13-slim`)
**Primary Dependencies**: FastAPI + Uvicorn (new); existing internal modules reused unchanged — `tradegumi.config`, `tradegumi.commands`, `tradegumi.journal`, `tradegumi.manual_trades`, `tradegumi.strategy_metrics`, `tradegumi.purge`, `tradegumi.persistence` (Postgres via psycopg 3, Redis via redis-py), `tradegumi.price_observations`, `tradegumi.api.*` execution clients
**Storage**: PostgreSQL 17 (durable analytics/journal/trades — source of truth), Redis 7 (hot-state snapshot `loop_state`, worker heartbeat, command channel), read-only shared data volume (`watchlist.json`, `signals.json`, `loop_state.json`)
**Testing**: pytest (`tool.poetry.group.dev.dependencies`); add Starlette/FastAPI `TestClient` (httpx-backed) for endpoint parity, auth, and command-channel failure coverage; existing suite under `src/tradegumi/tests/`
**Target Platform**: Linux container (`tradegumi-api` service, `Dockerfile` `python` target, port 8199), launched via `entrypoint.api.sh`
**Project Type**: Single Python backend service (web API) within a multi-service repo (worker + api + Next.js dashboard)
**Performance Goals**: Parity-preserving — no material latency change versus the current stdlib server; analytics endpoints serve from Postgres in the same request/response envelope
**Constraints**: API MUST NOT place orders (read-only broker access only); MUST fail fast if Postgres is unreachable at startup; MUST degrade (not crash) when Redis/broker are unavailable; responses must be structurally/semantically compatible with the current implementation; CORS (`*`) and `X-API-Key`/`JOURNAL_TOKEN` auth behavior preserved per-endpoint
**Scale/Scope**: ~30 endpoints across 7 concerns; single operator + dashboard consumer; low request volume (operator tooling, not public traffic)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Signal Integrity (NON-NEGOTIABLE) | PASS | No signal-detection logic is touched. This is a transport/framework refactor of the API service; the four-layer signal stack lives in the worker and is untouched. |
| II. Execution Layer Abstraction | PASS | The API continues to obtain a broker client only through the existing `get_api_execution_client()` / `ExecutionClient` abstraction for reads. No broker-specific code is introduced into the API routes; client selection stays config-driven (`TRADEGUMI_MODE`). |
| III. Risk-First (NON-NEGOTIABLE) | PASS | The API exposes **no** order-placement route and MUST NOT place orders (FR-004). Read-only broker access (positions/account/history) only. Order placement remains worker-only. Parity tests assert no order-placement path exists. |
| IV. Observable by Default | PASS | Existing logging is preserved and mapped to framework equivalents: command accept/reject/undelivered outcomes still logged (FR-006), startup/shutdown logged. No event currently posted to Discord/JSON state by the worker is removed. The API only *reads* the JSON state files. |
| V. Configuration-Driven Operations | PASS | `/api/config/*` and `/api/action/*` endpoints keep publishing to the worker via the Redis command channel with identical request/response behavior (FR-005). Port, auth token, heartbeat staleness, and mode stay env-var driven. No new hardcoded config. |
| Security & Credential Hygiene | PASS | No secrets added to source; `X-API-Key`→`JOURNAL_TOKEN` auth preserved per-endpoint (FR-011). New dependency wiring reads creds from existing config/env. `.env.example` reviewed — no new required secret (FastAPI/Uvicorn need none). |
| Code Quality & Documentation | PASS (enforced in tasks) | New route modules, dependencies, and app factory MUST carry module/class/function docstrings stating purpose, params/returns, raised exceptions, and the order-placement prohibition where relevant. A code-quality check task is included. |
| Pull Request Policy | PENDING | Reviewer not yet identified by spec/tasks/user. Per constitution, the Polish phase of `tasks.md` MUST include a non-optional final PR task; if no reviewer is identified by task generation, that task MUST instruct the implementer to ask the user to identify the reviewer before opening the PR. Memory note: dual-account workflow (DockeGumi author / Gitchegumi reviewer) — confirm with user at PR time. |

**Result**: No violations. Complexity Tracking not required. Pull Request Policy carried forward as a PENDING action resolved at task generation / PR time.

## Project Structure

### Documentation (this feature)

```text
specs/023-fastapi-api-migration/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── api-endpoints.md  # Full endpoint inventory + parity contract
├── checklists/
│   └── requirements.md  # Spec quality checklist (already present)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
src/tradegumi/
├── api_main.py          # MODIFIED: start Uvicorn against the app factory (replaces start_api_server loop)
├── api_app.py           # NEW: FastAPI app factory (create_app()) — wires routers, CORS, docs, lifespan
├── api/
│   ├── deps.py          # NEW: shared FastAPI dependencies (db backend, redis cache/state,
│   │                    #      auth/token, read-only execution client, runtime-state access)
│   ├── routes/          # NEW: per-concern routers
│   │   ├── status.py    #   /api/status
│   │   ├── data.py      #   /api/data/* , /api/prices , /api/data/trade_correlations
│   │   ├── config_actions.py  # /api/config/* , /api/action/* , /api/purge
│   │   ├── journal.py   #   /api/data/journal , /api/journal/* (incl. DELETE /api/journal)
│   │   ├── trades.py    #   /api/positions , /api/trades/* , /api/trades/manual* (GET/POST/PUT/DELETE)
│   │   └── strategy_metrics.py  # /api/strategies , /api/strategy-metrics/*
│   ├── base_client.py   # UNCHANGED (ExecutionClient abstraction)
│   ├── oanda_client.py  # UNCHANGED
│   └── matchtrader_client.py  # UNCHANGED
├── api_server.py        # REMOVED after cutover (logic migrated into api_app.py + routes/)
│                        #   — shared helpers (runtime state, get_api_execution_client,
│                        #     worker_live) relocate into api/deps.py or a small helpers module
└── tests/
    ├── test_api_reads_redis.py   # UPDATED to exercise the FastAPI app
    └── test_api_*.py             # NEW: parity / auth / command-channel TestClient suites

Dockerfile               # UPDATED: ensure fastapi+uvicorn installed via Poetry (no structural change)
src/pyproject.toml       # UPDATED: add fastapi + uvicorn[standard] to main deps; httpx to dev deps
entrypoint.api.sh        # UNCHANGED command (`python -m tradegumi.api_main`); api_main now runs Uvicorn
docker-compose.yml       # UNCHANGED (same image, port 8199, healthcheck GET /api/status)
docs/ , src/README.md    # UPDATED if local dev / startup commands change (FR-018)
```

**Structure Decision**: Single Python backend service. The current monolithic
`api_server.py` is decomposed into a FastAPI app factory (`api_app.py`), a shared
dependency module (`api/deps.py`), and seven concern-scoped routers under
`api/routes/`. The cross-process helpers that currently live in `api_server.py`
(`get_runtime_state`/`set_runtime_state`, `get_api_execution_client`,
`worker_live`) move into `api/deps.py` (or a thin helpers module imported by it)
so both the API routes and any remaining worker callers keep a single source of
truth. `api_main.py` keeps the same module entrypoint (`python -m
tradegumi.api_main`) and the same Postgres fail-fast startup check, but boots
Uvicorn against `create_app()` instead of the stdlib `HTTPServer`. The external
container contract (image, port 8199, healthcheck) is unchanged.

## Complexity Tracking

> No constitution violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

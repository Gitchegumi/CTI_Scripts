# Implementation Plan: Split Runtime into API, Dashboard, and Worker Containers

**Branch**: `019-split-runtime-containers` | **Date**: 2026-06-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/019-split-runtime-containers/spec.md`

## Summary

Today a single container runs the Python trading bot and the Next.js dashboard
under `entrypoint.sh`, which uses `wait -n` so that **either** process exiting
tears down **both**. Inside the Python process, the HTTP API server
(`api_server.py`, port 8199) runs in a background thread of `main.py` and shares
an in-memory `_runtime_state` dict with the worker loop — including the live
broker execution `client`. The dashboard already talks to the API over
`NEXT_PUBLIC_API_URL`, so it is the most loosely coupled piece.

This feature splits the runtime into three independently deployable
docker-compose services — **tradegumi-worker** (the four-layer signal loop, no
public port), **tradegumi-api** (HTTP analytics + control on 8199), and
**tradegumi-dashboard** (Next.js on 3000) — so a failure or restart of any one
service does not disturb the other two. The two hard problems are (1) the API
no longer shares memory with the worker, so the cross-process state and command
paths that exist today as `set_runtime_state`/`get_runtime_state` must move onto
the Redis/Postgres infrastructure already landed in #108, and (2) several API
read endpoints currently reach into the worker's live execution `client`, which
must be replaced with a broker-agnostic read-only path that never gains
order-placement ability.

## Technical Context

**Language/Version**: Python 3.13 (bot/API), TypeScript / Next.js on Node 22 (dashboard)
**Primary Dependencies**: stdlib `http.server` (API), `psycopg` 3 (Postgres), `redis-py` (cache + pub/sub), `pytz`, `requests`; Next.js for the dashboard
**Storage**: Postgres = durable source of truth (evaluated opportunities, criterion results, journal); Redis = hot-state cache + command/heartbeat channel (TTL-bounded)
**Testing**: pytest (`src/tradegumi/tests`); docker-compose smoke test for service isolation
**Target Platform**: Linux containers orchestrated by docker-compose (production deployment standard per constitution)
**Project Type**: Multi-service web application (worker + API service + UI)
**Performance Goals**: Preserve current behavior — 60s worker loop cadence; dashboard reflects worker state within the existing Redis TTL window (~10s for loop_state)
**Constraints**: API process MUST never place orders (risk enforcement stays worker-only); worker MUST keep trading when Redis or Postgres is briefly unavailable; external port contract unchanged (API 8199, dashboard 3000)
**Scale/Scope**: Single worker instance (no horizontal worker scaling); single operator dashboard; existing symbol watchlist scope

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
| --- | --- | --- |
| **I. Signal Integrity** | PASS | The four-layer pipeline is untouched. Splitting moves only process/transport boundaries; `signal_engine`, `decision_engine`, and layer ordering stay entirely inside the worker. No layer bypass or partial-signal path is introduced. |
| **II. Execution Layer Abstraction** | PASS (with guard) | The API's new read-only account/positions/trade-history path MUST go through the existing `ExecutionClient` interface (`src/tradegumi/api/base_client.py`), selected by the same config/env as the worker. No broker is referenced directly in API or signal code. Re-verify after design that the API client is read-only. |
| **III. Risk-First** | PASS (with guard) | Position sizing, daily-loss, drawdown, and max-open-position checks remain solely in the worker. The API service MUST NOT expose or reach any order-placement path; its execution client is used only for read endpoints. Risk checks still run/log in `alert_only`. This is the central safety constraint of the split — enforced in research decision R3. |
| **IV. Observable by Default** | PASS (with additions) | New significant events become observable: service start/stop, command received/applied/rejected, command-channel unavailable, and per-service health. Worker continues posting to Discord + JSON/Postgres state. Heartbeat is published so worker liveness is not silent. |
| **V. Configuration-Driven Operations** | PASS | Mode/program/phase changes via `/api/config/*` must still take effect across the new process boundary — now delivered worker-ward over a Redis command channel rather than in-memory mutation. No code change or full restart required to switch mode. All params stay env-var driven. |
| **Security & Credential Hygiene** | PASS | All three services consume secrets via `env_file: .env` (already the pattern); no secrets in compose/Dockerfiles. `.env.example` updated for any new vars (e.g. heartbeat/command channel names) with placeholders. Logs keep redacting tokens/webhooks. |
| **Code Quality & Documentation** | PASS (commitment) | New modules (API-only entrypoint, command channel, heartbeat, read-only client accessor) get full docstrings stating purpose, params, side effects, and the risk/observability constraints they uphold. Tasks include the mandatory code-quality check. |
| **Pull Request Policy** | PENDING | No reviewer identified yet by user or feature context. The generated `tasks.md` MUST include a final Polish-phase task to open the PR with a reviewer, and — since none is identified — that task MUST require the implementer to ask the user to name the reviewer before opening the PR. |

No constitution violations require Complexity Tracking. The three-service split is
the minimum structure that satisfies the spec's isolation requirements (FR-004,
FR-007, FR-008); it is not added complexity beyond what the feature demands.

## Project Structure

### Documentation (this feature)

```text
specs/019-split-runtime-containers/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — cross-process state, commands, read-only client, health
├── data-model.md        # Phase 1 output — Redis keys/channels, message shapes, heartbeat
├── quickstart.md        # Phase 1 output — bring up the 3 services, verify isolation
├── contracts/           # Phase 1 output — command channel + heartbeat contracts
│   ├── command-channel.md
│   └── service-health.md
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
# Container / orchestration (the heart of this feature)
docker-compose.yml            # CHANGED: tradegumi → tradegumi-worker + tradegumi-api + tradegumi-dashboard
Dockerfile                    # CHANGED: split combined image into a python (worker/api) image + node (dashboard) image
                              #          (or one python image with per-service `command:` + a node image)
entrypoint.sh                 # REPLACED: per-service entrypoints (no more dual-process `wait -n`)
  ├── entrypoint.worker.sh    # NEW: runs `python -m tradegumi.main` (loop only)
  ├── entrypoint.api.sh       # NEW: runs the API-only entrypoint
  └── (dashboard uses `npm start` directly)
.env.example                  # CHANGED: document any new channel/heartbeat env vars

# Python worker + API service (same image, different entrypoints)
src/tradegumi/
├── main.py                   # CHANGED: run() no longer starts the API server in-thread; subscribes to
│                             #          the Redis command channel and applies commands each loop;
│                             #          publishes heartbeat + json-safe runtime snapshot to Redis
├── api_server.py             # CHANGED: reads loop_state/watchlist/signals from Redis + Postgres instead of
│                             #          in-process get_runtime_state(); config/rescan POSTs publish commands
│                             #          to Redis instead of mutating in-memory state; uses a read-only client
├── api_main.py               # NEW: standalone entrypoint that starts ONLY the API server (no worker loop)
├── runtime_state.py          # NEW (optional): shared helpers for reading/writing runtime snapshot via Redis
├── commands.py               # NEW: command channel — publish (API side) + consume/apply (worker side)
├── persistence/
│   └── redis.py              # CHANGED (small): add command pub/sub + heartbeat helpers atop existing RedisCache
└── tests/
    ├── test_commands.py          # NEW: command publish→consume→apply round-trip
    ├── test_api_reads_redis.py   # NEW: API serves loop_state/watchlist from Redis, Postgres for journal
    └── test_service_isolation.py # NEW/compose smoke: killing one service leaves the others running

# Dashboard (already API-driven via NEXT_PUBLIC_API_URL — minimal change)
dashboard/                    # CHANGED: own image/service; NEXT_PUBLIC_API_URL points at tradegumi-api;
                              #          drop reliance on the public/data symlink (was worker-local)
```

**Structure Decision**: Reuse one Python image for both `tradegumi-worker` and
`tradegumi-api` (identical dependencies; they differ only by entrypoint/command),
and keep a separate Node image for `tradegumi-dashboard`. This avoids duplicating
the Python build and keeps worker/API code in the existing `src/tradegumi`
package. The combined `entrypoint.sh` with `wait -n` is removed — that shared
fate is exactly the coupling the feature eliminates. Cross-process state and
commands ride on the Redis/Postgres infrastructure from #108 rather than a new
transport.

## Complexity Tracking

> No constitution violations require justification. The three-service
> decomposition is the minimum needed to satisfy FR-004/FR-007/FR-008
> (independent failure, health, and restart), so this table is intentionally
> empty.

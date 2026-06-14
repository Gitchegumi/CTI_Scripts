# Phase 0 Research: Split Runtime into API, Dashboard, and Worker Containers

This document resolves the design unknowns surfaced while reading the current
runtime (`main.py`, `api_server.py`, `persistence/`, `docker-compose.yml`,
`Dockerfile`, `entrypoint.sh`). Each decision is grounded in what the code does
today so the split preserves behavior.

## Current-state findings (the constraints we must work within)

- **API runs inside the worker process.** `main.py:run()` calls
  `start_api_server()` (background thread) and then enters the `while True`
  worker loop. Both share the module-level `_runtime_state` dict in
  `api_server.py` via `set_runtime_state` / `get_runtime_state`.
- **Commands flow through shared memory today.** `POST /api/config/mode`,
  `/api/config/program`, `/api/config/phase`, `/api/config/challenge_type`, and
  `/api/action/rescan` mutate `_runtime_state` (e.g. `force_rescan = True`); the
  worker reads it on its next iteration. There is no cross-process channel yet.
- **Some API reads need the live broker client.** `/api/positions`,
  `/api/trades/history` (source trades), and parts of `/api/trades` pull
  `get_runtime_state().get("client")` — the worker's live `ExecutionClient`. A
  separate API process will not have that object.
- **Redis snapshot already exists, one-way.** `set_runtime_state` already
  publishes a JSON-safe snapshot to Redis key `loop_state` (TTL 10s), explicitly
  dropping the live `client`. But the API still *reads* from in-process state,
  not Redis.
- **Postgres is already the durable source of truth** for evaluated
  opportunities, criterion results, and the journal (#108). Redis is a TTL cache.
- **The dashboard is already API-driven.** Every dashboard route uses
  `NEXT_PUBLIC_API_URL` (default `http://localhost:8199`). The
  `public/data → src/tradegumi/data` symlink in the Dockerfile is legacy and
  worker-local; under the split the dashboard must not depend on it.
- **`entrypoint.sh` couples fate.** `wait -n $BOT_PID $DASHBOARD_PID` means
  either process exiting kills both — the exact cascade the feature removes.

## R1 — How does worker runtime state reach the API service?

**Decision**: The worker publishes its JSON-safe runtime snapshot
(`loop_state`), `watchlist`, and `active_signals` to Redis with TTLs (the
machinery already exists in `RedisCache` and `set_runtime_state`). The API
service **reads these from Redis** instead of in-process `get_runtime_state()`.
Durable analytics (journal, evaluated opportunities, strategy metrics) the API
continues to read **directly from Postgres**, which it can already reach.

**Rationale**: Reuses #108 infrastructure with no new transport. The one-way
snapshot already drops non-serializable live objects, so the contract is clean.
TTLs give the API a natural staleness signal (missing/expired `loop_state` →
worker is not currently publishing).

**Alternatives considered**:
- *API reads worker JSON files over a shared volume* — rejected: reintroduces
  filesystem coupling and a shared writable volume between services; Redis is the
  intended hot-state layer.
- *Worker exposes an internal HTTP endpoint the API scrapes* — rejected: gives
  the worker an inbound port (spec says worker has no public HTTP port) and adds
  a second control plane.

## R2 — How do operator commands reach the worker after the split?

**Decision**: Add a **Redis command channel**. The API publishes command
messages (mode/program/phase/challenge_type change, rescan, and any existing
control POST) to a Redis pub/sub channel **and** records the latest desired
config in a durable Redis key (last-write-wins). The worker subscribes to the
channel for low-latency delivery and, on each loop iteration (and at startup),
reconciles against the durable key so a command issued while the worker was
momentarily down is still applied when it returns.

**Rationale**: Pub/sub alone drops messages sent while no subscriber is
connected, which would violate FR-005/FR-010 ("not silently lost"). Pairing
pub/sub (fast path) with a durable "desired state" key (recovery path) gives
at-least-once application without a full queue system. `RedisCache.publish`
already exists; we add a small consumer + a desired-config key.

**Alternatives considered**:
- *Pure pub/sub* — rejected: messages issued during a worker restart are lost.
- *Redis Streams / a real queue* — rejected as over-engineered for a
  single-worker, low-frequency control plane; revisit only if multi-worker.
- *Postgres-backed command table* — viable and durable, but heavier than a
  desired-config key for what is effectively idempotent config reconciliation;
  Redis keeps control-plane latency low. Postgres stays the analytics SoT.

## R3 — How does the API serve account/positions/trade-history without the worker's live client? (SAFETY-CRITICAL)

**Decision**: The API service constructs its **own broker client through the
existing `ExecutionClient` interface**, selected by the same config/env as the
worker, and uses it **only for read operations** (`get_open_positions`,
`get_trade_history`, account info). Order-placement methods are never called from
the API process, and the API code path exposes no route that places an order.
Position sizing, daily-loss, drawdown, and max-open checks remain exclusively in
the worker.

**Rationale**: `ExecutionClient` is broker-agnostic (Constitution II), so the
API stays free of direct broker references. Read endpoints are inherently
side-effect-free at the broker. Keeping a second *read-only* connection is far
simpler than round-tripping positions through Redis and avoids staleness on the
operator's account view. Risk-First (Constitution III) is upheld because the only
component that can place orders is the worker.

**Guard rails (verified in design + tests)**:
- The API entrypoint must not import or invoke risk/order-placement code paths.
- A test asserts the API service never calls an order-placement method.
- If broker creds are absent in the API service, the affected read endpoints
  degrade to `503 client not available` (the existing behavior), not a crash.

**Alternatives considered**:
- *Worker publishes positions/account snapshots to Redis; API reads them* —
  viable and arguably "purest" (single broker connection, worker-only), but adds
  TTL staleness to the operator's live account view and more worker work. Kept as
  a fallback if running two broker connections proves problematic; the
  `ExecutionClient` read-only approach is the primary.
- *Proxy these endpoints from API to a worker HTTP endpoint* — rejected: gives
  the worker an inbound port (forbidden by spec).

## R4 — Per-service health checks and isolated restarts

**Decision**:
- **tradegumi-api**: docker healthcheck curls `http://localhost:8199/api/status`
  (already exists today as the compose healthcheck target).
- **tradegumi-dashboard**: healthcheck hits the Next.js port 3000 root (or a
  lightweight `/` 200 check).
- **tradegumi-worker**: has no HTTP port, so it publishes a **heartbeat** key to
  Redis (e.g. `heartbeat:worker` with a short TTL refreshed each loop). Its
  docker healthcheck runs a tiny Python check that reads the heartbeat and fails
  if missing/stale. This makes worker liveness observable (Constitution IV) and
  health independent of the other services (FR-007).
- Each service keeps `restart: unless-stopped` so restarts are isolated (FR-008);
  removing the `wait -n` entrypoint is what actually makes a single-service
  crash/restart non-cascading.

**Rationale**: Each health signal reflects only that service's own concern.
Heartbeat-in-Redis is the standard way to health-check a process with no inbound
port and doubles as the API's "is the worker live?" indicator.

**Alternatives considered**:
- *Give the worker a minimal health HTTP port* — rejected: spec says worker has
  no public HTTP port; a heartbeat key is sufficient and avoids a listener.
- *File-based liveness on a shared volume* — rejected: reintroduces cross-service
  filesystem coupling.

## R5 — Container/image layout and startup ordering

**Decision**: One Python image serves both `tradegumi-worker` and
`tradegumi-api` (identical deps; differ only by entrypoint/`command`). A separate
Node image serves `tradegumi-dashboard`. Replace the combined `entrypoint.sh`
with per-service entrypoints; the dashboard uses `npm start`. Compose
`depends_on` with health conditions: worker and api depend on Postgres + Redis
healthy; dashboard depends on api healthy. Services tolerate dependencies coming
up late (worker keeps trying Redis/Postgres; dashboard shows a degraded state if
the API is briefly unreachable).

**Rationale**: Avoids duplicating the Python build, keeps the worker/API in one
package, and matches docker-compose as the deployment standard (constitution).
`depends_on: condition: service_healthy` already used in the current compose file
gives ordered startup without app-level retries being mandatory — but the worker
must still survive a mid-run dependency blip (FR-010/FR-011).

**Alternatives considered**:
- *Three fully separate images* — rejected: needless duplication of the Python
  toolchain for worker vs api.
- *Keep one image, three `command:` overrides including the dashboard* —
  rejected for the dashboard: Node runtime differs from the Python base; a
  dedicated Node image is cleaner.

## R6 — Degradation when Redis or Postgres is unavailable

**Decision**:
- **Redis down**: the worker keeps trading on its last-applied config (the
  desired-config key is unreadable, so it holds current settings); `RedisCache`
  methods already no-op/log on failure rather than throw. The API surfaces that
  commands cannot currently be delivered (publish returns false → API responds
  with a "command not delivered / will reconcile" status, never a silent 200).
- **Postgres down**: the worker must not crash the trading cycle solely because a
  metric/journal write failed (FR-011) — writes are guarded and logged; the loop
  continues. The API's analytics endpoints return an error/empty state rather
  than crashing.

**Rationale**: Directly satisfies FR-010/FR-011 and the spec edge cases. Aligns
with the existing defensive style in `RedisCache` (warn-and-continue).

**Alternatives considered**:
- *Halt the worker when Postgres is down to guarantee no lost metrics* —
  rejected: stopping trading because analytics storage blipped is the opposite of
  the feature's intent (keep trading alive). Metric durability is best-effort
  relative to trading continuity.

## Summary of resolved unknowns

| # | Unknown | Resolution |
| --- | --- | --- |
| R1 | Worker→API state transport | Worker publishes snapshot to Redis (TTL); API reads Redis for hot state + Postgres for durable analytics |
| R2 | API→worker commands | Redis pub/sub (fast) + durable desired-config key (recovery); worker reconciles on loop + startup |
| R3 | API account/positions without worker client | API gets its own **read-only** `ExecutionClient`; never places orders (Risk-First upheld) |
| R4 | Worker health with no HTTP port | Redis heartbeat key + tiny healthcheck script; api/dashboard use HTTP healthchecks |
| R5 | Image/compose layout | One Python image (worker+api by entrypoint) + Node image (dashboard); health-gated `depends_on` |
| R6 | Redis/Postgres outage behavior | Worker keeps trading; commands never silently dropped; metric writes best-effort |

All NEEDS CLARIFICATION items from Technical Context are resolved. Proceed to
Phase 1.

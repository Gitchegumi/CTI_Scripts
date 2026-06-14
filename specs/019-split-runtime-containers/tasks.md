---
description: "Task list for Split Runtime into API, Dashboard, and Worker Containers"
---

# Tasks: Split Runtime into API, Dashboard, and Worker Containers

**Input**: Design documents from `/specs/019-split-runtime-containers/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included where the plan explicitly enumerated them
(`test_commands.py`, `test_api_reads_redis.py`, `test_service_isolation.py`) —
these prove the cross-process behavior that cannot be eyeballed.

**Organization**: Tasks are grouped by user story so each story is an
independently testable increment of the split.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1/US2/US3/US4 (maps to spec.md user stories)
- Exact file paths included in each task

## Path Conventions

Python worker + API live in `src/tradegumi/`; dashboard in `dashboard/`;
container/orchestration files at repo root (`docker-compose.yml`, `Dockerfile`,
`entrypoint*.sh`, `.env.example`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare configuration and dependency surface for the split.

- [X] T001 [P] Document new cross-process env vars (worker heartbeat/command channel settings as needed; confirm `NEXT_PUBLIC_API_URL`, `TRADEGUMI_REDIS_URL`, `TRADEGUMI_DATABASE_URL`) with placeholders and inline docs in `.env.example`
- [X] T002 [P] Verify `redis` (redis-py) and `psycopg` are declared in `src/pyproject.toml` and `requirements.txt`; add if missing
- [X] T003 [P] Confirm Python docstring / code-quality check covers changed files (pre-commit or CI) per Constitution Code Quality gate

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared mechanics the split stories all build on — the Redis data
plane helpers, the image restructure, and per-service entrypoints.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Extend `src/tradegumi/persistence/redis.py` with cross-process helpers atop `RedisCache`: `set_heartbeat`/`get_heartbeat` (key `heartbeat:worker`, TTL ≥2–3× loop interval ≈150s), `publish_command`/`subscribe_commands` (channel `commands`), and `set_desired_config`/`get_desired_config` (key `desired_config`), each with docstrings stating TTLs and failure (no-op) behavior
- [X] T005 Restructure `Dockerfile` into a shared Python image used by both worker and API (drop the combined final stage that installs Node into the Python image) and prepare a separate Node-based dashboard image build
- [X] T006 [P] Create per-service entrypoints: `entrypoint.worker.sh` (runs `python -m tradegumi.main`) and `entrypoint.api.sh` (runs `python -m tradegumi.api_main`); delete the dual-process `wait -n` logic from `entrypoint.sh`. NOTE: `entrypoint.api.sh` is inert until `api_main.py` exists (T013, US2) and the api service is added (T017, US2)

**Checkpoint**: Redis helpers, image split, and entrypoints exist — user stories can begin.

---

## Phase 3: User Story 1 - Trading continues when the dashboard fails (Priority: P1) 🎯 MVP

**Goal**: Move the dashboard into its own container so a dashboard crash/restart
can no longer take down the trading engine.

**Independent Test**: Kill the dashboard container mid-loop; the worker keeps
polling/scanning/alerting and the API still responds (SC-001).

**Scope note**: At the end of US1 the worker and API remain co-located in one
container (the API still runs in-thread until US2); only the dashboard is
separated here. That is sufficient to deliver SC-001.

### Implementation for User Story 1

- [X] T007 [US1] Create a standalone Next.js dashboard image build in `Dockerfile` (or `dashboard/Dockerfile`) producing a Node-only runtime that does not depend on the worker's `public/data` symlink
- [X] T008 [US1] Add `tradegumi-dashboard` service to `docker-compose.yml` (port 3000, `env_file: .env`, `NEXT_PUBLIC_API_URL=http://tradegumi-api:8199`, `restart: unless-stopped`)
- [X] T009 [US1] Remove dashboard startup from the combined container entrypoint so the remaining Python service no longer launches `npm start`; confirm the dashboard reads exclusively via the API
- [X] T010 [US1] Verify SC-001: `docker compose kill tradegumi-dashboard`, confirm the worker loop continues and `GET /api/status` still returns 200 (record in `specs/019-split-runtime-containers/quickstart.md` results) — ✅ VERIFIED 2026-06-14 on live stack: worker kept trading, no errors in docker logs, other containers unaffected

**Checkpoint**: Dashboard failure no longer affects trading — MVP delivered.

---

## Phase 4: User Story 2 - Dashboard and API survive a worker failure (Priority: P2)

**Goal**: Extract the API into its own container that reads hot state from Redis
and durable analytics from Postgres (with its own read-only execution client),
so the analytics path stays alive when the worker dies.

**Independent Test**: Kill the worker container; the API still returns 200 and
the dashboard renders persisted analytics (SC-002).

### Tests for User Story 2

- [ ] T011 [P] [US2] Write `src/tradegumi/tests/test_api_reads_redis.py` asserting the API serves `loop_state`/`watchlist`/`active_signals` from Redis and journal/metrics from Postgres with no in-process worker (expected to fail until T013–T015)

### Implementation for User Story 2

- [ ] T012 [P] [US2] Capture the pre-split API surface: enumerate every endpoint the combined `src/tradegumi/api_server.py` exposes today into `specs/019-split-runtime-containers/quickstart.md` (parity baseline for FR-012/SC-006)
- [ ] T013 [P] [US2] Create `src/tradegumi/api_main.py` — standalone entrypoint that starts only the API server (no worker loop), wiring Redis and Postgres access
- [ ] T014 [US2] Refactor `src/tradegumi/api_server.py` to read runtime state from Redis (degraded state on missing/expired `loop_state`) and analytics from Postgres, replacing in-process `get_runtime_state()` reads
- [ ] T015 [US2] Update `src/tradegumi/main.py` so the worker publishes the JSON-safe runtime snapshot (`loop_state`/`watchlist`/`active_signals`) to Redis each loop and no longer calls `start_api_server()`
- [ ] T016 [US2] Implement read-only `ExecutionClient` access in `src/tradegumi/api_server.py` for `/api/positions`, `/api/trades/history`, and account endpoints via `src/tradegumi/api/base_client.py`; ensure no order-placement path is reachable from the API and return `503` when the client is unavailable
- [ ] T017 [US2] Update `docker-compose.yml`: rename the remaining service to `tradegumi-worker` (no published port) and add `tradegumi-api` (port 8199, `env_file: .env`, `depends_on` postgres+redis healthy, `restart: unless-stopped`); wire worker→`entrypoint.worker.sh`, api→`entrypoint.api.sh`
- [ ] T018 [US2] Guard worker durable-write paths in `src/tradegumi/main.py` (and the strategy-metrics/journal write helpers it calls) so a Postgres outage logs-and-continues without crashing the trading cycle (FR-011)
- [ ] T019 [US2] Verify SC-002 + FR-011: `docker compose kill tradegumi-worker` → `GET /api/status` returns 200 and the dashboard renders Postgres-backed analytics; separately, stop Postgres mid-loop → worker keeps trading

**Checkpoint**: API + dashboard survive a worker outage; all three run as separate services; worker survives a Postgres blip.

---

## Phase 5: User Story 3 - Independent health monitoring and isolated restarts (Priority: P2)

**Goal**: Give each service a health signal reflecting only its own concern, and
confirm restarts don't cascade.

**Independent Test**: Each service's health reflects only itself; restarting one
leaves the other two running (SC-003, SC-004).

### Tests for User Story 3

- [ ] T020 [P] [US3] Write `src/tradegumi/tests/test_service_isolation.py` (or a compose smoke script) asserting that restarting one service does not restart the others and that a single-service failure turns only that service's health red

### Implementation for User Story 3

- [ ] T021 [P] [US3] Create `src/tradegumi/healthcheck.py` with a `worker` mode that reads `tradegumi:heartbeat:worker` and exits non-zero if the key is missing or its `ts` is older than the freshness threshold (~150s)
- [ ] T022 [US3] Update `src/tradegumi/main.py` to publish the worker heartbeat (`ts`, `loop_count`, `mode`) to Redis each loop with a TTL ≥2–3× the loop interval (~150s, never shorter than the loop interval)
- [ ] T023 [US3] Add per-service healthchecks in `docker-compose.yml`: worker → `python -m tradegumi.healthcheck worker`, api → `curl -f http://localhost:8199/api/status`, dashboard → HTTP check on port 3000
- [ ] T024 [US3] Add a `worker_live` flag to `GET /api/status` in `src/tradegumi/api_server.py` derived from the worker heartbeat, so the dashboard can show worker connectivity without coupling API health to the worker
- [ ] T025 [US3] Emit observability for health events (Constitution IV): post to Discord and write to state when the worker starts, when its heartbeat goes stale, and when it recovers — in `src/tradegumi/main.py` (start) and the heartbeat-staleness path
- [ ] T026 [US3] Verify SC-003/SC-004: restart each service in turn and confirm the other two stay up; induce a single-service failure and confirm only its health goes red

**Checkpoint**: Per-service health and isolated restarts confirmed and observable.

---

## Phase 6: User Story 4 - Operator-issued commands reach the worker (Priority: P3)

**Goal**: Replace the in-memory command path with the Redis command channel so
config changes and rescans reach the now-separate worker, and are not lost if the
worker is briefly down.

**Independent Test**: Issue a command via the API → worker applies it; a command
issued while the worker is down is applied on restart (SC-005, FR-010).

### Tests for User Story 4

- [ ] T027 [P] [US4] Write `src/tradegumi/tests/test_commands.py` covering publish→consume→apply round-trip and a command issued while the worker is down being applied on startup reconciliation (expected to fail until T028–T030)

### Implementation for User Story 4

- [ ] T028 [P] [US4] Create `src/tradegumi/commands.py`: command schema + validation and publish (API) / consume + apply (worker) helpers for `set_mode`/`set_program`/`set_phase`/`set_challenge_type`/`rescan` per `contracts/command-channel.md`
- [ ] T029 [US4] Update API control handlers in `src/tradegumi/api_server.py` (`/api/config/*`, `/api/action/rescan`) to validate, then publish a command and update `desired_config`; return a non-2xx status when delivery fails instead of a silent success
- [ ] T030 [US4] Update `src/tradegumi/main.py` worker to subscribe to the `commands` channel, reconcile `desired_config` at startup and each loop, apply changes without a restart, and reflect the new mode in the heartbeat
- [ ] T031 [US4] Emit observability for command events (Constitution IV): post to Discord and write to state on command accepted (API), command applied (worker), command rejected (validation), and command-channel-unavailable, in `src/tradegumi/api_server.py` and `src/tradegumi/main.py`
- [ ] T032 [US4] Verify SC-005/FR-010: stop the worker, `POST /api/config/mode mode=demo`, start the worker, confirm it comes up in `demo` via reconciliation (per `quickstart.md`)

**Checkpoint**: Operator control fully preserved across the process boundary and observable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, quality, and the required PR task.

- [ ] T033 [P] Update `README.md` and `docs/` to describe the three-service architecture, new env vars, and local-dev commands from `quickstart.md`
- [ ] T034 Review all changed code for intention-revealing names, simple control flow, and no unexplained magic values (Constitution Code Quality gate)
- [ ] T035 Add/verify docstrings for new modules (`api_main.py`, `commands.py`, `healthcheck.py`, new `redis.py` helpers) and all modified functions
- [ ] T036 Run full `quickstart.md` validation end-to-end (SC-001…SC-005) AND confirm FR-012/SC-006 parity: every endpoint in the pre-split surface captured in T012 still responds correctly post-split
- [ ] T037 Security check: confirm `.env`-only secrets, no values in `docker-compose.yml`/Dockerfiles, and token/webhook redaction across all three services' logs
- [ ] T038 Submit the PR with the user/context-identified reviewer — **no reviewer has been identified yet, so the implementer MUST ask the user to name the reviewer before opening the PR** (Constitution Pull Request Policy)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **US1 (Phase 3)**: Depends on Foundational. Independent of US2–US4.
- **US2 (Phase 4)**: Depends on Foundational. The core API/worker split; US3 and US4 build on it.
- **US3 (Phase 5)**: Depends on Foundational; meaningfully testable after US2 (separate worker to heartbeat).
- **US4 (Phase 6)**: Depends on Foundational and US2 (the command channel is only needed once the API is a separate process).
- **Polish (Phase 7)**: Depends on all targeted stories being complete.

### User Story Dependencies

- **US1 (P1)**: Standalone — dashboard isolation only.
- **US2 (P2)**: Standalone core split; does not depend on US1.
- **US3 (P2)**: Builds on US2 (worker as its own service to health-check).
- **US4 (P3)**: Builds on US2 (separate API process needs the Redis command channel).

### Within Each User Story

- Tests (where present) written first and expected to fail before implementation.
- Snapshot/publish (worker) before read refactor (API) where both touch the same key.
- Service definition + entrypoint wiring after the code path it runs exists.
- Observability tasks (T025, T031) after the events they instrument exist.

### Parallel Opportunities

- All Setup tasks (T001–T003) run in parallel.
- T006 is parallel with T004/T005 within Foundational (different files).
- US1 and US2 can be developed in parallel after Foundational (different files), then US3/US4 after US2.
- Test-writing tasks (T011, T020, T027) are [P] within their stories.
- T012 (parity capture) and T013 (api_main.py) are [P] — different files.

---

## Parallel Example: User Story 2

```bash
# Write the failing test first:
Task: "Write src/tradegumi/tests/test_api_reads_redis.py"

# Then parallelizable work (different files):
Task: "Capture pre-split API surface into quickstart.md"      # T012
Task: "Create src/tradegumi/api_main.py standalone API entrypoint"  # T013
# (T014/T015 touch api_server.py and main.py respectively — can also parallelize)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 US1: split the dashboard out.
3. **STOP and VALIDATE**: kill the dashboard, confirm trading continues (SC-001).
4. Deploy/demo — the most damaging failure mode is already fixed.

### Incremental Delivery

1. Setup + Foundational → groundwork ready.
2. US1 → trading survives dashboard failure (MVP).
3. US2 → API/dashboard survive worker failure + worker survives Postgres blip (the full split).
4. US3 → per-service health + isolated restarts (observable).
5. US4 → operator commands preserved across the boundary (observable).

### Notes

- [P] = different files, no dependencies.
- Worker must keep trading when Redis/Postgres blips (FR-010/FR-011) — implemented in T018/T030, verified in T019/T032.
- The API must never place orders (Risk-First) — enforced in T016, reviewed in T034.
- New significant events must be observable (Constitution IV) — T025 (health) and T031 (commands).
- T038 is non-optional and must remain in Polish per the constitution.

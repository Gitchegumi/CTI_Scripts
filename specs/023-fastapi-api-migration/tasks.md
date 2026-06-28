---

description: "Task list for FastAPI migration of the TradeGumi API service"
---

# Tasks: Refactor Python API Service to FastAPI

**Input**: Design documents from `specs/023-fastapi-api-migration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-endpoints.md, quickstart.md

**Tests**: INCLUDED — endpoint parity, auth, and command-channel failure coverage are explicitly required (spec FR-017; issue #116 acceptance criteria). TestClient suites use FastAPI dependency overrides for hermetic, fast runs.

**Organization**: Tasks are grouped by user story. Because this is a *parity refactor* (not greenfield), the foundational app/factory/deps layer is shared by all stories; a few router files (`journal.py`, `trades.py`) are touched by more than one story — those cross-story touches are called out and are NOT marked `[P]`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 / US4 (maps to spec.md user stories)
- All paths are relative to repo root `E:\GitHub\CTI_Scripts`

## Path Conventions

- Python service source: `src/tradegumi/`
- New app factory: `src/tradegumi/api_app.py`; shared deps: `src/tradegumi/api/deps.py`; routers: `src/tradegumi/api/routes/`
- Tests: `src/tradegumi/tests/`
- Parity baseline: current `src/tradegumi/api_server.py` + `contracts/api-endpoints.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add framework dependencies and create the package skeleton.

- [x] T001 Add `fastapi` and `uvicorn[standard]` to `[tool.poetry.dependencies]` and `httpx` to `[tool.poetry.group.dev.dependencies]` in `src/pyproject.toml`, then run `poetry lock` (in `src/`) to refresh `src/poetry.lock`.
- [x] T002 Run `poetry install` in `src/` and confirm `fastapi`, `uvicorn`, and `httpx` resolve on Python 3.13 (note any `uvloop`/`httptools` build needs on `python:3.13-slim`).
- [x] T003 [P] Create the router package skeleton: `src/tradegumi/api/routes/__init__.py` and empty module files `status.py`, `data.py`, `config_actions.py`, `journal.py`, `trades.py`, `strategy_metrics.py` under `src/tradegumi/api/routes/`, each with a module docstring stating its concern.
- [x] T004 [P] Update root `requirements.txt` only if it is still consumed by any tooling (verify first; the image build uses Poetry) — otherwise leave a note in `research.md` that it is legacy. File: `requirements.txt`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The FastAPI app factory, shared dependencies, parity-preserving error envelopes, path aliasing, and the Uvicorn entrypoint. Every user story depends on this.

**⚠️ CRITICAL**: No router/story work can begin until this phase is complete.

- [x] T005 Create `src/tradegumi/api/deps.py` and migrate the cross-process helpers out of `api_server.py`: `get_runtime_state` / `set_runtime_state`, `get_api_execution_client` (read-only; MUST NOT place orders), `worker_live`, and the `_json_safe_state` helper. Preserve behavior and docstrings verbatim in intent.
- [x] T006 In `src/tradegumi/api/deps.py` add FastAPI dependency providers: `get_db_dep` (returns `tradegumi.persistence.get_db()`), `get_cache_dep`, `get_execution_client_dep`, and `require_auth` (reads `X-API-Key`, compares to `config.JOURNAL_TOKEN`, no-op when unset, raises `HTTPException(401)` mapped to body `{"error":"Unauthorized"}`). Docstring each.
- [x] T007 Create `src/tradegumi/api_app.py` with `create_app()`: instantiate `FastAPI(title/version/description)`, add `CORSMiddleware` (origins `*`; methods GET,POST,PUT,DELETE,OPTIONS; headers Content-Type,X-API-Key) reproducing `_send_cors()`/`do_OPTIONS`, and leave `/docs`,`/redoc`,`/openapi.json` enabled (FR-020).
- [x] T008 In `src/tradegumi/api_app.py` register custom exception/handlers so error bodies match the legacy shape: 404 → `{"error":"not found"}`, 405 → `{"error":"Method not allowed"}`, 401 → `{"error":"Unauthorized"}`, and a `RequestValidationError`/HTTP 422 → remap to `400 {"error": <message>}` safety net (Decision 4). Never emit raw `{"detail": ...}` for `/api/*`.
- [x] T009 In `src/tradegumi/api_app.py` add path-alias handling so `/api/manual-trades` → `/api/trades/manual` and `/api/manual-trades/<rest>` → `/api/trades/manual/<rest>` resolve to the same handlers (middleware or alias routes), reproducing `_route_path()` (FR-014).
- [x] T010 Register all routers (`status`, `data`, `config_actions`, `journal`, `trades`, `strategy_metrics`) in `create_app()` via `app.include_router(...)`. Routers may be empty stubs at this point.
- [x] T011 Modify `src/tradegumi/api_main.py` to boot Uvicorn against `create_app()` (e.g. `uvicorn.Server`/`uvicorn.run`) on `API_PORT`, keeping: the explicit Postgres reachability check BEFORE serving (fail-fast, FR-008), `config.validate_config()`, the logging format, and clean SIGTERM/SIGINT shutdown. Remove the `start_api_server` thread usage.
- [x] T012 [P] Add shared test fixtures in `src/tradegumi/tests/conftest.py` (or a new `_api.py` helper): a `TestClient` built from `create_app()` plus dependency-override helpers to inject fake Postgres backend, fake Redis cache/state, fake execution client, and a configurable `JOURNAL_TOKEN`.

**Checkpoint**: App boots, returns 404 `{"error":"not found"}` for unknown paths, serves `/docs`, and fails fast without Postgres. Routers are empty — story work can begin.

---

## Phase 3: User Story 1 - Dashboard & operator reads keep working (Priority: P1) 🎯 MVP

**Goal**: Every existing read/analytics endpoint returns the same status codes and parsed response structure as `api_server.py`, so the dashboard renders unchanged.

**Independent Test**: Run the dashboard (or the parity TestClient suite) against the rebuilt app with representative data; every read screen/endpoint matches the baseline in `contracts/api-endpoints.md`.

### Tests for User Story 1 ⚠️ (write first, expect FAIL)

- [x] T013 [P] [US1] Parity tests for status + data reads in `src/tradegumi/tests/test_api_status_data.py`: `/api/status` (incl. `worker_live`), `/api/data/loop_state|watchlist|signals`, `/api/data/trade_correlations`, `/api/prices` — assert status + parsed structure and default-empty shapes.
- [x] T014 [P] [US1] Parity tests for strategy-metrics in `src/tradegumi/tests/test_api_strategy_metrics.py`: `/api/strategies` and `/api/strategy-metrics/{summary,opportunities,lifecycle-events,compare,export}` success + 400 missing-param + 500 paths.
- [x] T015 [P] [US1] Parity tests for read-only trades/journal-read in `src/tradegumi/tests/test_api_reads.py`: `/api/positions`, `/api/trades/history` (auth), `/api/trades/manual` GET (auth), `/api/trades/manual/export` (auth), `/api/trades/manual/stats` (auth), `/api/data/journal`, `/api/journal/export` (auth) — incl. 503 client-not-available.

### Implementation for User Story 1

- [x] T016 [P] [US1] Implement `src/tradegumi/api/routes/status.py`: `GET /api/status` returning merged config + runtime snapshot incl. `worker_live`, degrading hot fields when the snapshot is stale/absent.
- [x] T017 [P] [US1] Implement `src/tradegumi/api/routes/data.py`: `GET /api/data/loop_state`, `/api/data/watchlist`, `/api/data/signals`, `/api/data/trade_correlations`, `/api/prices` — reading the read-only data volume / runtime snapshot with the existing default-empty payloads.
- [x] T018 [P] [US1] Implement `src/tradegumi/api/routes/strategy_metrics.py`: `/api/strategies` and the five `/api/strategy-metrics/*` endpoints, reproducing required-param 400s, value-error 400s, and 500s exactly.
- [x] T019 [US1] Implement the READ endpoints in `src/tradegumi/api/routes/trades.py`: `GET /api/positions`, `GET /api/trades/history` (auth via `require_auth`), `GET /api/trades/manual`, `/export`, `/stats` (auth) — using the read-only execution client and 503 when absent. (File shared with US2 — reads only here.)
- [x] T020 [US1] Implement the READ endpoints in `src/tradegumi/api/routes/journal.py`: `GET /api/data/journal` (open) and `GET /api/journal/export` (auth, 404 empty range, 400 bad). (File shared with US2 — reads only here.)
- [x] T021 [US1] Run `src/tradegumi/tests/test_api_status_data.py`, `test_api_strategy_metrics.py`, `test_api_reads.py` and make all US1 parity tests pass.

**Checkpoint**: The dashboard's read surface is fully served by FastAPI and matches the baseline. MVP is demoable.

---

## Phase 4: User Story 2 - Operator control actions reach the worker safely (Priority: P1)

**Goal**: Config changes, journal mutations, manual-trade writes, actions, and purge are validated, auth-gated where required, delivered over the Redis command channel where applicable, and NEVER report false success. The API places no orders.

**Independent Test**: Issue each control action against the rebuilt app; valid commands publish + ack with `command_id`, invalid → 400, channel-down → 503 "not delivered", protected writes → 401 without the key; assert no order-placement path exists.

### Tests for User Story 2 ⚠️ (write first, expect FAIL)

- [x] T022 [P] [US2] Command-channel tests in `src/tradegumi/tests/test_api_commands.py`: `/api/config/{mode,challenge_type,program,phase}` and `/api/action/rescan` → accepted `{status,command_id}`; invalid → 400; `commands.publish` falsey → 503 `{"error":"command not delivered — command channel unavailable","type":...}`; `/api/action/restart` → `{status:"restart_requested"}`.
- [x] T023 [P] [US2] Auth-behavior tests in `src/tradegumi/tests/test_api_auth.py`: with `JOURNAL_TOKEN` set, every protected endpoint (per `contracts/api-endpoints.md`) returns 401 `{"error":"Unauthorized"}` without the header and succeeds with it; open endpoints ignore the header; with token unset, auth is a no-op.
- [x] T024 [P] [US2] Write/mutation parity tests in `src/tradegumi/tests/test_api_writes.py`: journal `grade/invalidate/notes/reset` (400 missing fields, 404 not found, `{ok:true}`), `DELETE /api/journal` (auth), manual-trade `POST`/`PUT/:id`/`DELETE/:id` (auth; 403/404/400/500 mapping), `/api/purge` (auth; 400 targets-not-list).
- [x] T025 [P] [US2] No-order-placement guard test in `src/tradegumi/tests/test_api_no_orders.py`: assert no route places a broker order and the execution client is only used for read methods (Constitution III, FR-004).

### Implementation for User Story 2

- [x] T026 [US2] Implement `src/tradegumi/api/routes/config_actions.py`: `/api/config/*` and `/api/action/rescan` via a shared `publish_command` helper (build → 400 on `CommandError`; publish → accepted, else 503; log each outcome), plus `/api/action/restart` and `POST /api/purge` (auth, targets validation).
- [x] T027 [US2] Add the MUTATION endpoints to `src/tradegumi/api/routes/journal.py`: `POST /api/journal/{grade,invalidate,notes,reset}` (open) and `DELETE /api/journal` (auth) with the existing 400/404 messages. (Depends on T020 — same file.)
- [x] T028 [US2] Add the MUTATION endpoints to `src/tradegumi/api/routes/trades.py`: `POST /api/trades/manual` (auth), `PUT /api/trades/manual/:id` (auth), `DELETE /api/trades/manual/:id` (auth), and the `405 "Method not allowed — use PUT or DELETE"` fallback for other methods on `/api/trades/manual/...`. (Depends on T019 — same file.)
- [x] T029 [US2] Run `test_api_commands.py`, `test_api_auth.py`, `test_api_writes.py`, `test_api_no_orders.py` and make all US2 tests pass.

**Checkpoint**: Full read + write parity. Control actions are safe; no false successes; no order placement.

---

## Phase 5: User Story 3 - Graceful degradation & fail-fast (Priority: P2)

**Goal**: Postgres-up + Redis/broker-down keeps analytics/journal/metrics serving; Postgres-down at startup refuses to start; broker-down → 503 on broker endpoints only.

**Independent Test**: Start with Postgres healthy but Redis+broker down → analytics/journal/metrics serve, `/api/status` reports `worker_live:false`; start with Postgres unreachable → service exits before serving.

### Tests for User Story 3 ⚠️ (write first, expect FAIL)

- [x] T030 [P] [US3] Resilience tests in `src/tradegumi/tests/test_api_resilience.py`: Redis cache raising/empty → analytics/journal/strategy-metrics still 200 and `worker_live=False`; execution client `None` → `/api/positions`,`/api/trades/history` return 503; assert no unhandled 500 cascade.
- [x] T031 [P] [US3] Startup fail-fast test in `src/tradegumi/tests/test_api_startup.py`: patch `get_db()` to raise and assert `api_main.main()` raises/exits before Uvicorn serves.

### Implementation for User Story 3

- [x] T032 [US3] Verify/harden degradation in `src/tradegumi/api/deps.py` so cache/state and `worker_live` lookups swallow errors (return empty/`{}`/`False`) and the execution-client dep yields `None` rather than raising, ensuring broker/Redis outages never fault unrelated endpoints (FR-009/FR-010).
- [x] T033 [US3] Confirm `src/tradegumi/api_main.py` fail-fast ordering (Postgres check before `uvicorn` serve) and that Redis/broker are NOT probed at startup; adjust if T011 left any gap.
- [x] T034 [US3] Run `test_api_resilience.py` and `test_api_startup.py` and make all US3 tests pass.

**Checkpoint**: Partial-outage and fail-fast behavior matches the previous service.

---

## Phase 6: User Story 4 - Developer route ownership (Priority: P3)

**Goal**: Routes are grouped by concern, shared concerns come from reusable dependencies, the legacy monolith is gone, and docs/schema are discoverable.

**Independent Test**: Review the tree — adding an endpoint touches only its concern's router + existing deps; `/docs` lists all endpoints; `api_server.py` is removed and nothing imports it.

- [x] T035 [US4] Update `src/tradegumi/tests/test_api_reads_redis.py` to exercise the FastAPI app/`TestClient` instead of the stdlib handler; keep its Redis-read assertions.
- [x] T036 [US4] Remove `src/tradegumi/api_server.py` after confirming no remaining imports of it across `src/` (grep `api_server`, `start_api_server`, `TradeGumiAPIHandler`); repoint any worker-side imports of the migrated helpers to `tradegumi.api.deps`.
- [x] T037 [P] [US4] Verify `/docs`, `/redoc`, and `/openapi.json` are reachable and the OpenAPI schema lists every `/api/*` endpoint; confirm no `/api/*` behavior changed (FR-020).
- [x] T038 [P] [US4] Update `dashboard/` only if it consumed any now-changed behavior — verify the dashboard proxy still targets the same paths (expected: no change). Note result in quickstart.

**Checkpoint**: Clean per-concern structure; monolith removed; docs live.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Packaging, docs, quality gates, validation, and the PR.

- [x] T039 [P] Confirm the `Dockerfile` `python` target installs `fastapi`/`uvicorn` via Poetry (no structural change expected); verify `EXPOSE 8199`, `entrypoint.api.sh` (`python -m tradegumi.api_main`), and the compose healthcheck `GET /api/status` still hold. Files: `Dockerfile`, `entrypoint.api.sh`, `docker-compose.yml`.
- [x] T040 [P] Update docs for any changed local-dev/startup commands per `quickstart.md`: `src/README.md` and `docs/` (note the new `/docs` endpoint; entrypoint unchanged) (FR-018).
- [x] T041 Review all changed/new code for intention-revealing names, simple control flow, and no unexplained magic values (Constitution: Code Quality).
- [x] T042 Add/verify Python module, class, function, method, and non-trivial-helper docstrings across `api_app.py`, `api/deps.py`, `api/routes/*.py`, and modified `api_main.py` (purpose, params/returns, raised exceptions, the order-placement prohibition where relevant).
- [x] T043 Run the full suite from `src/`: `poetry run pytest -q`; ensure parity/auth/command-channel/resilience/startup tests all pass (SC-002, SC-007).
- [x] T044 Execute `quickstart.md` validation: boot locally, smoke-test endpoints + `/docs`, and run the three manual degradation checks (Postgres fail-fast, Redis-down degrade, broker-down 503).
- [x] T045 Commit the change set **as DockeGumi**: first run `gh auth status` to confirm the active GitHub account is DockeGumi and `git config user.*` resolves to DockeGumi; if it does NOT, STOP and ask the user to switch accounts before committing/pushing. Use conventional commits referencing issue #116.
- [x] T046 Push the `023-fastapi-api-migration` branch as DockeGumi and open a PR (base `master`) that **requests Gitchegumi as reviewer**. If pushing as DockeGumi is not possible, STOP and ask the user how to proceed before opening the PR. (Constitution: Pull Request Policy — reviewer identified = Gitchegumi.)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **US1 (Phase 3)**: Depends on Foundational. MVP.
- **US2 (Phase 4)**: Depends on Foundational. Shares `journal.py`/`trades.py` files with US1 → T027 depends on T020, T028 depends on T019. Otherwise independent.
- **US3 (Phase 5)**: Depends on Foundational; verifies behavior best after US1/US2 routes exist, but the resilience hardening (T032/T033) lives in shared foundational files.
- **US4 (Phase 6)**: Depends on US1+US2 routers being complete (T036 removes the monolith only after all routes are migrated).
- **Polish (Phase 7)**: Depends on all desired stories complete. T045/T046 are last and non-optional.

### Within Each User Story

- Tests written first and FAIL before implementation.
- Shared-file ordering: US1 read endpoints in `journal.py`/`trades.py` (T019/T020) before US2 mutations in the same files (T027/T028).

### Parallel Opportunities

- Setup: T003, T004 in parallel.
- Foundational: T012 parallel with handler/factory tasks once T005–T007 exist (note T008–T011 edit `api_app.py`/`api_main.py` and are sequential among themselves).
- US1: T013/T014/T015 (tests) in parallel; T016/T017/T018 (separate router files) in parallel; T019/T020 sequential-safe (separate files, can also be parallel) but precede US2's same-file tasks.
- US2: T022/T023/T024/T025 (tests) in parallel; T026 parallel with T027/T028 only if files differ (T026 is `config_actions.py`; T027/T028 touch journal/trades).
- US3: T030/T031 in parallel.
- Polish: T039/T040 in parallel; T041–T046 sequential.

---

## Parallel Example: User Story 1

```bash
# Tests for US1 together:
Task: "Parity tests for status + data reads in src/tradegumi/tests/test_api_status_data.py"
Task: "Parity tests for strategy-metrics in src/tradegumi/tests/test_api_strategy_metrics.py"
Task: "Parity tests for read-only trades/journal in src/tradegumi/tests/test_api_reads.py"

# Separate router files for US1 together:
Task: "Implement src/tradegumi/api/routes/status.py"
Task: "Implement src/tradegumi/api/routes/data.py"
Task: "Implement src/tradegumi/api/routes/strategy_metrics.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 US1.
2. **STOP and VALIDATE**: dashboard read surface matches baseline.
3. Demo the read-only dashboard on FastAPI.

### Incremental Delivery

1. Setup + Foundational → app boots, fails fast, serves `/docs`.
2. + US1 → read/analytics parity (MVP).
3. + US2 → control actions + auth + no-order safety.
4. + US3 → resilience/fail-fast verified.
5. + US4 → monolith removed, structure clean, docs live.
6. Polish → packaging, docs, full pytest, quickstart validation, PR.

### Commit & PR account workflow (user-specified)

- All commits/pushes for this feature are made **as DockeGumi**; run `gh auth status` (and check `git config user.name/email`) before committing to confirm the active account (T045).
- The PR **requests Gitchegumi as reviewer** (T046), provided pushing as DockeGumi succeeds; if not, stop and ask the user.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- The hardest parity risk is FastAPI defaults: ensure 401/404/405/validation bodies use `{"error": ...}` (never `{"detail": ...}`/raw 422) — covered by T008 and asserted in T023/parity tests.
- `journal.py` and `trades.py` are the only cross-story files; respect the read-before-mutation task ordering.
- Verify each test FAILS before implementing its endpoints.
- The API must expose NO order-placement route at any point (T025 guards this).

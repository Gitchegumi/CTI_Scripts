# Tasks: Provider-Agnostic Market Data Streaming

**Input**: Design documents from `specs/014-market-data-streaming/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Tests**: Required by specification for parsing, heartbeat, fallback, resubscribe, journal dispatch, polling fallback, and graceful shutdown.
**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- All tasks include exact file paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add configuration and test scaffolding without changing runtime behavior yet.

- [X] T001 Add market data env var documentation to `.env.example`
- [X] T002 Add market data configuration constants to `src/tradegumi/config.py`, including mode, reconnect interval, heartbeat timeout, max backoff, and max reconnect attempts
- [X] T003 [P] Create market data test fixture helpers in `src/tradegumi/tests/test_market_data.py`
- [X] T004 [P] Create Oanda stream payload fixtures in `src/tradegumi/tests/test_oanda_market_data.py`
- [X] T005 [P] Review planned Python modules for required module/class/function docstrings before implementation in `src/tradegumi/market_data.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build provider-neutral contracts and shared dispatch that all stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Create provider-neutral lifecycle types and health dataclasses in `src/tradegumi/market_data.py`
- [X] T007 Implement provider-neutral observation dispatch helper in `src/tradegumi/market_data.py`
- [X] T008 Wire observation dispatch to `publish_tick_observations()` or equivalent shared history helpers in `src/tradegumi/price_observations.py`
- [X] T009 Wire observation dispatch to `evaluate_price_observation()` without duplicating journal evaluation in `src/tradegumi/market_data.py`
- [X] T010 [P] Add unit tests for provider-neutral lifecycle state transitions in `src/tradegumi/tests/test_market_data.py`
- [X] T011 [P] Add unit tests for observation dispatch to history and journal evaluator in `src/tradegumi/tests/test_market_data.py`
- [X] T012 Add stream/polling health snapshot shape for runtime state in `src/tradegumi/market_data.py`
- [X] T013 Update code-quality checklist coverage for new market data helpers in `src/tradegumi/tests/test_market_data.py`

**Checkpoint**: Provider-neutral market data foundation is ready for streaming and polling providers.

---

## Phase 3: User Story 1 - Stream Live Prices Without REST Polling Spikes (Priority: P1) MVP

**Goal**: Oanda streaming publishes shared observations and avoids REST price calls while healthy.

**Independent Test**: Run Oanda stream provider tests with stream fixtures and verify observations are published with CTI symbols and `OANDA_PRICING_STREAM`.

### Tests for User Story 1

- [X] T014 [P] [US1] Add Oanda chunked line-delimited price, heartbeat, malformed-line, and unknown-event parsing tests in `src/tradegumi/tests/test_oanda_market_data.py`
- [X] T015 [P] [US1] Add Oanda symbol mapping tests using `config.from_oanda_symbol()` in `src/tradegumi/tests/test_oanda_market_data.py`
- [X] T016 [P] [US1] Add source correctness tests for `OANDA_PRICING_STREAM` observations in `src/tradegumi/tests/test_oanda_market_data.py`
- [X] T017 [P] [US1] Add no-duplicate-REST-pricing test for healthy streaming mode in `src/tradegumi/tests/test_main_market_data.py`

### Implementation for User Story 1

- [X] T018 [US1] Implement Oanda stream event parser for chunked line-delimited JSON events in `src/tradegumi/market_data.py`
- [X] T019 [US1] Implement Oanda streaming provider start/stop read loop using configured practice/live stream URL in `src/tradegumi/market_data.py`
- [X] T020 [US1] Convert Oanda price events to CTI-symbol `PriceObservation` records in `src/tradegumi/market_data.py`
- [X] T021 [US1] Integrate streaming provider construction with existing Oanda client auth/account settings in `src/tradegumi/main.py`
- [X] T022 [US1] Route live price observation through market data provider instead of direct `client.get_pricing()` while streaming is healthy in `src/tradegumi/main.py`
- [X] T023 [US1] Update loop state price merge to read latest shared observations in `src/tradegumi/main.py`
- [X] T024 [US1] Add compact INFO streaming health summary counters in `src/tradegumi/market_data.py`

**Checkpoint**: Oanda streaming can serve as MVP live price source without duplicate REST pricing calls.

---

## Phase 4: User Story 2 - Fallback Safely When Streaming Fails (Priority: P2)

**Goal**: Streaming failures reconnect safely and then fall back to polling without stopping the bot.

**Independent Test**: Simulate auth failure, stale heartbeat, disconnect, and repeated reconnect failures; verify polling observations continue.

### Tests for User Story 2

- [X] T025 [P] [US2] Add heartbeat handling tests in `src/tradegumi/tests/test_oanda_market_data.py`
- [X] T026 [P] [US2] Add stale heartbeat reconnect tests in `src/tradegumi/tests/test_oanda_market_data.py`
- [X] T027 [P] [US2] Add reconnect backoff, max-attempt, fallback, and connection-limit tests in `src/tradegumi/tests/test_oanda_market_data.py`
- [X] T028 [P] [US2] Add polling fallback activation tests in `src/tradegumi/tests/test_market_data.py`
- [X] T029 [P] [US2] Add safe auth error logging tests in `src/tradegumi/tests/test_oanda_market_data.py`

### Implementation for User Story 2

- [X] T030 [US2] Implement heartbeat liveness tracking in `src/tradegumi/market_data.py`
- [X] T031 [US2] Implement bounded reconnect, max-attempt, and backoff-cap policy in `src/tradegumi/market_data.py`
- [X] T032 [US2] Implement repeated-failure transition to polling fallback in `src/tradegumi/market_data.py`
- [X] T033 [US2] Implement polling market data provider wrapper around `ExecutionClient.get_pricing()` in `src/tradegumi/market_data.py`
- [X] T034 [US2] Wire fallback state into main loop market data orchestration in `src/tradegumi/main.py`
- [X] T035 [US2] Ensure provider error logs omit Oanda token/account secrets in `src/tradegumi/market_data.py`

**Checkpoint**: Streaming failure no longer blocks price observation or journal outcome updates.

---

## Phase 5: User Story 3 - Resubscribe Cleanly as Watchlist Changes (Priority: P3)

**Goal**: Market data subscriptions follow scan symbol changes without duplicate active streams.

**Independent Test**: Simulate full, periodic, and API-triggered rescan symbol changes and verify a single active provider observes the latest symbol set.

### Tests for User Story 3

- [X] T036 [P] [US3] Add provider resubscribe tests for changed symbol sets in `src/tradegumi/tests/test_market_data.py`
- [X] T037 [P] [US3] Add no-duplicate-stream worker tests in `src/tradegumi/tests/test_market_data.py`
- [X] T038 [P] [US3] Add rescan-during-reconnect latest-symbol-set test in `src/tradegumi/tests/test_main_market_data.py`
- [X] T039 [P] [US3] Add graceful shutdown tests for active stream workers in `src/tradegumi/tests/test_market_data.py`

### Implementation for User Story 3

- [X] T040 [US3] Detect scan symbol changes and call provider resubscribe in `src/tradegumi/main.py`
- [X] T041 [US3] Stop old stream workers before replacing subscription generation in `src/tradegumi/market_data.py`
- [X] T042 [US3] Ensure reconnect uses latest subscription generation in `src/tradegumi/market_data.py`
- [X] T043 [US3] Add provider stop call to main shutdown handling in `src/tradegumi/main.py`
- [X] T044 [US3] Update runtime state with active symbol count and provider mode in `src/tradegumi/main.py`

**Checkpoint**: Rescans and shutdown manage market data lifecycle cleanly.

---

## Phase 6: User Story 4 - Preserve Provider Portability (Priority: P4)

**Goal**: Core consumers remain provider-agnostic and can be tested with a fake provider.

**Independent Test**: Fake provider publishes observations and drives journal/dashboard/signal behavior without Oanda imports.

### Tests for User Story 4

- [X] T045 [P] [US4] Add fake-provider consumer test for journal dispatch in `src/tradegumi/tests/test_market_data.py`
- [X] T046 [P] [US4] Add fake-provider latest-observation test for signal trigger pricing in `src/tradegumi/tests/test_signal_engine.py`
- [X] T047 [P] [US4] Add dashboard/runtime state no-provider-specific-fields test in `src/tradegumi/tests/test_main_market_data.py`

### Implementation for User Story 4

- [X] T048 [US4] Remove or isolate any Oanda-specific branching from journal/dashboard/signal consumers in `src/tradegumi/main.py`
- [X] T049 [US4] Keep Oanda stream raw payload handling isolated in provider code in `src/tradegumi/market_data.py`
- [X] T050 [US4] Add provider-neutral health response serialization in `src/tradegumi/api_server.py`
- [X] T051 [US4] Update dashboard types only if market-data health is surfaced in `dashboard/src/types/index.ts`

**Checkpoint**: Future MatchTrader market data can implement the provider contract without rewriting consumers.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and operational hardening across all stories.

- [X] T052 [P] Update operator documentation for streaming mode and fallback in `docs/signal-journal.md`
- [X] T053 [P] Add `.env.example` comments for Oanda practice/live stream URLs and fallback settings
- [X] T054 Run quickstart validation scenarios from `specs/014-market-data-streaming/quickstart.md` using deterministic tests; live Oanda credential validation deferred
- [X] T055 Run focused pytest suite for market data, Oanda stream, signal outcomes, and price observations, including streamed journal dispatch timing coverage
- [X] T056 Run dashboard lint/build if dashboard files changed; not required because dashboard files were unchanged
- [X] T057 Review changed Python code for intention-revealing names and no unexplained magic values
- [X] T058 Verify required docstrings on new/modified Python modules, public classes, public methods, public functions, and non-trivial helpers
- [X] T059 Confirm logs redact secrets and detailed observation logs remain DEBUG-only
- [X] T060 Submit PR with DockeGumi as reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 Streaming MVP (Phase 3)**: Depends on Foundational.
- **US2 Fallback (Phase 4)**: Depends on Foundational and integrates with US1 but can be tested with fake providers.
- **US3 Resubscribe (Phase 5)**: Depends on Foundational and provider lifecycle from US1/US2.
- **US4 Portability (Phase 6)**: Depends on Foundational and validates final consumer boundaries.
- **Polish (Phase 7)**: Depends on selected stories being complete.

### User Story Dependencies

- **US1 (P1)**: MVP live streaming path; start after Foundational.
- **US2 (P2)**: Safe fallback and reconnect; should follow US1 for full streaming behavior but can test fallback provider independently.
- **US3 (P3)**: Resubscribe lifecycle; follows provider lifecycle work.
- **US4 (P4)**: Portability verification; best after consumer wiring is complete.

### Parallel Opportunities

- Fixture/test scaffolding tasks T003-T004 can run in parallel.
- Foundational tests T010-T011 can run in parallel.
- Story-specific test tasks marked [P] can run before corresponding implementation tasks.
- Documentation and env example polish tasks can run in parallel with final validation.

## Parallel Example: User Story 1

```text
Task: "T014 Add Oanda price-line parsing tests in src/tradegumi/tests/test_oanda_market_data.py"
Task: "T015 Add Oanda symbol mapping tests using config.from_oanda_symbol() in src/tradegumi/tests/test_oanda_market_data.py"
Task: "T016 Add source correctness tests for OANDA_PRICING_STREAM observations in src/tradegumi/tests/test_oanda_market_data.py"
Task: "T017 Add no-duplicate-REST-pricing test for healthy streaming mode in src/tradegumi/tests/test_main_market_data.py"
```

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Complete US1 so Oanda streaming publishes shared observations and avoids duplicate REST pricing.
3. Validate journal, dashboard, and signal cadence are preserved.

### Incremental Delivery

1. Add streaming MVP.
2. Add reconnect and polling fallback.
3. Add resubscribe/shutdown lifecycle.
4. Verify provider portability and dashboard/runtime health.
5. Polish docs, env examples, and validation.

### Stop Conditions

- Stop if streaming causes missed Signal Journal TP/SL updates.
- Stop if duplicate active streams are detected.
- Stop if reconnect behavior risks exceeding Oanda connection limits.
- Stop if any source code change leaks Oanda-specific stream objects into signal, journal, or dashboard consumers.

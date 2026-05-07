# Tasks: OANDA API Resilience

**Input**: Design documents from `/specs/009-oanda-api-resilience/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by the feature specification. Write or update focused pytest coverage for OANDA paths, retries, completion flags, signal diagnostics, and passive metrics behavior.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Audit current OANDA integration and diagnostics before changing behavior.

- [x] T001 Inspect current OANDA request wrapper, timeout behavior, URL construction, retry absence, candle parsing, position paths, trade dependent-order path, and order parser in `src/tradegumi/api/oanda_client.py`
- [x] T002 [P] Inspect shared `Candle` model and execution client contract in `src/tradegumi/api/base_client.py`
- [x] T003 [P] Inspect OANDA URL defaults and symbol conversion behavior in `src/tradegumi/config.py`
- [x] T004 [P] Inspect signal-engine candle retrieval, complete-candle selection, upstream exception classification, and missing indicator-column classification in `src/tradegumi/signal_engine.py`
- [x] T005 [P] Inspect strategy metrics API/data failure classification in `src/tradegumi/strategy_metrics.py`
- [x] T006 [P] Create or locate OANDA client test file `src/tradegumi/tests/test_oanda_client.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared provider request/error and candle-completion primitives before user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T007 Add provider-neutral candle completion field with backward-compatible default in `src/tradegumi/api/base_client.py`
- [x] T008 Define OANDA retryable status constants, timeout defaults, and safe diagnostic fields in `src/tradegumi/api/oanda_client.py`
- [x] T009 Define a structured OANDA request exception or diagnostic carrier with method, path, status, instrument, granularity, attempts, and non-secret message in `src/tradegumi/api/oanda_client.py`
- [x] T010 Add docstrings for new OANDA helper/exception primitives in `src/tradegumi/api/oanda_client.py`

**Checkpoint**: Shared request/error and candle primitives are ready for story implementation.

---

## Phase 3: User Story 1 - Recover From Transient OANDA Candle Failures (Priority: P1) MVP

**Goal**: Transient OANDA candle failures retry before signal evaluation and repeated failures become precise indeterminate API/data diagnostics.

**Independent Test**: Simulate transient candle retrieval responses and confirm retry succeeds or an exhausted failure is indeterminate with provider-specific context.

### Tests for User Story 1

- [x] T011 [P] [US1] Add tests for 504 retry-before-success candle retrieval in `src/tradegumi/tests/test_oanda_client.py`
- [x] T012 [P] [US1] Add tests for 429, 500, 502, 503, and 504 retryable status handling in `src/tradegumi/tests/test_oanda_client.py`
- [x] T013 [P] [US1] Add tests for non-retryable 4xx immediate failure with method, path, status, instrument, granularity, and attempt context in `src/tradegumi/tests/test_oanda_client.py`
- [x] T014 [P] [US1] Add signal-engine test proving repeated OANDA candle fetch failure produces indeterminate diagnostics rather than normal no-signal or strategy rejection in `src/tradegumi/tests/test_signal_engine.py`

### Implementation for User Story 1

- [x] T015 [US1] Normalize OANDA REST and stream base URLs with trailing slash removal in `src/tradegumi/config.py` and `src/tradegumi/api/oanda_client.py`
- [x] T016 [US1] Add bounded request timeout to all OANDA REST requests in `src/tradegumi/api/oanda_client.py`
- [x] T017 [US1] Implement retry/backoff for retryable OANDA statuses and network timeouts in `src/tradegumi/api/oanda_client.py`
- [x] T018 [US1] Ensure candle fetch failures preserve OANDA diagnostic context through signal-engine indeterminate diagnostics in `src/tradegumi/signal_engine.py`
- [x] T019 [US1] Ensure repeated OANDA candle failures are not classified as no-trend, normal no-signal, or strategy rejection in `src/tradegumi/signal_engine.py` and `src/tradegumi/strategy_metrics.py`

**Checkpoint**: User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Verify OANDA Endpoint and Response Contracts (Priority: P2)

**Goal**: Every OANDA REST path and order response parser used by the bot matches documented v20 behavior.

**Independent Test**: Unit tests inspect all client paths and transaction-based order creation parsing.

### Tests for User Story 2

- [x] T020 [P] [US2] Add URL normalization tests proving no double slashes for trailing base URLs in `src/tradegumi/tests/test_oanda_client.py`
- [x] T021 [P] [US2] Add endpoint path tests for candles, pricing, account summary, account instruments, open positions, single position, close position, trade dependent-order modification, and order creation in `src/tradegumi/tests/test_oanda_client.py`
- [x] T022 [P] [US2] Add order creation parser tests for create/fill, cancel, reject, related transaction, and last transaction response shapes in `src/tradegumi/tests/test_oanda_client.py`

### Implementation for User Story 2

- [x] T023 [US2] Add `price=M` to OANDA candle request params in `src/tradegumi/api/oanda_client.py`
- [x] T024 [US2] Fix single-position lookup to use `/v3/accounts/{accountID}/positions/{instrument}` in `src/tradegumi/api/oanda_client.py`
- [x] T025 [US2] Ensure close-position requests use `/v3/accounts/{accountID}/positions/{instrument}/close` with instrument identifiers in `src/tradegumi/api/oanda_client.py`
- [x] T026 [US2] Fix SL/TP dependent-order modification to use `/v3/accounts/{accountID}/trades/{tradeSpecifier}/orders` in `src/tradegumi/api/oanda_client.py`
- [x] T027 [US2] Fix order creation response parsing to handle transaction-based OANDA response fields without assuming top-level `order` in `src/tradegumi/api/oanda_client.py`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Preserve Complete-Candle Signal Inputs and Diagnostics (Priority: P3)

**Goal**: Only provider-complete candles feed indicator windows, and upstream data failures remain distinguishable from strategy-rule outcomes.

**Independent Test**: Feed complete, incomplete, partial, malformed, and failed candle responses through client/signal/metrics tests and inspect diagnostics.

### Tests for User Story 3

- [x] T028 [P] [US3] Add candle parsing test proving OANDA `complete` is preserved in `src/tradegumi/tests/test_oanda_client.py`
- [x] T029 [P] [US3] Add signal-engine test proving incomplete provider candles are excluded from signal evaluation in `src/tradegumi/tests/test_signal_engine.py`
- [x] T030 [P] [US3] Add test proving missing MACD signal or indicator columns caused by upstream candle failure are diagnosed as upstream data/API failure, not strategy rejection, in `src/tradegumi/tests/test_signal_engine.py`
- [x] T031 [P] [US3] Add regression test proving metrics collection remains passive and does not mutate signal-engine candle inputs in `src/tradegumi/tests/test_strategy_metrics.py`

### Implementation for User Story 3

- [x] T032 [US3] Preserve OANDA candle `complete` flag when constructing `Candle` objects in `src/tradegumi/api/oanda_client.py`
- [x] T033 [US3] Filter or select signal-engine candle windows using provider `complete` before indicator calculation in `src/tradegumi/signal_engine.py`
- [x] T034 [US3] Diagnose malformed OANDA candle responses and missing midpoint data as `oanda_response_malformed` or operation-specific OANDA data failure in `src/tradegumi/api/oanda_client.py`
- [x] T035 [US3] Map upstream OANDA failures and missing indicator columns caused by upstream data failure to indeterminate diagnostics in `src/tradegumi/signal_engine.py` and `src/tradegumi/strategy_metrics.py`

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and handoff.

- [x] T036 [P] Update OANDA/API failure diagnostic documentation in `docs/strategy-metrics.md`
- [x] T037 [P] Update signal journal notes in `docs/signal-journal.md` if provider diagnostics appear in journal-visible fields
- [x] T038 Review changed Python code for intention-revealing names, simple control flow, no unexplained magic values, and useful docstrings in `src/tradegumi/api/oanda_client.py`, `src/tradegumi/api/base_client.py`, `src/tradegumi/signal_engine.py`, and `src/tradegumi/strategy_metrics.py`
- [x] T039 Run focused validation from `specs/009-oanda-api-resilience/quickstart.md`
- [ ] T040 Submit PR with DockeGumi as reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 6)**: Depends on implemented stories and validation.

### User Story Dependencies

- **User Story 1 (P1)**: MVP; starts after Foundational.
- **User Story 2 (P2)**: Starts after Foundational; can run alongside US1 after request helper shape is set.
- **User Story 3 (P3)**: Starts after Foundational; depends on candle completion field and benefits from US1 diagnostics.

### Parallel Opportunities

- T002 through T006 can run in parallel.
- T011 through T014 can be authored in parallel if coordinated across test files.
- T020 through T022 can be authored in parallel if coordinated in `test_oanda_client.py`.
- T028 through T031 can be authored in parallel if coordinated across test files.
- T036 and T037 can run in parallel.

---

## Parallel Example: User Story 1

```text
Task: "Add tests for 504 retry-before-success candle retrieval in src/tradegumi/tests/test_oanda_client.py"
Task: "Add tests for 429, 500, 502, 503, and 504 retryable status handling in src/tradegumi/tests/test_oanda_client.py"
Task: "Add signal-engine test proving repeated OANDA candle fetch failure produces indeterminate diagnostics rather than normal no-signal or strategy rejection in src/tradegumi/tests/test_signal_engine.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational phases.
2. Add failing OANDA retry and signal diagnostic tests.
3. Implement URL normalization, timeout, retry/backoff, and structured provider failure diagnostics.
4. Validate OANDA retry behavior and signal indeterminate classification.

### Incremental Delivery

1. Deliver US1 to stop transient 504s from immediately suppressing signal evaluation.
2. Deliver US2 to correct endpoint contracts and order parser behavior.
3. Deliver US3 to preserve complete candles and clarify upstream-data versus strategy outcomes.
4. Run quickstart validation and prepare PR.

### Notes

- Do not tune thresholds, loosen trend rules, change MACD rules, force signal emission, or alter entry criteria.
- Keep OANDA-specific behavior inside the OANDA client except for provider-neutral candle completion and signal diagnostics.
- Verify tests fail before implementation where the behavior is currently uncovered or incorrect.

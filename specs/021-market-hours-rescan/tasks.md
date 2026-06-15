# Tasks: Forex Market Hours Rescan

**Input**: Design documents from `specs/021-market-hours-rescan/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: Included because the feature specification and quickstart require boundary, rescan, and diagnostic validation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or has no dependency on incomplete tasks
- **[Story]**: User story label for story-phase tasks only
- Every task includes an exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the feature context and prepare source files that will be touched.

- [X] T001 Review existing session, rescan, and dashboard market-state flows in `src/tradegumi/session_rules.py`, `src/tradegumi/main.py`, `src/tradegumi/pre_session_scanner.py`, `src/tradegumi/callback.py`, `dashboard/src/hooks/useData.ts`, and `dashboard/src/types/index.ts`
- [X] T002 [P] Create focused session-rule test file `src/tradegumi/tests/test_session_rules.py`
- [X] T003 [P] Create focused forced-rescan scanner test file `src/tradegumi/tests/test_pre_session_scanner.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared session/availability concepts that all user stories depend on.

**Critical**: No user story implementation should begin until this phase is complete.

- [X] T004 Define stable forex session reason codes and boundary labels in `src/tradegumi/session_rules.py`
- [X] T005 Add a structured forex market-session status helper in `src/tradegumi/session_rules.py` that returns symbol, category, evaluated time, open state, reason, and boundary context
- [X] T006 Preserve existing boolean compatibility by routing `is_trading_open`, `is_market_open`, and `is_trading_day` through the structured session helper in `src/tradegumi/session_rules.py`
- [X] T007 [P] Add shared fake execution-client fixtures for scanner/rescan tests in `src/tradegumi/tests/test_pre_session_scanner.py`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Recognize the Forex Trading Week (Priority: P1) MVP

**Goal**: Forex instruments are open from Sunday 16:00 CT / 17:00 ET through Friday 16:00 CT / 17:00 ET, and closed outside that weekly window.

**Independent Test**: Run `pytest src\tradegumi\tests\test_session_rules.py` and verify Sunday open, weekday open, Friday close, Saturday closed, and DST-aware cases.

### Tests for User Story 1

- [X] T008 [P] [US1] Add Sunday 15:59 CT closed, Sunday 16:00 CT open, and Sunday 21:40 CT open tests in `src/tradegumi/tests/test_session_rules.py`
- [X] T009 [P] [US1] Add weekday open, Friday 15:59 CT open, Friday 16:00 CT closed, and Saturday closed tests in `src/tradegumi/tests/test_session_rules.py`
- [X] T010 [P] [US1] Add daylight-saving boundary equivalence tests for Central and Eastern timestamps in `src/tradegumi/tests/test_session_rules.py`

### Implementation for User Story 1

- [X] T011 [US1] Replace weekday-only forex hours with weekly forex open/close evaluation in `src/tradegumi/session_rules.py`
- [X] T012 [US1] Ensure commodities that intentionally follow forex rules use the same weekly session behavior in `src/tradegumi/session_rules.py`
- [X] T013 [US1] Keep crypto always-open behavior and existing non-forex category behavior from regressing in `src/tradegumi/session_rules.py`
- [X] T014 [US1] Update or remove stale Oanda-specific forex-hours comments so documented behavior matches the implemented 17:00 ET boundary in `src/tradegumi/session_rules.py`
- [X] T015 [US1] Run `pytest src\tradegumi\tests\test_session_rules.py`

**Checkpoint**: User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Forced Rescan Preserves Symbol Availability (Priority: P2)

**Goal**: Forced rescans during the open forex trading week evaluate each symbol independently and do not mark every symbol unavailable because of a global closed-market decision.

**Independent Test**: Run scanner/rescan tests with a fake execution client and verify available symbols remain available during open forex hours while symbol-specific unavailable results stay isolated.

### Tests for User Story 2

- [X] T016 [P] [US2] Add forced-rescan test for open forex hours preserving available symbols in `src/tradegumi/tests/test_pre_session_scanner.py`
- [X] T017 [P] [US2] Add forced-rescan test for symbol-specific unavailable reasons affecting only those symbols in `src/tradegumi/tests/test_pre_session_scanner.py`
- [X] T018 [P] [US2] Add rescan command regression coverage for `force_rescan` behavior in `src/tradegumi/tests/test_commands.py`

### Implementation for User Story 2

- [X] T019 [US2] Add per-symbol availability result construction that separates forex market closure from account/instrument unavailability in `src/tradegumi/pre_session_scanner.py`
- [X] T020 [US2] Update forced-rescan orchestration to use per-symbol forex market status when refreshing availability in `src/tradegumi/main.py`
- [X] T021 [US2] Include symbol availability counts in rescan callback payloads without breaking existing `trigger` consumers in `src/tradegumi/main.py` and `src/tradegumi/callback.py`
- [X] T022 [US2] Run `pytest src\tradegumi\tests\test_pre_session_scanner.py src\tradegumi\tests\test_commands.py`

**Checkpoint**: User Stories 1 and 2 work independently.

---

## Phase 5: User Story 3 - Explain Market-Closed Decisions (Priority: P3)

**Goal**: Operator-visible diagnostics distinguish forex market closure from symbol unavailability and show useful weekly boundary context.

**Independent Test**: Inspect loop-state and watchlist diagnostic payloads around open/close boundaries and verify dashboard market-open derivation does not treat symbol-specific unavailable states as global market closure.

### Tests for User Story 3

- [X] T023 [P] [US3] Add loop-state diagnostic tests for `market_closed`, `symbol_unavailable`, and `available` availability states in `src/tradegumi/tests/test_main_market_data.py`
- [X] T024 [P] [US3] Add compile-time coverage for additive loop-state diagnostic fields by updating `LoopState` symbol typing in `dashboard/src/types/index.ts`

### Implementation for User Story 3

- [X] T025 [US3] Add `market_open`, `availability_state`, `availability_reason`, and `session_boundary` fields to loop-state symbol entries in `src/tradegumi/main.py`
- [X] T026 [US3] Verify or update Discord market open/close notifications for corrected forex weekly session decisions in `src/tradegumi/main.py` and `src/tradegumi/alerts.py`
- [X] T027 [US3] Update dashboard loop-state types for additive availability diagnostic fields in `dashboard/src/types/index.ts`
- [X] T028 [US3] Update `useMarketOpen` to ignore symbol-specific unavailable states when deriving global market-open polling behavior in `dashboard/src/hooks/useData.ts`
- [X] T029 [US3] Run `pytest src\tradegumi\tests\test_main_market_data.py`
- [X] T030 [US3] Run `npm run build` if `dashboard/src/types/index.ts` or `dashboard/src/hooks/useData.ts` changed

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and release readiness.

- [X] T031 [P] Update operator-facing forex market-hours documentation in `docs/market-hours.md`
- [X] T032 Review changed Python code for intention-revealing names, simple control flow, no unexplained magic values, and useful docstrings in `src/tradegumi/session_rules.py`, `src/tradegumi/main.py`, and `src/tradegumi/pre_session_scanner.py`
- [X] T033 Run quickstart validation commands from `specs/021-market-hours-rescan/quickstart.md`
- [X] T034 Run targeted regression tests for affected signal/session flows with `pytest src\tradegumi\tests\test_session_rules.py src\tradegumi\tests\test_pre_session_scanner.py src\tradegumi\tests\test_main_market_data.py src\tradegumi\tests\test_commands.py`
- [X] T035 Confirm no signal-layer, risk-check, watchlist-membership, or broker-specific session-rule regressions were introduced in `src/tradegumi/session_rules.py`, `src/tradegumi/main.py`, and `src/tradegumi/pre_session_scanner.py`
- [X] T036 Submit PR as author DockeGumi with email "dock@gitchegumi.com" and request review from Gitchegumi.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion - MVP
- **User Story 2 (Phase 4)**: Depends on Foundational completion and benefits from US1 session correctness
- **User Story 3 (Phase 5)**: Depends on Foundational completion and integrates diagnostics from US1/US2
- **Polish (Phase 6)**: Depends on selected user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Start after Phase 2; no dependency on US2 or US3
- **User Story 2 (P2)**: Start after Phase 2; validates best after US1 but can use fake open-session helpers independently
- **User Story 3 (P3)**: Start after Phase 2; consumes diagnostic fields from US1/US2

### Parallel Opportunities

- T002 and T003 can run in parallel after T001
- T007 can run in parallel with T004-T006
- US1 tests T008-T010 can be drafted in parallel
- US2 tests T016-T018 can be drafted in parallel
- US3 tests T023-T024 can be drafted in parallel
- Documentation task T030 can run in parallel with final validation tasks after implementation

## Parallel Example: User Story 1

```text
Task: "Add Sunday boundary tests in src/tradegumi/tests/test_session_rules.py"
Task: "Add Friday/weekend tests in src/tradegumi/tests/test_session_rules.py"
Task: "Add DST equivalence tests in src/tradegumi/tests/test_session_rules.py"
```

## Parallel Example: User Story 2

```text
Task: "Add open forex forced-rescan test in src/tradegumi/tests/test_pre_session_scanner.py"
Task: "Add symbol-specific unavailable forced-rescan test in src/tradegumi/tests/test_pre_session_scanner.py"
Task: "Add rescan command regression coverage in src/tradegumi/tests/test_commands.py"
```

## Parallel Example: User Story 3

```text
Task: "Add loop-state diagnostic tests in src/tradegumi/tests/test_main_market_data.py"
Task: "Add dashboard diagnostic field validation in dashboard/src/types/index.ts"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 to correct the forex weekly session rules.
3. Run `pytest src\tradegumi\tests\test_session_rules.py`.
4. Stop and validate the Sunday 21:40 CT, Sunday open, weekday open, Friday close, and Saturday closed cases.

### Incremental Delivery

1. Complete Setup and Foundational tasks.
2. Deliver US1 to fix forex market-open classification.
3. Deliver US2 to fix forced-rescan availability behavior.
4. Deliver US3 to improve diagnostics and dashboard market-open derivation.
5. Complete Polish tasks and reviewer handoff.

### Notes

- Keep session logic broker-neutral.
- Do not change signal-layer thresholds, risk gates, or watchlist scoring as part of this feature.
- Tests should fail before implementation when feasible.
- Additive payload fields must remain backward compatible for existing API/callback consumers.

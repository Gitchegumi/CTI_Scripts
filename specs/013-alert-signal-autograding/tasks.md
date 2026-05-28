# Tasks: Alert Signal Auto-Grading

**Input**: Design documents from `/specs/013-alert-signal-autograding/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by the feature specification. Write focused tests before implementation where practical.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the codebase for shared price observations and outcome fields.

- [x] T001 Inspect current journal field defaults, export headers, and prime helper behavior in `src/tradegumi/journal.py`
- [x] T002 Inspect current one-second pricing path in `src/tradegumi/main.py` and current live dashboard price consumers in `src/tradegumi/api_server.py` and `dashboard/src/hooks/useData.ts`
- [x] T003 [P] Create placeholder test modules `src/tradegumi/tests/test_price_observations.py` and `src/tradegumi/tests/test_signal_outcomes.py`
- [x] T004 [P] Confirm Python docstring expectations for new modules in `src/tradegumi/price_observations.py` and `src/tradegumi/signal_outcomes.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and journal helpers required by all user stories.

**CRITICAL**: No user story implementation should begin until this phase is complete.

- [x] T005 [P] Implement `PriceObservation`, source constants, timestamp normalization, and bid/ask/mid derivation in `src/tradegumi/price_observations.py`
- [x] T006 [P] Implement bounded per-symbol rolling history and latest-observation read helpers in `src/tradegumi/price_observations.py`
- [x] T007 [P] Add unit tests for observation validation, mid derivation, latest lookup, and bounded pruning in `src/tradegumi/tests/test_price_observations.py`
- [x] T008 Add additive journal outcome constants, default normalization helpers, and export header fields in `src/tradegumi/journal.py`
- [x] T009 Add journal read/update helpers for unresolved alert-only/developing entries and outcome field updates in `src/tradegumi/journal.py`
- [x] T010 Add tests for legacy, expired, invalidated, and export-compatible outcome fields in `src/tradegumi/tests/test_journal.py`

**Checkpoint**: Foundation ready; the repo has a neutral observation model and journal can safely read/write outcome fields.

---

## Phase 3: User Story 1 - Auto-Grade Alert-Only Signals (Priority: P1) MVP

**Goal**: Automatically close unresolved alert-only/developing journal entries when target or stop is touched.

**Independent Test**: Create alert-only BUY/SELL entries, feed ordered observations, and verify TP, SL, and still-open outcomes without signal generation or trade execution.

### Tests for User Story 1

- [x] T011 [P] [US1] Add long TP, long SL, short TP, short SL, and no-hit evaluator tests in `src/tradegumi/tests/test_signal_outcomes.py`
- [x] T012 [P] [US1] Add midpoint fallback outcome-source test in `src/tradegumi/tests/test_signal_outcomes.py`
- [x] T013 [P] [US1] Add same-cycle ambiguous TP/SL test in `src/tradegumi/tests/test_signal_outcomes.py`

### Implementation for User Story 1

- [x] T014 [US1] Implement outcome decision dataclasses and BUY/SELL bid/ask/midpoint rules in `src/tradegumi/signal_outcomes.py`
- [x] T015 [US1] Implement evaluator service that evaluates unresolved same-symbol entries and updates only journal outcome fields in `src/tradegumi/signal_outcomes.py`
- [x] T016 [US1] Update `src/tradegumi/journal.py` to map auto TP/SL outcomes to compatible `grade` and `trade_grade` values without breaking existing filters
- [x] T017 [US1] Record `outcome_checked_at`, `exit_time`, `exit_price`, `observations_to_outcome`, `max_favorable_excursion`, and `max_adverse_excursion` when available in `src/tradegumi/journal.py`
- [x] T018 [US1] Run focused backend tests for `src/tradegumi/tests/test_signal_outcomes.py` and related journal tests

**Checkpoint**: User Story 1 works independently as the MVP.

---

## Phase 4: User Story 2 - Reuse Live Price Observations (Priority: P1)

**Goal**: Feed dashboard and evaluator from the existing live price observation path without adding a second polling loop.

**Independent Test**: Run or simulate the one-second price loop and verify observations publish once, dashboard reads still work, and evaluator receives the same observations.

### Tests for User Story 2

- [x] T019 [P] [US2] Add test proving published `PriceTick` values become `dashboard_poll` observations in `src/tradegumi/tests/test_price_observations.py`
- [x] T020 [P] [US2] Add integration-style test with a fake client showing one pricing fetch feeds evaluator updates in `src/tradegumi/tests/test_signal_outcomes.py`

### Implementation for User Story 2

- [x] T021 [US2] Publish existing one-second `client.get_pricing(scan_symbols)` ticks into the shared observation service in `src/tradegumi/main.py`
- [x] T022 [US2] Invoke the signal outcome evaluator from the same observation publication path in `src/tradegumi/main.py`
- [x] T023 [US2] Add latest price observation read support for dashboard/API consumers in `src/tradegumi/api_server.py` where it avoids duplicate pricing calls
- [x] T024 [US2] Ensure `/api/positions` behavior in `src/tradegumi/api_server.py` remains backward compatible if no shared observation exists
- [x] T025 [US2] Run tests that verify no evaluator-specific `get_pricing()` call path exists

**Checkpoint**: Dashboard-price and evaluator flow share the backend observation path.

---

## Phase 5: User Story 3 - Preserve Manual Review Control (Priority: P1)

**Goal**: Keep manually graded or locked entries from being overwritten, while allowing reset entries to become auto-gradable again.

**Independent Test**: Manually grade a signal, feed conflicting prices, and verify the manual outcome remains; reset to pending and verify eligibility returns when not locked.

### Tests for User Story 3

- [x] T026 [P] [US3] Add manual override is not overwritten test in `src/tradegumi/tests/test_signal_outcomes.py`
- [x] T027 [P] [US3] Add reset-to-pending clears auto outcome eligibility test in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 3

- [x] T028 [US3] Update manual grade and invalidation flows to set manual override fields in `src/tradegumi/journal.py`
- [x] T029 [US3] Update reset flow to clear auto outcome fields and preserve manual lock semantics in `src/tradegumi/journal.py`
- [x] T030 [US3] Ensure evaluator skips manually overridden or manually locked entries in `src/tradegumi/signal_outcomes.py`
- [x] T031 [US3] Run focused manual grade/reset/evaluator tests

**Checkpoint**: Manual review state remains authoritative.

---

## Phase 6: User Story 4 - Resolve Prime Signal Conflicts (Priority: P2)

**Goal**: Align active prime suppression with auto-graded outcomes.

**Independent Test**: Resolve an existing prime by TP/SL before a new same-symbol signal and verify replacement; leave prime unresolved and verify block/invalidation count.

### Tests for User Story 4

- [x] T032 [P] [US4] Add unresolved prime blocks and increments invalidated-by-prime test in `src/tradegumi/tests/test_journal.py`
- [x] T033 [P] [US4] Add resolved TP/SL prime allows new prime test in `src/tradegumi/tests/test_journal.py`
- [x] T034 [P] [US4] Add ambiguous prime prevents duplicate open prime test in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 4

- [x] T035 [US4] Update active-prime detection to treat auto TP/SL outcomes as resolved in `src/tradegumi/journal.py`
- [x] T036 [US4] Record `invalidated_by_prime` outcome/status/source when a new same-symbol signal is blocked in `src/tradegumi/journal.py`
- [x] T037 [US4] Ensure prime deactivation and new-prime creation remain atomic within append/update locking in `src/tradegumi/journal.py`
- [x] T038 [US4] Update prime suppression metrics for invalidated-by-prime evidence if supported in `src/tradegumi/strategy_metrics.py`
- [x] T039 [US4] Run focused prime suppression and strategy metrics tests

**Checkpoint**: Prime suppression agrees with auto-graded journal outcomes.

---

## Phase 7: User Story 5 - Review Outcomes in Journal and Exports (Priority: P2)

**Goal**: Show auto-graded status, outcome, source, exit details, manual state, and ambiguity in API/dashboard/export surfaces without clutter.

**Independent Test**: Auto-grade several records, load journal API/dashboard, and export CSV to verify outcome fields render and legacy entries still work.

### Tests for User Story 5

- [x] T040 [P] [US5] Add export fields test for status/outcome/source/exit/manual/ambiguous fields in `src/tradegumi/tests/test_journal.py`
- [x] T041 [P] [US5] Add dashboard type coverage for journal outcome fields in `dashboard/src/types/index.ts`

### Implementation for User Story 5

- [x] T042 [US5] Pass additive outcome fields through journal API responses in `src/tradegumi/api_server.py`
- [x] T043 [US5] Add compact outcome/source/exit/manual/ambiguous rendering to `dashboard/src/app/journal/page.tsx`
- [x] T044 [US5] Update shared dashboard journal types in `dashboard/src/types/index.ts`
- [x] T045 [US5] Update journal export behavior and filename compatibility checks in `src/tradegumi/journal.py`
- [x] T046 [US5] Run dashboard lint/build checks from `dashboard/` when UI/types compile

**Checkpoint**: Analysts can review and export auto-graded outcomes.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, regression, quality, and PR preparation.

- [x] T047 [P] Update or create `docs/signal-journal.md` with auto-grading fields, manual override behavior, reset behavior, and streaming upgrade note
- [x] T048 Review changed Python code for intention-revealing names, simple control flow, bounded retention, and no unexplained magic values
- [x] T049 Add or update Python module, class, function, method, and non-trivial helper docstrings in `src/tradegumi/price_observations.py`, `src/tradegumi/signal_outcomes.py`, and modified journal/API helpers
- [x] T050 Run `pytest src/tradegumi/tests`
- [x] T051 Run `npm run lint` and `npm run build` from `dashboard/` if dashboard files changed
- [x] T052 Verify quickstart scenarios in `specs/013-alert-signal-autograding/quickstart.md`
- [x] T053 Confirm no undocumented broker browser/chart/devtools endpoint usage was introduced anywhere under `src/` or `dashboard/`
- [x] T054 Submit PR with DockeGumi as reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 Auto-Grading (Phase 3)**: Depends on Foundational; MVP.
- **US2 Price Reuse (Phase 4)**: Depends on Foundational and integrates with US1 evaluator.
- **US3 Manual Control (Phase 5)**: Depends on Foundational and US1 journal/evaluator behavior.
- **US4 Prime Conflicts (Phase 6)**: Depends on US1 and current prime helpers.
- **US5 Journal Review (Phase 7)**: Depends on journal fields from Foundational/US1.
- **Polish (Phase 8)**: Depends on desired user stories.

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational and is the MVP.
- **US2 (P1)**: Can start after Foundational; final evaluator integration depends on US1 service shape.
- **US3 (P1)**: Can start after Foundational; skip behavior depends on US1 evaluator.
- **US4 (P2)**: Depends on US1 outcome state and existing prime helpers.
- **US5 (P2)**: Depends on outcome fields being available from earlier phases.

### Parallel Opportunities

- T003 and T004 can run in parallel.
- T005, T006, and T007 can be developed in tight TDD order; tests and implementation touch separate files.
- US1 tests T011-T013 can be written in parallel before T014-T017.
- US3 tests T026-T027 can be written in parallel.
- US4 tests T032-T034 can be written in parallel.
- Documentation T047 can run after field names stabilize while final regression runs continue.

## Parallel Example: User Story 1

```text
Task: "Add long TP, long SL, short TP, short SL, and no-hit evaluator tests in src/tradegumi/tests/test_signal_outcomes.py"
Task: "Add midpoint fallback outcome-source test in src/tradegumi/tests/test_signal_outcomes.py"
Task: "Add same-cycle ambiguous TP/SL test in src/tradegumi/tests/test_signal_outcomes.py"
```

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks.
2. Complete US1 tests and evaluator implementation.
3. Validate TP, SL, no-hit, midpoint, and ambiguous behavior before integrating into the live loop.

### Incremental Delivery

1. US1 delivers deterministic auto-grading against supplied observations.
2. US2 wires those observations into the existing one-second backend pricing path.
3. US3 protects manual review workflows.
4. US4 aligns prime suppression with resolved outcomes.
5. US5 exposes compact review/export surfaces.

### Safety Notes

- The evaluator must not call broker clients.
- The signal engine must not own grading decisions.
- Existing manual grades and legacy records remain compatible.
- Every Python public module/class/function added or modified needs useful docstrings.

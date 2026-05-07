# Tasks: Fix Signal Stack IndexError

**Input**: Design documents from `/specs/008-fix-signal-indexerror/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/signal-stack-readiness.md, quickstart.md

**Tests**: Required by the feature specification. Add/adjust focused pytest coverage before implementation changes where practical.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm current signal-stack and diagnostics surface before editing behavior.

- [x] T001 Inspect current M5 candle retrieval, closed-candle selection, indicator indexing, and exception handling in `src/tradegumi/signal_engine.py`
- [x] T002 [P] Inspect current signal-engine blocker and pipeline-state classification in `src/tradegumi/strategy_metrics.py`
- [x] T003 [P] Inspect existing signal and metrics regression tests in `src/tradegumi/tests/test_signal_engine.py` and `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T004 [P] Confirm documentation locations for signal diagnostics in `docs/strategy-metrics.md` and `docs/signal-journal.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared readiness model and expected diagnostic contract before user-story implementation.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T005 Define the required signal-stack readiness fields and counts in `src/tradegumi/signal_engine.py`
- [x] T006 Define reusable data-not-ready diagnostic construction for signal-stack readiness in `src/tradegumi/signal_engine.py`
- [x] T007 Ensure new or modified Python helpers in `src/tradegumi/signal_engine.py` have useful docstrings and intention-revealing names

**Checkpoint**: Readiness diagnostic shape is established and user story implementation can begin.

---

## Phase 3: User Story 1 - Defer Signal Evaluation When Data Is Not Ready (Priority: P1) MVP

**Goal**: Signal stack classifies missing closed-candle or indicator-window inputs as structured data-not-ready outcomes without raw indexing failures.

**Independent Test**: Evaluate signal-stack inputs with empty, one-row, open-only, and warmup-short M5 data and confirm structured data-not-ready diagnostics with no raw indexing failure.

### Tests for User Story 1

- [x] T008 [P] [US1] Add empty M5 candle list and one-candle M5 list regression tests in `src/tradegumi/tests/test_signal_engine.py`
- [x] T009 [P] [US1] Add no-fully-closed-candle regression test in `src/tradegumi/tests/test_signal_engine.py`
- [x] T010 [P] [US1] Add insufficient indicator-window regression tests for zero and short usable indicator output in `src/tradegumi/tests/test_signal_engine.py`

### Implementation for User Story 1

- [x] T011 [US1] Implement pre-evaluation raw candle and closed-candle readiness validation in `src/tradegumi/signal_engine.py`
- [x] T012 [US1] Implement pre-index indicator-window readiness validation before StochRSI, MACD, Keltner, candlestick, and recent-candle slicing in `src/tradegumi/signal_engine.py`
- [x] T013 [US1] Replace normal short-data raw `IndexError` classification with structured `DataNotReady` diagnostics in `src/tradegumi/signal_engine.py`
- [x] T014 [US1] Ensure data-not-ready returns existing deferred or indeterminate signal result without strategy rejection in `src/tradegumi/signal_engine.py`

**Checkpoint**: User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Preserve Normal Signal Rule Evaluation When Inputs Are Ready (Priority: P2)

**Goal**: Complete, aligned input data proceeds to candle-close gate and existing signal rules without being marked as missing signal-engine data.

**Independent Test**: Provide valid aligned M5 candle and indicator data and confirm signal-engine data is not missing before existing rule evaluation.

### Tests for User Story 2

- [x] T015 [P] [US2] Add valid aligned M5 candle and indicator progression test in `src/tradegumi/tests/test_signal_engine.py`
- [x] T016 [P] [US2] Add test proving strategy-rule rejection remains `criteria_failed` rather than data-not-ready in `src/tradegumi/tests/test_signal_engine.py`

### Implementation for User Story 2

- [x] T017 [US2] Ensure M5 candle request/retention count satisfies the largest signal-stack indicator window in `src/tradegumi/signal_engine.py`
- [x] T018 [US2] Ensure evaluation uses the previous fully closed candle when the latest candle is open and a previous closed candle exists in `src/tradegumi/signal_engine.py`
- [x] T019 [US2] Preserve existing signal-rule thresholds, trend logic, and emitted/rejected decision semantics in `src/tradegumi/signal_engine.py`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Report Complete Readiness Diagnostics (Priority: P3)

**Goal**: Metrics and signal journal consumers receive complete, backward-compatible readiness diagnostics and blockers.

**Independent Test**: Inspect metrics output for readiness failures and confirm required counts, blocker fields, and compatibility fields are present.

### Tests for User Story 3

- [x] T020 [P] [US3] Add metrics test for `DataNotReady` diagnostic fields in `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T021 [P] [US3] Add metrics test for `decision_reason`, `first_blocker`, `all_blockers`, `blocking_layer`, and `blocked_signal` on missing signal-engine data in `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T022 [P] [US3] Add backward-compatible metrics JSON field test in `src/tradegumi/tests/test_strategy_metrics.py`

### Implementation for User Story 3

- [x] T023 [US3] Populate structured readiness diagnostic counts and `DataNotReady` type in `src/tradegumi/signal_engine.py`
- [x] T024 [US3] Ensure blocker/layer classification distinguishes data-not-ready from strategy rejection in `src/tradegumi/strategy_metrics.py`
- [x] T025 [US3] Preserve existing metrics JSON fields while adding readiness fields in `src/tradegumi/strategy_metrics.py`

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, validation, and PR handoff.

- [x] T026 [P] Update signal readiness diagnostics documentation in `docs/strategy-metrics.md`
- [x] T027 [P] Update signal journal diagnostic notes if applicable in `docs/signal-journal.md`
- [x] T028 Review changed Python code for intention-revealing names, simple control flow, no unexplained magic values, and useful docstrings in `src/tradegumi/signal_engine.py` and `src/tradegumi/strategy_metrics.py`
- [x] T029 Run focused validation from `specs/008-fix-signal-indexerror/quickstart.md`
- [ ] T030 Submit PR with DockeGumi as reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 6)**: Depends on implemented stories and validation.

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational; MVP scope.
- **User Story 2 (P2)**: Starts after Foundational; can be validated independently but should be checked after US1 readiness helpers exist.
- **User Story 3 (P3)**: Starts after Foundational; depends on the diagnostic shape from US1.

### Parallel Opportunities

- T002, T003, and T004 can run in parallel.
- T008, T009, and T010 can be authored in parallel if coordinated in the same test file.
- T015 and T016 can be authored in parallel if coordinated in the same test file.
- T020, T021, and T022 can be authored in parallel if coordinated in the same test file.
- T026 and T027 can run in parallel.

---

## Parallel Example: User Story 1

```text
Task: "Add empty M5 candle list and one-candle M5 list regression tests in src/tradegumi/tests/test_signal_engine.py"
Task: "Add no-fully-closed-candle regression test in src/tradegumi/tests/test_signal_engine.py"
Task: "Add insufficient indicator-window regression tests for zero and short usable indicator output in src/tradegumi/tests/test_signal_engine.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Add failing readiness tests for short and missing M5 inputs.
3. Implement readiness validation and `DataNotReady` diagnostic returns.
4. Run `pytest src/tradegumi/tests/test_signal_engine.py`.

### Incremental Delivery

1. Deliver US1 to stop raw indexing failures for normal data-not-ready inputs.
2. Deliver US2 to prove valid candidates still reach signal rule evaluation.
3. Deliver US3 to complete metrics classification and documentation.
4. Run focused quickstart validation and prepare PR.

### Notes

- Do not tune thresholds, loosen trend rules, force signal emission, or change entry criteria.
- Keep changes close to existing signal and metrics modules.
- Verify tests fail before implementation where the current code does not already cover the case.

# Tasks: Repair Signal Pipeline Diagnostics

**Input**: Design documents from `specs/006-repair-signal-diagnostics/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required by acceptance criteria. Write or update focused pytest coverage before implementation for each story.

**Organization**: Tasks are grouped by user story so each diagnostic slice can be implemented and tested independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the existing diagnostics surface and prepare focused test entry points.

- [x] T001 Confirm current branch and working tree with `C:\Program Files\Git\cmd\git.exe` in `E:\GitHub\CTI_Scripts`
- [x] T002 Review existing metric models and persistence compatibility in `src/tradegumi/strategy_metrics.py`
- [x] T003 Review existing signal-stack and candle-close diagnostic creation in `src/tradegumi/signal_engine.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared diagnostic fields and compatibility plumbing needed by all stories.

**CRITICAL**: No user story work should begin until these shared fields can round-trip through storage and export.

- [x] T004 Add additive diagnostic fields for `pipeline_state`, `near_miss_reason`, `threshold_version_unknown_reason`, criterion `diagnostic_state`, criterion `reason`, and criterion `context` in `src/tradegumi/strategy_metrics.py`
- [x] T005 Add SQLite migration and row hydration support for the new opportunity and criterion fields in `src/tradegumi/strategy_metrics.py`
- [x] T006 [P] Add focused round-trip tests for new additive fields and JSON compatibility in `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T007 Review changed Python helpers for useful docstrings and intention-revealing names in `src/tradegumi/strategy_metrics.py` and `src/tradegumi/signal_engine.py`

**Checkpoint**: New fields persist and export without breaking existing JSON consumers.

---

## Phase 3: User Story 1 - Attribute Missing Signal Data (Priority: P1) MVP

**Goal**: Valid directional trend candidates with incomplete signal-stack inputs become indeterminate with explicit data-quality blockers.

**Independent Test**: A candidate whose trend criteria pass but signal data is missing exports as indeterminate with specific reason, blocker fields, and `signal_engine_data.blocked_signal = true`.

### Tests for User Story 1

- [x] T008 [P] [US1] Add missing `signal_engine_data` blocker assignment test in `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T009 [P] [US1] Add required missing-data `blocked_signal = true` test in `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T010 [P] [US1] Add top-blocker aggregation test for indeterminate `signal_engine_data:missing` in `src/tradegumi/tests/test_strategy_metrics.py`

### Implementation for User Story 1

- [x] T011 [US1] Add structured signal input missing reason helpers in `src/tradegumi/signal_engine.py`
- [x] T012 [US1] Update signal-stack exception diagnostics to name missing input categories and compact context in `src/tradegumi/signal_engine.py`
- [x] T013 [US1] Update indeterminate validation to populate blocker fields for data-quality outcomes in `src/tradegumi/strategy_metrics.py`
- [x] T014 [US1] Include indeterminate opportunities with blockers in top-blocker aggregation in `src/tradegumi/strategy_metrics.py`

**Checkpoint**: Missing signal data is visible at opportunity, criterion, and summary levels.

---

## Phase 4: User Story 2 - Clarify Candle Close Gate Behavior (Priority: P2)

**Goal**: Candle-close gate diagnostics explain timing, gate rule, units, and whether a candidate is waiting, failed, or passed.

**Independent Test**: Before-close and after-close candidates export distinct gate diagnostics with timing fields and do not turn ordinary open-candle waiting into near misses.

### Tests for User Story 2

- [x] T015 [P] [US2] Add candle-close before-close behavior test in `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T016 [P] [US2] Add candle-close after-close behavior test in `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T017 [P] [US2] Add near-miss classification test excluding open-candle waiting in `src/tradegumi/tests/test_strategy_metrics.py`

### Implementation for User Story 2

- [x] T018 [US2] Add candle timing diagnostic helper with current time, open time, close time, seconds until or since close, timeframe, gate rule, and units in `src/tradegumi/signal_engine.py`
- [x] T019 [US2] Update `candle_close_gate` criterion creation to use stable subreasons and context in `src/tradegumi/signal_engine.py`
- [x] T020 [US2] Update near-miss assignment rules and reason summaries in `src/tradegumi/strategy_metrics.py`
- [x] T021 [US2] Separate open-candle waiting from rejected rule failures in summary counts in `src/tradegumi/strategy_metrics.py`

**Checkpoint**: Candle-close failures are no longer opaque or automatically counted as near misses.

---

## Phase 5: User Story 3 - Make Pipeline Counts Explainable (Priority: P3)

**Goal**: The export summary shows a reconciled funnel, meaningful top blockers, near-miss reason counts, and threshold-version unknown explanations.

**Independent Test**: A mixed export with trend skip, missing signal data, candle-close waiting/failure, rule rejection, emitted signal, and indeterminate outcome has reconciled summary counts.

### Tests for User Story 3

- [x] T022 [P] [US3] Add summary funnel count test in `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T023 [P] [US3] Add near-miss reason summary count test in `src/tradegumi/tests/test_strategy_metrics.py`
- [x] T024 [P] [US3] Add threshold-version unknown handling test in `src/tradegumi/tests/test_strategy_metrics.py`

### Implementation for User Story 3

- [x] T025 [US3] Add pipeline-state classification and summary funnel aggregation in `src/tradegumi/strategy_metrics.py`
- [x] T026 [US3] Add near-miss reason aggregation and export fields in `src/tradegumi/strategy_metrics.py`
- [x] T027 [US3] Add threshold-version unknown reason aggregation in `src/tradegumi/strategy_metrics.py`
- [x] T028 [US3] Update strategy metrics documentation for all changed field meanings in `docs/strategy-metrics.md`

**Checkpoint**: The summary makes the next blocker stage obvious without inspecting every opportunity.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full feature and finish required documentation and PR hygiene.

- [x] T029 Run focused pytest validation with `python -m pytest src/tradegumi/tests/test_strategy_metrics.py`
- [x] T030 Review changed Python code for useful docstrings, intention-revealing names, and no unexplained magic values in `src/tradegumi/strategy_metrics.py` and `src/tradegumi/signal_engine.py`
- [x] T031 Verify `docs/strategy-metrics.md` defines skipped, rejected, indeterminate, near miss, candle close gate, signal engine data, blocked signal, first blocker, all blockers, and blocking layer
- [x] T032 Run quickstart validation steps from `specs/006-repair-signal-diagnostics/quickstart.md`
- [x] T033 Submit PR with DockeGumi as reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; MVP scope.
- **User Story 2 (Phase 4)**: Depends on Foundational and can proceed after or alongside US1 if merge scope is coordinated.
- **User Story 3 (Phase 5)**: Depends on Foundational and benefits from US1/US2 data but remains independently testable with synthetic opportunities.
- **Polish (Phase 6)**: Depends on selected user stories being complete.

### Parallel Opportunities

- T006 can run after T004 and T005 are sketched.
- T008, T009, and T010 can be authored together because they cover separate assertions in the same test file.
- T015, T016, and T017 can be authored together before candle-close implementation.
- T022, T023, and T024 can be authored together before aggregation implementation.

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks.
2. Complete US1 so missing signal stack data is no longer hidden.
3. Run focused tests for US1 before adding candle-close and funnel refinements.

### Incremental Delivery

1. US1 repairs indeterminate data-quality attribution.
2. US2 repairs candle-close timing and near-miss classification.
3. US3 repairs summary-level explainability and documentation.

### Notes

- Keep all changes additive for JSON compatibility.
- Do not tune thresholds, loosen trend rules, or force trades.
- Use Windows Git explicitly: `C:\Program Files\Git\cmd\git.exe`.

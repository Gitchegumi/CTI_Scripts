# Tasks: Continuation Management Events

**Input**: Design documents from `/specs/018-continuation-management/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because the specification defines independent tests and the constitution requires focused regression coverage for signal, risk, outcome, and observability behavior.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish configuration, fixture, and documentation anchors used by all lifecycle work.

- [ ] T001 Add continuation management environment defaults to `src/tradegumi/config.py`
- [ ] T002 Add continuation management default variable documentation to `.env.example`
- [ ] T003 [P] Add current-week continuation-only fixture notes for issue #100 validation in `specs/018-continuation-management/quickstart.md`
- [ ] T004 [P] Review planned Python changes for required module/function docstrings and record expectations in `specs/018-continuation-management/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core lifecycle helpers and storage normalization that all user stories depend on.

**Critical**: No user story work can begin until this phase is complete.

- [ ] T005 Add lifecycle constants, role names, and managed outcome reason constants to `src/tradegumi/journal.py`
- [ ] T006 Add lifecycle fields to journal normalization and CSV export headers in `src/tradegumi/journal.py`
- [ ] T007 Add managed trade dataclass or typed helper structures for entry, management event, and outcome values in `src/tradegumi/journal.py`
- [ ] T008 Add active managed-trade lookup by symbol and direction in `src/tradegumi/journal.py`
- [ ] T009 Add reusable R-multiple and direction-aware favorable-move helper functions in `src/tradegumi/journal.py`
- [ ] T010 [P] Add lifecycle summary dataclass fields and zero defaults to `src/tradegumi/strategy_metrics.py`
- [ ] T011 [P] Add TypeScript lifecycle field types to `dashboard/src/types/index.ts`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Open Trades Only From Pullbacks (Priority: P1) MVP

**Goal**: Pullback and high-value pullback signals can open trades; continuation signals without a qualifying pullback do not create standalone trade entries.

**Independent Test**: Process mixed and continuation-only signal sequences, then confirm only pullback-originated signals create open trade entries.

### Tests for User Story 1

- [ ] T012 [P] [US1] Add journal tests for pullback-created trade entries and continuation-only non-entry evidence in `src/tradegumi/tests/test_journal.py`
- [ ] T013 [P] [US1] Add signal engine regression tests proving continuation detection is preserved while entry creation is blocked without active pullback state in `src/tradegumi/tests/test_signal_engine.py`
- [ ] T014 [P] [US1] Add metrics regression test for the 92-row issue sample and 101-row current-week continuation-only sample producing zero pullback entries in `src/tradegumi/tests/test_strategy_metrics.py`

### Implementation for User Story 1

- [ ] T015 [US1] Initialize `trade_id`, `entry_signal_id`, `entry_signal_type`, `current_stop_loss`, `current_take_profit`, `risk_at_entry`, and `lifecycle_role=entry` for pullback entries in `src/tradegumi/journal.py`
- [ ] T016 [US1] Prevent duplicate active same-symbol same-direction pullback entries in `src/tradegumi/journal.py`
- [ ] T017 [US1] Route continuation signals with no active same-direction pullback trade to non-entry lifecycle evidence in `src/tradegumi/journal.py`
- [ ] T018 [US1] Update signal alert/journal call path to use lifecycle-aware append behavior in `src/tradegumi/alerts.py`
- [ ] T019 [US1] Ensure signal engine continuation generation remains available for management routing in `src/tradegumi/signal_engine.py`
- [ ] T020 [US1] Preserve legacy continuation records as readable non-managed signal evidence in `src/tradegumi/journal.py`

**Checkpoint**: User Story 1 is functional and independently testable.

---

## Phase 4: User Story 2 - Manage Active Trades With Continuations (Priority: P2)

**Goal**: Same-direction continuation signals become accepted or rejected management events linked to active pullback-originated trades.

**Independent Test**: Open a pullback trade, apply continuation events at several favorable-move levels, and verify SL/TP updates or rejection reasons.

### Tests for User Story 2

- [ ] T021 [P] [US2] Add same-direction continuation management acceptance tests for break-even, profit-protect, and TP extension rules in `src/tradegumi/tests/test_journal.py`
- [ ] T022 [P] [US2] Add rejection tests for insufficient favorable movement, risk-increasing SL changes, extension caps, disabled management, and duplicate event replay in `src/tradegumi/tests/test_journal.py`
- [ ] T023 [P] [US2] Add opposite-direction continuation warning tests in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 2

- [ ] T024 [US2] Implement continuation management event creation with `management_event_id`, `source_signal_id`, accepted flag, and rejection reason in `src/tradegumi/journal.py`
- [ ] T025 [US2] Implement break-even SL movement from configured R threshold in `src/tradegumi/journal.py`
- [ ] T026 [US2] Implement profit-protect SL tightening from configured R threshold and offset in `src/tradegumi/journal.py`
- [ ] T027 [US2] Implement capped TP extension from configured multiple, max extension count, and max target R in `src/tradegumi/journal.py`
- [ ] T028 [US2] Implement management rejection reasons for no active trade, insufficient progress, risk increase, duplicate event, and cap reached in `src/tradegumi/journal.py`
- [ ] T029 [US2] Implement opposite-direction continuation warning persistence without opening a trade in `src/tradegumi/journal.py`
- [ ] T030 [US2] Preserve useful continuation management evidence when prime-entry suppression would otherwise hide duplicate entry alerts in `src/tradegumi/journal.py`

**Checkpoint**: User Stories 1 and 2 are functional and independently testable.

---

## Phase 5: User Story 3 - Account For Managed Outcomes Correctly (Priority: P3)

**Goal**: Final managed trade outcomes classify TP, loss stop, break-even stop, profit-protected stop, and manual closes from actual managed SL/TP state.

**Independent Test**: Apply managed SL/TP updates, close trades through each outcome path, and verify result category and captured R.

### Tests for User Story 3

- [ ] T031 [P] [US3] Add managed TP, SL loss, break-even SL, and profit-protected SL outcome tests for BUY and SELL trades in `src/tradegumi/tests/test_signal_outcomes.py`
- [ ] T032 [P] [US3] Add manual close profit and manual close loss classification tests in `src/tradegumi/tests/test_journal.py`
- [ ] T033 [P] [US3] Add captured R and managed-versus-original result comparison tests in `src/tradegumi/tests/test_strategy_metrics.py`

### Implementation for User Story 3

- [ ] T034 [US3] Add direction-aware managed exit classification helper in `src/tradegumi/signal_outcomes.py`
- [ ] T035 [US3] Update outcome application to use `current_stop_loss` and `current_take_profit` for managed trades in `src/tradegumi/signal_outcomes.py`
- [ ] T036 [US3] Persist `managed_exit_reason`, `managed_result_category`, `captured_r`, and close fields on managed trade closure in `src/tradegumi/journal.py`
- [ ] T037 [US3] Update manual grade and manual close paths to classify profit or loss relative to entry and direction in `src/tradegumi/journal.py`
- [ ] T038 [US3] Preserve legacy grade and outcome behavior for unmanaged records in `src/tradegumi/signal_outcomes.py`

**Checkpoint**: User Stories 1, 2, and 3 are functional and independently testable.

---

## Phase 6: User Story 4 - Report Lifecycle Metrics Separately (Priority: P4)

**Goal**: Journal exports, strategy metrics exports, and dashboards distinguish entry events, management events, warnings, and managed outcomes.

**Independent Test**: Export a mixed lifecycle sample and confirm lifecycle rows, counters, accepted/rejected management counts, and managed outcomes are separately visible.

### Tests for User Story 4

- [ ] T039 [P] [US4] Add Signal Journal CSV export tests for lifecycle fields and legacy blank-field compatibility in `src/tradegumi/tests/test_journal.py`
- [ ] T040 [P] [US4] Add strategy metrics summary tests for all managed lifecycle counters in `src/tradegumi/tests/test_strategy_metrics.py`
- [ ] T041 [P] [US4] Add dashboard type/build validation coverage for managed lifecycle fields in `dashboard/src/types/index.ts`

### Implementation for User Story 4

- [ ] T042 [US4] Aggregate pullback entries, continuation management observed, accepted, rejected, TP extensions, SL tightenings, break-even moves, profit-protected wins, opposite-direction warnings, average R captured, MFE, and managed-vs-original deltas in `src/tradegumi/strategy_metrics.py`
- [ ] T043 [US4] Include lifecycle identifiers and managed result fields in strategy metrics opportunity export rows in `src/tradegumi/strategy_metrics.py`
- [ ] T044 [US4] Display lifecycle role, management status, old/new SL/TP values, and managed outcomes in `dashboard/src/app/journal/page.tsx`
- [ ] T045 [US4] Display managed lifecycle counters and managed-vs-original comparison in `dashboard/src/app/strategy-metrics/page.tsx`
- [ ] T046 [US4] Ensure journal and metrics API responses remain backward compatible for blank legacy lifecycle fields in `src/tradegumi/api_server.py`

**Checkpoint**: All user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation, documentation, code quality, and release readiness across all stories.

- [ ] T047 [P] Update managed lifecycle documentation in `docs/signal-journal.md`
- [ ] T048 [P] Update validation notes and manual replay scenarios in `specs/018-continuation-management/quickstart.md`
- [ ] T049 Review changed Python code for intention-revealing names, simple control flow, no unexplained magic values, and required docstrings in `src/tradegumi/`
- [ ] T050 Run focused Python validation from quickstart in `src/tradegumi/tests/`
- [ ] T051 Run full Python regression validation in `src/tradegumi/tests/`
- [ ] T052 Run dashboard lint and build checks in `dashboard/`
- [ ] T053 Confirm continuation-only exports from issue #100 and current-week sample create zero trade entries using `specs/018-continuation-management/quickstart.md`
- [ ] T054 Ask the user to identify the PR reviewer before opening the PR, then submit the PR with that reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and benefits from US1 entry state.
- **User Story 3 (Phase 5)**: Depends on managed trade state from US1 and management state from US2.
- **User Story 4 (Phase 6)**: Depends on lifecycle fields from US1-US3.
- **Polish (Phase 7)**: Depends on all desired story phases.

### User Story Dependencies

- **US1 Open Trades Only From Pullbacks**: Required MVP and prerequisite for meaningful management.
- **US2 Manage Active Trades With Continuations**: Requires active pullback trade state from US1.
- **US3 Account For Managed Outcomes Correctly**: Requires managed SL/TP state from US2.
- **US4 Report Lifecycle Metrics Separately**: Requires lifecycle data from US1-US3.

### Parallel Opportunities

- T003 and T004 can run in parallel with other setup tasks after configuration names are chosen.
- T010 and T011 can run in parallel with journal foundational work.
- US1 tests T012-T014 can be written in parallel.
- US2 tests T021-T023 can be written in parallel after foundational helpers exist.
- US3 tests T031-T033 can be written in parallel.
- US4 tests T039-T041 can be written in parallel.
- Dashboard work T044-T045 can proceed after backend field names are stable.
- Documentation tasks T047-T048 can run in parallel with final validation.

---

## Parallel Example: User Story 1

```text
Task: "T012 [P] [US1] Add journal tests for pullback-created trade entries and continuation-only non-entry evidence in src/tradegumi/tests/test_journal.py"
Task: "T013 [P] [US1] Add signal engine regression tests proving continuation detection is preserved while entry creation is blocked without active pullback state in src/tradegumi/tests/test_signal_engine.py"
Task: "T014 [P] [US1] Add metrics regression test for the 92-row issue sample and 101-row current-week continuation-only sample producing zero pullback entries in src/tradegumi/tests/test_strategy_metrics.py"
```

## Parallel Example: User Story 2

```text
Task: "T021 [P] [US2] Add same-direction continuation management acceptance tests for break-even, profit-protect, and TP extension rules in src/tradegumi/tests/test_journal.py"
Task: "T022 [P] [US2] Add rejection tests for insufficient favorable movement, risk-increasing SL changes, extension caps, disabled management, and duplicate event replay in src/tradegumi/tests/test_journal.py"
Task: "T023 [P] [US2] Add opposite-direction continuation warning tests in src/tradegumi/tests/test_journal.py"
```

## Parallel Example: User Story 3

```text
Task: "T031 [P] [US3] Add managed TP, SL loss, break-even SL, and profit-protected SL outcome tests for BUY and SELL trades in src/tradegumi/tests/test_signal_outcomes.py"
Task: "T032 [P] [US3] Add manual close profit and manual close loss classification tests in src/tradegumi/tests/test_journal.py"
Task: "T033 [P] [US3] Add captured R and managed-versus-original result comparison tests in src/tradegumi/tests/test_strategy_metrics.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for User Story 1.
3. Validate that continuation-only samples create zero trade entries.
4. Stop and review journal/export behavior before applying management rules.

### Incremental Delivery

1. Add US1 to stop continuation entry noise.
2. Add US2 to use continuation as management evidence.
3. Add US3 to classify managed exits correctly.
4. Add US4 to expose the lifecycle in metrics, exports, and dashboard.

### Quality Gates

- Tests should be written first for each user story and fail before implementation.
- Preserve broker abstraction and risk checks throughout.
- Keep all new thresholds configuration-driven.
- Verify legacy journal and metrics records remain readable.
- Ask for the PR reviewer before opening the PR.

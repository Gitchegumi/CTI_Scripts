# Tasks: Repair DB-backed page performance and restore signal pipeline progression

**Input**: Design documents from `specs/007-repair-db-signals/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md  
**Tests**: Required by the specification for query behavior/response correctness where practical and signal pipeline regression coverage.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or has no dependency on incomplete tasks.
- **[Story]**: Maps to User Story 1, 2, or 3 from `spec.md`.
- Every task includes exact file paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish baseline context and measurement targets before implementation.

- [x] T001 Read `specs/007-repair-db-signals/spec.md`, `specs/007-repair-db-signals/plan.md`, `specs/007-repair-db-signals/research.md`, and `specs/007-repair-db-signals/contracts/`
- [x] T002 [P] Capture current backend test command behavior from `src/pyproject.toml` and existing tests in `src/tradegumi/tests/`
- [x] T003 [P] Capture current dashboard validation command behavior from `dashboard/package.json`
- [x] T004 [P] Review Python docstring requirements from `.specify/memory/constitution.md` before modifying backend helpers

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Identify the concrete slow paths and signal flow before changing behavior.

**CRITICAL**: No user story implementation should begin until this phase is complete.

- [x] T005 Inspect DB-backed dashboard route handlers in `dashboard/src/app/api/strategy-metrics/`, `dashboard/src/app/api/journal/`, `dashboard/src/app/api/manual-trades/`, and `dashboard/src/app/api/trades/history/route.ts`
- [x] T006 Inspect DB-backed dashboard pages/components in `dashboard/src/app/strategy-metrics/page.tsx`, `dashboard/src/app/journal/page.tsx`, `dashboard/src/app/manual-trades/page.tsx`, `dashboard/src/components/TradeHistory.tsx`, `dashboard/src/hooks/useData.ts`, and `dashboard/src/lib/api.ts`
- [x] T007 Inspect backend persistence/query modules in `src/tradegumi/database.py`, `src/tradegumi/strategy_metrics.py`, `src/tradegumi/journal.py`, and `src/tradegumi/manual_trades.py`
- [x] T008 Inspect signal progression modules in `src/tradegumi/signal_engine.py`, `src/tradegumi/signal_processor.py`, `src/tradegumi/decision_engine.py`, `src/tradegumi/indicators.py`, and `src/tradegumi/strategy_metrics.py`
- [x] T009 Search for diagnostic spelling mismatches `signal_engine_data` and `singal_engine_data` across `src/`, `dashboard/`, and `docs/`
- [x] T010 Record baseline slow endpoints/pages and signal blockage findings in `specs/007-repair-db-signals/analysis.md`

**Checkpoint**: Foundation ready. Slow paths, affected modules, and signal blockage hypotheses are documented before code edits.

---

## Phase 3: User Story 1 - Fast DB-backed operator pages (Priority: P1) MVP

**Goal**: DB-backed pages load quickly under normal local/dev data volume without user-facing behavior drift.

**Independent Test**: Load strategy metrics, signal journal, manual trade journal, and dashboard trade history with representative data and confirm the same visible information appears without a 5+ second wait.

### Tests for User Story 1

- [x] T011 [P] [US1] Add or update backend query/response correctness tests for strategy metrics in `src/tradegumi/tests/test_strategy_metrics.py`
- [ ] T012 [P] [US1] Add or update backend query/response correctness tests for manual trades in `src/tradegumi/tests/test_manual_trades.py`
- [ ] T013 [P] [US1] Add or update backend query/response correctness tests for journal reads in `src/tradegumi/tests/test_journal.py`
- [ ] T014 [P] [US1] Add or update database schema/index behavior tests in `tests/tradegumi/test_database.py`

### Implementation for User Story 1

- [ ] T015 [US1] Add lightweight timing around confirmed slow backend read paths in `src/tradegumi/strategy_metrics.py`, `src/tradegumi/journal.py`, `src/tradegumi/manual_trades.py`, or `src/tradegumi/database.py`
- [x] T016 [US1] Add idempotent SQLite index setup for confirmed slow filters/orderings in `src/tradegumi/database.py` and related module schema setup
- [x] T017 [US1] Optimize strategy metrics summary/opportunities/export query paths in `src/tradegumi/strategy_metrics.py`
- [ ] T018 [US1] Optimize signal journal default reads/export paths in `src/tradegumi/journal.py`
- [ ] T019 [US1] Optimize manual trade history/stats query paths in `src/tradegumi/manual_trades.py`
- [x] T020 [US1] Reduce duplicate or waterfall strategy metrics fetches in `dashboard/src/app/strategy-metrics/page.tsx` and `dashboard/src/app/api/strategy-metrics/`
- [ ] T021 [US1] Reduce duplicate or waterfall signal journal fetches in `dashboard/src/app/journal/page.tsx` and `dashboard/src/app/api/journal/route.ts`
- [ ] T022 [US1] Reduce duplicate or waterfall manual trade fetches in `dashboard/src/app/manual-trades/page.tsx` and `dashboard/src/app/api/manual-trades/`
- [ ] T023 [US1] Bound or optimize dashboard trade history loading in `dashboard/src/components/TradeHistory.tsx` and `dashboard/src/app/api/trades/history/route.ts`
- [x] T024 [US1] Verify optimized DB-backed routes preserve response shape against tests and manual route inspection

**Checkpoint**: User Story 1 is independently functional and measurable.

---

## Phase 4: User Story 2 - Valid trend candidates reach signal evaluation (Priority: P1)

**Goal**: A trend-valid candidate with complete signal data and a fully closed M5 candle reaches signal rule evaluation.

**Independent Test**: Run signal-pipeline tests covering insufficient candles, exactly enough candles, last closed candle selection, M5 gate boundaries, and full trend-valid progression.

### Tests for User Story 2

- [x] T025 [P] [US2] Add insufficient-candles signal engine data regression test in `src/tradegumi/tests/test_signal_engine.py`
- [x] T026 [P] [US2] Add exactly-enough-candles signal engine data regression test in `src/tradegumi/tests/test_signal_engine.py`
- [x] T027 [P] [US2] Add last-closed-candle selection regression test in `src/tradegumi/tests/test_signal_engine.py`
- [x] T028 [P] [US2] Add M5 candle close before/exact/after boundary tests in `src/tradegumi/tests/test_signal_engine.py`
- [ ] T029 [P] [US2] Add full trend-valid candidate reaches signal rules test in `src/tradegumi/tests/test_signal_pipeline.py`

### Implementation for User Story 2

- [x] T030 [US2] Add explicit signal data sufficiency guards and docstrings in `src/tradegumi/signal_engine.py`
- [x] T031 [US2] Implement deterministic timezone-aware last closed candle/window selection helper in `src/tradegumi/signal_engine.py`
- [x] T032 [US2] Implement deterministic M5 candle-close gate helper in `src/tradegumi/signal_engine.py`
- [x] T033 [US2] Update signal data preparation to return complete/missing diagnostic states without `IndexError` in `src/tradegumi/signal_engine.py`
- [ ] T034 [US2] Update pre-close gate handling so waiting candidates remain eligible for later evaluation in `src/tradegumi/signal_engine.py` and orchestration call sites
- [ ] T035 [US2] Ensure trend-valid candidates flow into signal rule evaluation when data is complete and gate passes in `src/tradegumi/signal_processor.py` or `src/tradegumi/decision_engine.py`
- [x] T036 [US2] Verify strategy thresholds and rule parameters are unchanged in `src/tradegumi/signal_engine.py`

**Checkpoint**: User Story 2 is independently functional and regression-covered.

---

## Phase 5: User Story 3 - Actionable diagnostics and measurement (Priority: P2)

**Goal**: Maintainers can see where DB latency and signal blockage occur without diagnostics breaking the pipeline.

**Independent Test**: Follow documented local measurement steps and review metrics output for accurate stage, gate, missing-data, and rule-evaluation counts.

### Tests for User Story 3

- [x] T037 [P] [US3] Add diagnostics normalization tests for `signal_engine_data` and `singal_engine_data` in `src/tradegumi/tests/test_strategy_metrics.py`
- [ ] T038 [P] [US3] Add diagnostics-do-not-break-pipeline regression test in `src/tradegumi/tests/test_strategy_metrics.py` or `src/tradegumi/tests/test_signal_pipeline.py`
- [ ] T039 [P] [US3] Add metrics summary regression test for nonzero `signal_rules_evaluated` when valid closed-candle candidates exist in `src/tradegumi/tests/test_strategy_metrics.py`

### Implementation for User Story 3

- [x] T040 [US3] Normalize diagnostic naming for `signal_engine_data` compatibility in `src/tradegumi/strategy_metrics.py`
- [x] T041 [US3] Improve missing data, candle gate, and rule evaluation diagnostics in `src/tradegumi/strategy_metrics.py`
- [ ] T042 [US3] Ensure diagnostics recording failures cannot abort signal progression in `src/tradegumi/strategy_metrics.py` without broad error masking
- [x] T043 [US3] Document performance measurement steps and before/after observations in `specs/007-repair-db-signals/quickstart.md`
- [ ] T044 [US3] Update operator-facing diagnostic documentation in `docs/strategy-metrics.md` and `docs/signal-journal.md`

**Checkpoint**: User Story 3 is independently functional and diagnostic output is actionable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, cleanup, and delivery.

- [x] T045 [P] Run backend focused tests from `src/` for modified modules
- [ ] T046 [P] Run root database tests in `tests/tradegumi/test_database.py`
- [x] T047 [P] Run dashboard lint/build commands from `dashboard/` if dashboard files changed
- [x] T048 Review changed Python code for intention-revealing names, simple control flow, no unexplained magic values, and required docstrings
- [x] T049 Verify `specs/007-repair-db-signals/analysis.md` documents root causes, slowest paths, and codebase analysis findings
- [x] T050 Verify `specs/007-repair-db-signals/quickstart.md` documents how to reproduce performance measurements locally
- [x] T051 Submit PR with DockeGumi as reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all implementation.
- **US1 Performance (Phase 3)**: Depends on Foundational.
- **US2 Signal Pipeline (Phase 4)**: Depends on Foundational and can run in parallel with US1 after analysis if files do not overlap unexpectedly.
- **US3 Diagnostics (Phase 5)**: Depends on Foundational and should integrate after or alongside US2 because diagnostics overlap signal metrics.
- **Polish (Phase 6)**: Depends on selected user stories being complete.

### User Story Dependencies

- **US1**: Independent performance increment after Foundational.
- **US2**: Independent signal correctness increment after Foundational.
- **US3**: Builds on diagnostic findings and may depend on US2 for final metrics expectations.

### Parallel Opportunities

- T002, T003, and T004 can run in parallel.
- T011 through T014 can be prepared in parallel because they target different test files.
- T025 through T029 can be prepared in parallel but converge on signal helper APIs.
- T037 through T039 can be prepared in parallel.
- T045 through T047 can run in parallel after implementation.

---

## Parallel Example: User Story 1

```text
Task: "Add or update backend query/response correctness tests for strategy metrics in src/tradegumi/tests/test_strategy_metrics.py"
Task: "Add or update backend query/response correctness tests for manual trades in src/tradegumi/tests/test_manual_trades.py"
Task: "Add or update backend query/response correctness tests for journal reads in src/tradegumi/tests/test_journal.py"
Task: "Add or update database schema/index behavior tests in tests/tradegumi/test_database.py"
```

## Parallel Example: User Story 2

```text
Task: "Add insufficient-candles signal engine data regression test in src/tradegumi/tests/test_signal_engine.py"
Task: "Add last-closed-candle selection regression test in src/tradegumi/tests/test_signal_engine.py"
Task: "Add full trend-valid candidate reaches signal rules test in src/tradegumi/tests/test_signal_pipeline.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational analysis.
2. Complete US1 performance repair because slow pages block operator use.
3. Stop and validate DB-backed page timings and response correctness.

### Signal Repair Increment

1. Complete US2 tests first and confirm they fail against the current bug.
2. Implement signal data sufficiency, last closed candle, and gate helpers.
3. Validate full trend-valid candidate progression without threshold changes.

### Diagnostics Increment

1. Normalize diagnostic naming.
2. Keep missing-data and waiting states accurate.
3. Confirm metrics can report signal-rule evaluation when valid closed-candle candidates exist.

### Delivery

1. Run focused backend and dashboard validation.
2. Update measurement docs and final analysis.
3. Submit PR with DockeGumi as reviewer.

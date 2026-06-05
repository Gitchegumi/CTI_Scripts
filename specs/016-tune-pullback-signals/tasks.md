# Tasks: Tune Pullback Signal Alerts

**Input**: Design documents from `specs/016-tune-pullback-signals/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required by FR-023. Write or update tests before implementation tasks in each user-story phase and verify they fail for the intended missing behavior.

**Organization**: Tasks are grouped by user story to enable independently testable increments.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks.
- **[Story]**: User-story label for story phases only.
- All tasks include exact repository paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the active feature context and baseline surfaces before changing signal behavior.

- [X] T001 Verify the active feature pointer, branch context, and attached baseline data references in `.specify/feature.json`, `AGENTS.md`, and `specs/016-tune-pullback-signals/plan.md`
- [X] T002 Review current pullback helper, strategy version, and diagnostic behavior in `src/tradegumi/signal_engine.py`
- [X] T003 [P] Review current strategy metrics summary, near-miss, and prime-suppression behavior in `src/tradegumi/strategy_metrics.py`
- [X] T004 [P] Review current Signal Journal pullback export and Discord payload fields in `src/tradegumi/journal.py` and `src/tradegumi/alerts.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared configuration and contract test coverage that all pullback tuning stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Add config tests for pullback trigger shape settings, Stoch memory bars, MACD hard-block mode, and threshold-version changes in `src/tradegumi/tests/test_strategy_metrics.py`
- [X] T006 Add `PULLBACK_TRIGGER_MAX_BODY_RANGE_RATIO`, `PULLBACK_TRIGGER_MIN_REJECTION_WICK_RANGE_RATIO`, `PULLBACK_TRIGGER_MIN_REJECTION_WICK_BODY_RATIO`, `PULLBACK_STOCH_MEMORY_BARS`, and `PULLBACK_MACD_HARD_BLOCK_ENABLED` in `src/tradegumi/config.py`
- [X] T007 Document new pullback tuning environment variables with conservative defaults in `.env.example`
- [X] T008 Include every new signal-affecting pullback setting in threshold-version hashing in `src/tradegumi/signal_engine.py`
- [X] T009 Run the config and threshold-version test selection in `src/tradegumi/tests/test_strategy_metrics.py`
- [X] T010 Capture the June 1-5 baseline counts from `C:/Users/User/Downloads/tradegumi 20260605/strategy-metrics-2026-06-01-to-2026-06-05.json` and `C:/Users/User/Downloads/tradegumi 20260605/signal-journal-all-2026-06-05.csv` in `specs/016-tune-pullback-signals/quickstart.md`

**Checkpoint**: Foundation ready; user story implementation can now begin.

---

## Phase 3: User Story 1 - Valid Pullbacks Become Alerts (Priority: P1) MVP

**Goal**: Valid BUY and SELL pullbacks emit `CTI-v1.2-pullback` alerts, journal rows, and operator-visible signal identity before continuation confirmation is required.

**Independent Test**: Replay or fixture valid long and short pullback setups and confirm emitted signals are pullback alerts with journal rows and distinct strategy/signal type.

### Tests for User Story 1

- [X] T011 [US1] Add valid BUY pullback fixture test with lower-wick rejection, value-area pullback, exhaustion evidence, and emitted `CTI-v1.2-pullback` signal in `src/tradegumi/tests/test_signal_engine.py`
- [X] T012 [US1] Add valid SELL pullback fixture test with upper-wick rejection, value-area pullback, exhaustion evidence, and emitted `CTI-v1.2-pullback` signal in `src/tradegumi/tests/test_signal_engine.py`
- [X] T013 [P] [US1] Add Signal Journal export test proving emitted pullback alerts create `signal_type=pullback` rows in `src/tradegumi/tests/test_journal.py`
- [X] T014 [P] [US1] Create operator alert payload test proving pullback strategy and signal type remain visible in `src/tradegumi/tests/test_alerts.py`

### Implementation for User Story 1

- [X] T015 [US1] Update pullback signal emission to preserve `CTI-v1.2-pullback`, `signal_type=pullback`, trigger context, and bridge status in `src/tradegumi/signal_engine.py`
- [X] T016 [US1] Ensure Signal Journal append and export paths retain emitted pullback identity and trigger fields in `src/tradegumi/journal.py`
- [X] T017 [US1] Ensure Discord/operator alert payloads preserve pullback signal type and strategy identity in `src/tradegumi/alerts.py`
- [X] T018 [US1] Run the US1 test selection in `src/tradegumi/tests/test_signal_engine.py`, `src/tradegumi/tests/test_journal.py`, and `src/tradegumi/tests/test_alerts.py`

**Checkpoint**: US1 is independently functional when valid BUY/SELL pullbacks emit and journal as pullbacks.

---

## Phase 4: User Story 2 - Pullback Gates Are Tuned Conservatively (Priority: P1)

**Goal**: Trigger candle, value-area sequence, Stoch RSI exhaustion, and optional MACD hard-block behavior accept realistic pullbacks while rejecting weak setups.

**Independent Test**: Controlled pass/fail fixtures prove shape, value-area, exhaustion, and MACD behavior without relying on production data.

### Tests for User Story 2

- [X] T019 [US2] Add pullback trigger shape tests for body-to-range, rejection wick, wrong wick direction, and generic pattern rejection in `src/tradegumi/tests/test_signal_engine.py`
- [X] T020 [US2] Add Keltner value-area tests for prior outer-band break, normalized tolerance, no exact-touch requirement, and missing prior-break rejection in `src/tradegumi/tests/test_signal_engine.py`
- [X] T021 [US2] Add Stoch RSI exhaustion memory tests for BUY recovery, SELL roll-down, stale exhaustion rejection, and configured memory bars in `src/tradegumi/tests/test_signal_engine.py`
- [X] T022 [US2] Add MACD soft-default and explicit hard-block tests for pullback entries in `src/tradegumi/tests/test_signal_engine.py`

### Implementation for User Story 2

- [X] T023 [US2] Implement candle body/range and rejection-wick calculations for pullback trigger evaluation in `src/tradegumi/signal_engine.py`
- [X] T024 [US2] Update `_pullback_trigger` diagnostics to include trigger context fields from `contracts/signal-diagnostics.md` in `src/tradegumi/signal_engine.py`
- [X] T025 [US2] Update `_pullback_keltner_sequence` to expose normalized value-area tolerance components and distance context in `src/tradegumi/signal_engine.py`
- [X] T026 [US2] Update `_pullback_stoch_rsi` to use configurable exhaustion memory bars and expose recovery or roll-down context in `src/tradegumi/signal_engine.py`
- [X] T027 [US2] Implement optional `PULLBACK_MACD_HARD_BLOCK_ENABLED` behavior while keeping MACD soft by default in `src/tradegumi/signal_engine.py`
- [X] T028 [US2] Run the US2 signal-engine test selection in `src/tradegumi/tests/test_signal_engine.py`

**Checkpoint**: US2 is independently functional when tuned gates pass realistic pullbacks and reject invalid fixtures with stable blockers.

---

## Phase 5: User Story 3 - Pullback Diagnostics Explain Outcomes (Priority: P2)

**Goal**: Metrics and exports quantify pullback candidates evaluated, rejected, near-missed, emitted, journaled, and prime-suppressed.

**Independent Test**: Mixed pass/fail/suppression fixtures produce complete pullback counts and stable blocker names in metrics and exports.

### Tests for User Story 3

- [X] T029 [US3] Add metrics summary tests for pullback evaluated, rejected-by-gate, near-miss, emitted, journaled, and prime-suppressed counts using the attached June 1-5 baseline shape in `src/tradegumi/tests/test_strategy_metrics.py`
- [X] T030 [US3] Add opportunity-row tests for pullback criterion context fields, threshold version, strategy, signal type, and first blocker names in `src/tradegumi/tests/test_strategy_metrics.py`
- [X] T031 [P] [US3] Add Signal Journal export tests for journaled pullback rows and prime-suppressed pullback visibility in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 3

- [X] T032 [US3] Add or verify pullback-specific aggregate counts and blocker grouping in `src/tradegumi/strategy_metrics.py`
- [X] T033 [US3] Preserve pullback diagnostic context fields when persisting evaluated opportunities and criterion rows in `src/tradegumi/strategy_metrics.py`
- [X] T034 [US3] Ensure journaled and prime-suppressed pullback counts can be correlated from journal fields in `src/tradegumi/journal.py`
- [X] T035 [US3] Run the US3 metrics and journal test selection in `src/tradegumi/tests/test_strategy_metrics.py` and `src/tradegumi/tests/test_journal.py`

**Checkpoint**: US3 is independently functional when reports explain pullback outcomes without reading raw logs.

---

## Phase 6: User Story 4 - Existing Strategy Protections Remain Intact (Priority: P2)

**Goal**: Pullback tuning preserves trend context, structure protection, prime-signal controls, and continuation behavior.

**Independent Test**: Continuation regressions, invalid pullback structure cases, and prime-suppression cases still produce expected outcomes alongside tuned pullback behavior.

### Tests for User Story 4

- [X] T036 [US4] Add continuation regression tests proving continuation strategy and `signal_type=continuation` remain distinct in `src/tradegumi/tests/test_signal_engine.py`
- [X] T037 [US4] Add pullback protection tests for missing larger-trend context and broken higher-low/lower-high structure in `src/tradegumi/tests/test_signal_engine.py`
- [X] T038 [P] [US4] Add prime-suppression regression tests proving suppressed pullbacks are counted separately from gate failures in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 4

- [X] T039 [US4] Preserve larger-trend bridge and structure rejection behavior while integrating tuned pullback gates in `src/tradegumi/signal_engine.py`
- [X] T040 [US4] Preserve continuation strategy labels, continuation criteria, and continuation diagnostics while integrating tuned pullback behavior in `src/tradegumi/signal_engine.py`
- [X] T041 [US4] Preserve prime-signal suppression behavior and suppression counters for pullback follow-on alerts in `src/tradegumi/journal.py`
- [X] T042 [US4] Run the US4 regression test selection in `src/tradegumi/tests/test_signal_engine.py` and `src/tradegumi/tests/test_journal.py`

**Checkpoint**: US4 is independently functional when protections still block weak or duplicate setups and continuation remains distinct.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, code quality, documentation, and PR readiness.

- [X] T043 Run full targeted validation from quickstart in `specs/016-tune-pullback-signals/quickstart.md`
- [X] T044 Review changed Python code for intention-revealing names, simple control flow, no unexplained magic values, and no broker-specific signal logic in `src/tradegumi/`
- [X] T045 Add or update docstrings for new or modified modules, public classes, public functions, public methods, and non-trivial helpers in `src/tradegumi/`
- [X] T046 [P] Update operator-facing documentation if new metric/export fields need explanation in `docs/signal-journal.md`
- [X] T047 [P] Run dashboard lint/build only if dashboard metrics types or UI changed in `dashboard/`
- [X] T048 Compare representative replay or simulation metrics against the attached June 1-5 baseline and record findings in `specs/016-tune-pullback-signals/quickstart.md`
- [X] T049 Submit PR with GitcheGumi as reviewer and use `specs/016-tune-pullback-signals/tasks.md` as the completion checklist

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational; recommended MVP.
- **US2 (Phase 4)**: Depends on Foundational and can be developed alongside US1 after shared config exists, but final validation should run after US1 signal emission paths are stable.
- **US3 (Phase 5)**: Depends on US1 emitted signal identity and US2 stable diagnostic contexts.
- **US4 (Phase 6)**: Depends on US1 and US2 behavior, then validates protections and regressions.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: MVP; no dependency on other stories after Foundational.
- **User Story 2 (P1)**: Can start after Foundational; shares `src/tradegumi/signal_engine.py` with US1, so coordinate edits.
- **User Story 3 (P2)**: Requires stable emitted signal identity and diagnostic reason/context names from US1 and US2.
- **User Story 4 (P2)**: Requires tuned pullback behavior from US1 and US2 to validate protections and continuation regression.

### Parallel Opportunities

- T003 and T004 can run in parallel during setup.
- T013 and T014 can run in parallel with signal-engine test authoring for US1 because they touch separate test files.
- T031 can run in parallel with US3 metrics tests because it touches journal tests.
- T037 can run in parallel with US4 signal-engine regression tests because it touches journal tests.
- T045 and T046 can run in parallel during polish if both are needed.

---

## Parallel Example: User Story 1

```text
Task: "T011 [US1] Add valid BUY pullback fixture test in src/tradegumi/tests/test_signal_engine.py"
Task: "T013 [P] [US1] Add Signal Journal export test in src/tradegumi/tests/test_journal.py"
Task: "T014 [P] [US1] Create operator alert payload test in src/tradegumi/tests/test_alerts.py"
```

## Parallel Example: User Story 3

```text
Task: "T029 [US3] Add metrics summary tests in src/tradegumi/tests/test_strategy_metrics.py"
Task: "T031 [P] [US3] Add Signal Journal export tests in src/tradegumi/tests/test_journal.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 to emit and journal valid pullbacks.
3. Stop and validate US1 independently with the US1 test selection.

### Incremental Delivery

1. Add shared config and threshold-version coverage.
2. Deliver US1 valid alert/journal behavior.
3. Deliver US2 conservative gate tuning and rejection coverage.
4. Deliver US3 metrics and export explanation.
5. Deliver US4 regression protections.
6. Run quickstart validation and representative replay comparison.

### Notes

- Tasks marked [P] are parallel-safe by file path.
- Story tasks include [US1], [US2], [US3], or [US4] for traceability.
- Tests should fail for the intended missing behavior before implementation.
- Commit after each task or coherent task group.

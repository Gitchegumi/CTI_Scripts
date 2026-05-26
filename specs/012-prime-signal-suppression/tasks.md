# Tasks: Prime Signal Suppression

**Input**: Design documents from `specs/012-prime-signal-suppression/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by the feature request. Write focused tests before implementation work in each user-story phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story the task serves
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the active feature context and existing integration points before implementation.

- [X] T001 Confirm `.specify/feature.json` points to `specs/012-prime-signal-suppression` and `AGENTS.md` points to `specs/012-prime-signal-suppression/plan.md`
- [X] T002 [P] Review current journal append, grade, reset, purge, and export helpers in `src/tradegumi/journal.py`
- [X] T003 [P] Review current journal dashboard grouping and card/detail rendering in `dashboard/src/app/journal/page.tsx`
- [X] T004 [P] Review current strategy metrics summary/export aggregation in `src/tradegumi/strategy_metrics.py`
- [X] T005 [P] Review current signal append caller in `src/tradegumi/alerts.py` and signal data shape in `src/tradegumi/signal_engine.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared test fixtures and prime field constants/helpers that all stories depend on.

**CRITICAL**: No user story implementation should begin until this phase is complete.

- [X] T006 [P] Extend `FakeSignal` in `src/tradegumi/tests/test_journal.py` to support SELL stop/take-profit shapes and deterministic timestamps
- [X] T007 [P] Add candle test helper objects in `src/tradegumi/tests/test_journal.py` for high/low/timestamp outcome inference scenarios
- [X] T008 Define prime field names, close reason constants, and unresolved grade helpers in `src/tradegumi/journal.py`
- [X] T009 Add Python docstrings for new shared prime helper functions in `src/tradegumi/journal.py`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Suppress Repeated Open Signals (Priority: P1) MVP

**Goal**: Repeated same-symbol signals no longer create new actionable journal rows while an unresolved prime exists.

**Independent Test**: Emit a first signal, then emit same-symbol same-direction and opposite-direction follow-on signals with no target/stop hit; verify one journal row remains and suppression counts increment.

### Tests for User Story 1

- [X] T010 [P] [US1] Add no-existing-prime creation test in `src/tradegumi/tests/test_journal.py`
- [X] T011 [P] [US1] Add existing BUY prime suppresses later BUY test in `src/tradegumi/tests/test_journal.py`
- [X] T012 [P] [US1] Add existing BUY prime suppresses later SELL test in `src/tradegumi/tests/test_journal.py`
- [X] T013 [P] [US1] Add same-symbol race/rapid append regression test in `src/tradegumi/tests/test_journal.py`
- [X] T014 [P] [US1] Add different-symbol signal bypasses active prime test in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 1

- [X] T015 [US1] Implement active unresolved prime lookup by symbol in `src/tradegumi/journal.py`
- [X] T016 [US1] Initialize prime fields for new actionable journal entries in `src/tradegumi/journal.py`
- [X] T017 [US1] Implement suppression update logic for same-symbol follow-on signals in `src/tradegumi/journal.py`
- [X] T018 [US1] Integrate prime lookup and suppression into `append_signal` under the existing journal lock in `src/tradegumi/journal.py`
- [X] T019 [US1] Ensure suppressed same-symbol signals do not create setup groups or strategy-stat opportunities in `src/tradegumi/journal.py`
- [X] T020 [US1] Run focused US1 tests with `python -m pytest src/tradegumi/tests/test_journal.py -k "prime or suppress"`

**Checkpoint**: User Story 1 is independently functional and testable.

---

## Phase 4: User Story 2 - Replace Prime After Inferred Outcome (Priority: P1)

**Goal**: A same-symbol signal can create a new actionable prime only after the old prime is inferred to have hit TP or SL.

**Independent Test**: Provide candles between prime and later signal that hit BUY/SELL target/stop and verify old prime closes while the later signal becomes prime.

### Tests for User Story 2

- [X] T021 [P] [US2] Add BUY prime inferred TP replacement test in `src/tradegumi/tests/test_journal.py`
- [X] T022 [P] [US2] Add BUY prime inferred SL replacement test in `src/tradegumi/tests/test_journal.py`
- [X] T023 [P] [US2] Add SELL prime inferred TP replacement test in `src/tradegumi/tests/test_journal.py`
- [X] T024 [P] [US2] Add SELL prime inferred SL replacement test in `src/tradegumi/tests/test_journal.py`
- [X] T025 [P] [US2] Add same-candle TP/SL ambiguous conservative SL test in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 2

- [X] T026 [US2] Add candle extraction/injection seam for prime TP/SL inference in `src/tradegumi/journal.py`
- [X] T027 [US2] Implement BUY and SELL target/stop high-low inference helper in `src/tradegumi/journal.py`
- [X] T028 [US2] Implement ambiguous same-candle conservative SL handling in `src/tradegumi/journal.py`
- [X] T029 [US2] Implement old-prime close field updates and new-prime insertion after inferred TP/SL in `src/tradegumi/journal.py`
- [X] T030 [US2] Preserve normal append behavior when prime inference cannot be evaluated safely in `src/tradegumi/journal.py`
- [X] T031 [US2] Run BUY/SELL inferred outcome tests with `python -m pytest src/tradegumi/tests/test_journal.py -k "inferred or ambiguous"`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Audit Suppression Outcomes (Priority: P2)

**Goal**: Suppression counts and inferred close evidence are visible in exports, metrics, and compact dashboard display.

**Independent Test**: Suppress signals, export the journal, view the dashboard card/detail, and verify metrics totals by symbol and close reason.

### Tests for User Story 3

- [X] T032 [P] [US3] Add export includes prime fields test in `src/tradegumi/tests/test_journal.py`
- [X] T033 [P] [US3] Add prime suppression metric aggregation tests in `src/tradegumi/tests/test_strategy_metrics.py`
- [X] T034 [P] [US3] Add dashboard suppressed count rendering test or type-safe render coverage in `dashboard/src/app/journal/page.tsx`

### Implementation for User Story 3

- [X] T035 [US3] Add prime fields to `EXPORT_FIELDS` and CSV normalization coverage in `src/tradegumi/journal.py`
- [X] T036 [US3] Add prime suppression fields to metrics summary/export models in `src/tradegumi/strategy_metrics.py`
- [X] T037 [US3] Aggregate total, by-symbol, inferred TP, inferred SL, ambiguous, and directional suppression metrics in `src/tradegumi/strategy_metrics.py`
- [X] T038 [US3] Add prime field types to `dashboard/src/types/index.ts`
- [X] T039 [US3] Add prime field properties to local `JournalEntry` type in `dashboard/src/app/journal/page.tsx`
- [X] T040 [US3] Render compact suppressed count text on journal card/detail in `dashboard/src/app/journal/page.tsx`
- [X] T041 [US3] Run focused export, metrics, and dashboard checks from `specs/012-prime-signal-suppression/quickstart.md`

**Checkpoint**: User Story 3 is independently functional and auditable.

---

## Phase 6: User Story 4 - Preserve Existing Journal Workflows (Priority: P2)

**Goal**: Manual grading, invalidation, reset, stale/expired behavior, purge, exports, setup grouping, and strategy-stat eligibility continue working with prime fields.

**Independent Test**: Exercise existing lifecycle operations on active primes and verify later same-symbol signals are not incorrectly suppressed.

### Tests for User Story 4

- [X] T042 [P] [US4] Add manual grade deactivates active prime test in `src/tradegumi/tests/test_journal.py`
- [X] T043 [P] [US4] Add manual invalidation deactivates active prime test in `src/tradegumi/tests/test_journal.py`
- [X] T044 [P] [US4] Add reset-to-pending prime state behavior test in `src/tradegumi/tests/test_journal.py`
- [X] T045 [P] [US4] Add stale/expired prime no longer suppresses test in `src/tradegumi/tests/test_journal.py`
- [X] T046 [P] [US4] Add restart recovery test for persisted active prime suppression in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 4

- [X] T047 [US4] Deactivate prime fields during manual grade and invalidation in `src/tradegumi/journal.py`
- [X] T048 [US4] Define and implement reset-to-pending prime behavior in `src/tradegumi/journal.py`
- [X] T049 [US4] Ensure stale/expired or invalid eligibility states cannot remain active primes in `src/tradegumi/journal.py`
- [X] T050 [US4] Ensure purge removes prime state without leaving external residue in `src/tradegumi/journal.py`
- [X] T051 [US4] Verify legacy records missing prime fields remain readable in `src/tradegumi/journal.py`
- [X] T052 [US4] Run full journal regression tests with `python -m pytest src/tradegumi/tests/test_journal.py`

**Checkpoint**: Existing journal workflows remain intact.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, full validation, and release hygiene.

- [X] T053 [P] Update or create `docs/signal-journal.md` with prime suppression fields and strategy-stat counting rule
- [X] T054 Review changed Python code for intention-revealing names, simple control flow, and no unexplained magic values in `src/tradegumi/journal.py` and `src/tradegumi/strategy_metrics.py`
- [X] T055 Add or update Python module, class, function, method, and non-trivial helper docstrings in `src/tradegumi/journal.py` and `src/tradegumi/strategy_metrics.py`
- [X] T056 Run backend validation with `python -m pytest src/tradegumi/tests`
- [X] T057 Run dashboard validation with `cd dashboard; npm run lint; npm run build`
- [X] T058 Run quickstart validation scenarios from `specs/012-prime-signal-suppression/quickstart.md`
- [ ] T059 Submit PR with DockeGumi as reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational; integrates naturally after US1 because replacement extends the same append decision path.
- **User Story 3 (Phase 5)**: Depends on prime fields from US1/US2.
- **User Story 4 (Phase 6)**: Depends on prime lifecycle fields from US1/US2.
- **Polish (Phase 7)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational; no dependency on other stories.
- **US2 (P1)**: Can start after Foundational, but safest after US1 because it extends active-prime handling.
- **US3 (P2)**: Depends on prime fields and suppression/closure data produced by US1/US2.
- **US4 (P2)**: Depends on prime fields and lifecycle rules produced by US1/US2.

### Parallel Opportunities

- Setup review tasks T002-T005 can run in parallel.
- Foundational test helper tasks T006-T007 can run in parallel.
- Test-writing tasks within each user story can run in parallel before implementation.
- US3 dashboard type/display work can run in parallel with metrics aggregation after prime field names stabilize.
- Documentation T053 can run in parallel with final validation once behavior and field names are stable.

## Parallel Example: User Story 1

```text
Task: "Add no-existing-prime creation test in src/tradegumi/tests/test_journal.py"
Task: "Add existing BUY prime suppresses later BUY test in src/tradegumi/tests/test_journal.py"
Task: "Add existing BUY prime suppresses later SELL test in src/tradegumi/tests/test_journal.py"
Task: "Add different-symbol signal bypasses active prime test in src/tradegumi/tests/test_journal.py"
```

## Parallel Example: User Story 3

```text
Task: "Add prime suppression metric aggregation tests in src/tradegumi/tests/test_strategy_metrics.py"
Task: "Add prime field types to dashboard/src/types/index.ts"
Task: "Add prime field properties to local JournalEntry type in dashboard/src/app/journal/page.tsx"
```

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks.
2. Complete US1 so unresolved same-symbol primes suppress repeated signals.
3. Validate US1 independently with focused journal tests.

### Incremental Delivery

1. Add US2 inferred TP/SL replacement.
2. Add US3 audit surfaces in export, metrics, and dashboard.
3. Add US4 lifecycle compatibility.
4. Run full backend and dashboard checks.

### Notes

- Preserve existing signal generation and strategy thresholds.
- Keep all journal mutation decisions under the existing journal lock.
- Do not let suppressed signals create rows, grading obligations, setup groups, or usable strategy-stat opportunities.
- Verify tests fail before implementing each tested behavior.

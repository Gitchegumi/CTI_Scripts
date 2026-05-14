# Tasks: Signal Setup Outcomes

**Input**: Design documents from `specs/011-signal-setup-outcomes/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md  
**Tests**: Required by FR-019 and quickstart validation. Story test tasks should be written before implementation tasks and verified failing first.

**Organization**: Tasks are grouped by user story so setup grouping, entry usability, stats eligibility, and normalized grades can be implemented and tested as independent increments.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or depends only on completed earlier phases
- **[Story]**: Maps task to a user story from spec.md
- Every task includes an exact repository path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare shared configuration, docs references, and baseline validation for the feature.

- [X] T001 Verify current branch and active feature point to `011-signal-setup-outcomes` in `.specify/feature.json`
- [X] T002 [P] Add `SIGNAL_SETUP_GROUP_WINDOW_MINUTES` defaulting to 10 minutes in `src/tradegumi/config.py`
- [X] T003 [P] Add valid-entry tolerance and stale-signal threshold configuration defaults in `src/tradegumi/config.py`
- [X] T004 [P] Add setup outcome field names to the export field list in `src/tradegumi/journal.py`
- [X] T005 [P] Add Signal Journal setup outcome TypeScript fields to `dashboard/src/types/index.ts`
- [X] T006 [P] Document the setup outcome field vocabulary and stats counting rule in `docs/signal-journal.md`
- [X] T007 Run the existing focused baseline tests from `src/tradegumi/tests/test_journal.py` and `src/tradegumi/tests/test_strategy_metrics.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build common outcome classification primitives used by all user stories.

**Critical**: No user story implementation should begin until this phase is complete.

- [X] T008 Create `TradeGrade` constants and allowed value validation in `src/tradegumi/journal.py`
- [X] T009 Create an `EntryMissDistance` normalization helper with absolute and ATR-normalized output in `src/tradegumi/journal.py`
- [X] T010 Create a setup outcome payload builder for new journal records in `src/tradegumi/journal.py`
- [X] T011 Add docstrings for all new setup outcome helpers in `src/tradegumi/journal.py`
- [X] T012 [P] Add reusable journal test factories for timestamped signals and legacy records in `src/tradegumi/tests/test_journal.py`
- [X] T013 [P] Add reusable strategy metrics test fixtures for eligible and excluded emitted signals in `src/tradegumi/tests/test_strategy_metrics.py`

**Checkpoint**: Shared outcome primitives are ready and user story work can proceed.

---

## Phase 3: User Story 1 - Identify Tradable Setups (Priority: P1) MVP

**Goal**: Same-symbol, same-direction, same-strategy emitted signals inside the configured grouping window share a setup group and later records are marked as duplicates.

**Independent Test**: Create multiple journaled signals inside and outside the grouping window and verify group IDs, duplicate flags, duplicate grade, and stats eligibility.

### Tests for User Story 1

- [X] T014 [US1] Add a failing test for first signal setup group creation in `src/tradegumi/tests/test_journal.py`
- [X] T015 [US1] Add a failing test for duplicate same-symbol same-direction same-strategy grouping inside the 10-minute window in `src/tradegumi/tests/test_journal.py`
- [X] T016 [US1] Add a failing test for new setup group creation at or after the grouping-window boundary in `src/tradegumi/tests/test_journal.py`
- [X] T017 [US1] Add a failing test for different strategy identities starting separate setup groups in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 1

- [X] T018 [US1] Implement active setup group lookup by symbol, direction, strategy, and signal timestamp in `src/tradegumi/journal.py`
- [X] T019 [US1] Generate stable `setup_group_id` values for first active setup records in `src/tradegumi/journal.py`
- [X] T020 [US1] Mark duplicate setup records with `is_duplicate_setup`, `trade_grade`, `usable_for_strategy_stats`, and `stats_exclusion_reason` in `src/tradegumi/journal.py`
- [X] T021 [US1] Update `append_signal` to include setup grouping fields for every new journaled signal in `src/tradegumi/journal.py`
- [X] T022 [US1] Run `python -m pytest src/tradegumi/tests/test_journal.py` for User Story 1 validation

**Checkpoint**: User Story 1 is independently functional and testable.

---

## Phase 4: User Story 2 - Classify Entry Usability at Signal Time (Priority: P1)

**Goal**: New journal records show whether entry was valid at signal time, how far price missed the suggested entry, signal age in M5 bars, and late-signal status.

**Independent Test**: Journal records within tolerance, outside tolerance, at the tolerance boundary, missing suggested entry, and without usable ATR all classify entry state consistently.

### Tests for User Story 2

- [X] T023 [US2] Add a failing test for entry-valid signals at and inside tolerance in `src/tradegumi/tests/test_journal.py`
- [X] T024 [US2] Add a failing test for late signals beyond valid entry tolerance in `src/tradegumi/tests/test_journal.py`
- [X] T025 [US2] Add a failing test for absolute and ATR-normalized `entry_miss_distance` values in `src/tradegumi/tests/test_journal.py`
- [X] T026 [US2] Add a failing test for missing or zero ATR leaving ATR-normalized distance blank in `src/tradegumi/tests/test_journal.py`
- [X] T027 [US2] Add a failing test for missing suggested entry marking `stats_exclusion_reason` as `missing_entry_context` in `src/tradegumi/tests/test_journal.py`
- [X] T028 [US2] Add a failing test for `signal_age_bars` from setup condition timing context in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 2

- [X] T029 [US2] Add signal-time price and entry tolerance inputs to the journal append path without changing signal thresholds in `src/tradegumi/alerts.py`
- [X] T030 [US2] Expose setup-condition first-true timing context from signal diagnostics without changing signal firing rules in `src/tradegumi/signal_engine.py`
- [X] T031 [US2] Calculate `entry_valid_at_signal`, `entry_miss_distance`, and `late_signal` in `src/tradegumi/journal.py`
- [X] T032 [US2] Calculate `signal_age_bars` as M5 bars since setup condition first became true in `src/tradegumi/journal.py`
- [X] T033 [US2] Classify missing entry context and entry-invalid records as excluded from strategy stats in `src/tradegumi/journal.py`
- [X] T034 [US2] Classify entry-invalid records as `MISSED_ENTRY` or `LATE_SIGNAL` with false stats eligibility in `src/tradegumi/journal.py`
- [X] T035 [US2] Run `python -m pytest src/tradegumi/tests/test_journal.py` for User Story 2 validation

**Checkpoint**: User Story 2 is independently functional and testable.

---

## Phase 5: User Story 3 - Protect Strategy Statistics (Priority: P2)

**Goal**: Strategy opportunity statistics count only records where `usable_for_strategy_stats` is true and report excluded signals separately.

**Independent Test**: Mix usable, duplicate, missed, stale, late, legacy, and manually invalidated signals, then verify opportunity counts only include eligible records.

### Tests for User Story 3

- [X] T036 [P] [US3] Add a failing metrics test for `trade_opportunity_count` counting only eligible journal records in `src/tradegumi/tests/test_strategy_metrics.py`
- [X] T037 [US3] Add a failing metrics test for `stats_excluded_count` and exclusion reason counts in `src/tradegumi/tests/test_strategy_metrics.py`
- [X] T038 [US3] Add a failing metrics test that missing legacy eligibility does not inflate trade opportunity count in `src/tradegumi/tests/test_strategy_metrics.py`
- [X] T039 [P] [US3] Add a failing journal test for stale signal stats exclusion in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 3

- [X] T040 [US3] Add additive eligibility fields or query support for strategy summary aggregation in `src/tradegumi/strategy_metrics.py`
- [X] T041 [US3] Implement the journal eligibility source-of-truth lookup used by strategy summaries in `src/tradegumi/strategy_metrics.py`
- [X] T042 [US3] Implement `trade_opportunity_count`, `stats_excluded_count`, and `stats_exclusion_counts` in `src/tradegumi/strategy_metrics.py`
- [X] T043 [US3] Ensure legacy records with missing `usable_for_strategy_stats` are reported as unknown or excluded from opportunity counts in `src/tradegumi/strategy_metrics.py`
- [X] T044 [US3] Update API summary response handling if needed for new metrics fields in `src/tradegumi/api_server.py`
- [X] T045 [US3] Update dashboard metrics or journal type handling for new stats fields in `dashboard/src/types/index.ts`
- [X] T046 [US3] Run `python -m pytest src/tradegumi/tests/test_strategy_metrics.py src/tradegumi/tests/test_journal.py` for User Story 3 validation

**Checkpoint**: User Story 3 is independently functional and testable.

---

## Phase 6: User Story 4 - Record Normalized Trade Grades (Priority: P3)

**Goal**: Every new journaled signal has exactly one normalized trade grade, and manual review/export paths preserve the allowed grade vocabulary.

**Independent Test**: Journal records across TP, SL, BE via review action, missed entry, late signal, duplicate, invalid, and pending states all use one allowed `trade_grade` value.

### Tests for User Story 4

- [X] T047 [US4] Add a failing test for allowed `trade_grade` value validation in `src/tradegumi/tests/test_journal.py`
- [X] T048 [US4] Add a failing test for `BE` trade grade acceptance and persistence in `src/tradegumi/tests/test_journal.py`
- [X] T049 [US4] Add a failing test for manual invalidation setting `trade_grade` to `INVALID` and false eligibility in `src/tradegumi/tests/test_journal.py`
- [X] T050 [US4] Add a failing test for pending reset preserving evidence and restoring `trade_grade` to `PENDING` in `src/tradegumi/tests/test_journal.py`
- [X] T051 [US4] Add a failing export test for stable setup outcome CSV columns in `src/tradegumi/tests/test_journal.py`
- [X] T052 [US4] Add API or UI invalidation validation coverage for `INVALID` trade grade behavior in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 4

- [X] T053 [US4] Map existing dashboard and Discord grade actions to normalized `trade_grade` updates in `src/tradegumi/journal.py`
- [X] T054 [US4] Map break-even review actions to `trade_grade` value `BE` in `src/tradegumi/journal.py`
- [X] T055 [US4] Add manual invalidation handling that preserves original evidence and notes in `src/tradegumi/journal.py`
- [X] T056 [US4] Add backend API handling for manual invalidation in `src/tradegumi/api_server.py`
- [X] T057 [US4] Update reset-to-pending behavior for normalized outcome fields in `src/tradegumi/journal.py`
- [X] T058 [US4] Add setup outcome fields to deterministic CSV export output in `src/tradegumi/journal.py`
- [X] T059 [US4] Render setup outcome fields, duplicate status, entry state, and normalized trade grade safely on the journal page in `dashboard/src/app/journal/page.tsx`
- [X] T060 [US4] Add dashboard manual invalidation control for journal records in `dashboard/src/app/journal/page.tsx`
- [X] T061 [US4] Add dashboard support for break-even grading in `dashboard/src/app/journal/page.tsx`
- [X] T062 [US4] Run `python -m pytest src/tradegumi/tests/test_journal.py` and dashboard checks if UI changed from `dashboard/`

**Checkpoint**: User Story 4 is independently functional and testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, code quality, and PR readiness.

- [X] T063 [P] Update `docs/signal-journal.md` with final setup grouping, entry validity, trade grade, and stats eligibility behavior
- [X] T064 [P] Update `.env.example` with the setup grouping window, entry tolerance, and stale-signal threshold configuration if environment-driven config was added
- [X] T065 Review changed Python names, constants, and control flow for intention-revealing code in `src/tradegumi/journal.py`, `src/tradegumi/strategy_metrics.py`, `src/tradegumi/alerts.py`, and `src/tradegumi/signal_engine.py`
- [X] T066 Add or revise Python module, public function, public class, method, and non-trivial helper docstrings in `src/tradegumi/journal.py`, `src/tradegumi/strategy_metrics.py`, `src/tradegumi/alerts.py`, and `src/tradegumi/signal_engine.py`
- [X] T067 Run full focused validation from `specs/011-signal-setup-outcomes/quickstart.md`
- [X] T068 Run broader Python regression tests with `python -m pytest src/tradegumi/tests`
- [X] T069 Run `npm run lint` and `npm run build` from `dashboard/` if dashboard files changed
- [ ] T070 Submit PR with DockeGumi as reviewer from repository root `E:/GitHub/CTI_Scripts`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2 and delivers the MVP.
- **Phase 4 US2**: Depends on Phase 2; can run after or alongside US1 if shared `journal.py` edits are coordinated.
- **Phase 5 US3**: Depends on Phase 2 and benefits from US1/US2 classification fields for complete behavior.
- **Phase 6 US4**: Depends on Phase 2 and can integrate after core classification behavior exists.
- **Phase 7 Polish**: Depends on selected user stories being complete.

### User Story Dependencies

- **US1 Identify Tradable Setups**: MVP; no dependency on other stories after foundation.
- **US2 Classify Entry Usability**: Independent after foundation, but shares `journal.py` with US1.
- **US3 Protect Strategy Statistics**: Can begin after foundation using fixtures, but final validation depends on US1/US2/US4 exclusions.
- **US4 Record Normalized Trade Grades**: Can begin after foundation, but duplicate and entry-invalid mappings depend on US1/US2 decisions.

### Parallel Opportunities

- Setup documentation/type tasks T005-T006 can run in parallel after config field names are agreed.
- Foundational fixture tasks T012-T013 can run in parallel.
- US2 integration tasks T029-T030 can run in parallel because they touch different files.
- US3 tests T036 and T039 can run in parallel because they touch different files.
- Documentation updates in T063-T064 can run in parallel with final validation.

---

## Coordination Note: User Story 1

```text
US1 tasks intentionally target src/tradegumi/tests/test_journal.py and src/tradegumi/journal.py, so they should be done sequentially to avoid conflicting edits.
```

## Parallel Example: User Story 2

```text
Task: "T029 [US2] Add signal-time price and entry tolerance inputs to the journal append path without changing signal thresholds in src/tradegumi/alerts.py"
Task: "T030 [US2] Expose setup-condition first-true timing context from signal diagnostics without changing signal firing rules in src/tradegumi/signal_engine.py"
```

## Parallel Example: User Story 3

```text
Task: "T036 [P] [US3] Add a failing metrics test for trade_opportunity_count counting only eligible journal records in src/tradegumi/tests/test_strategy_metrics.py"
Task: "T039 [P] [US3] Add a failing journal test for stale signal stats exclusion in src/tradegumi/tests/test_journal.py"
```

## Coordination Note: User Story 4

```text
US4 tests and implementation mostly target src/tradegumi/tests/test_journal.py, src/tradegumi/journal.py, and dashboard/src/app/journal/page.tsx, so backend and UI work should be coordinated to avoid conflicting edits.
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for User Story 1.
3. Validate setup grouping independently with `python -m pytest src/tradegumi/tests/test_journal.py`.
4. Stop for review if only duplicate setup grouping is needed first.

### Incremental Delivery

1. Deliver US1 setup grouping.
2. Add US2 entry usability and signal age.
3. Add US3 stats eligibility aggregation.
4. Add US4 normalized grade review/export support.
5. Run quickstart validation and full regression checks.

### Notes

- Keep strategy thresholds and signal firing rules unchanged.
- Treat tests as required for this feature because FR-019 explicitly requires practical coverage.
- Avoid rewriting historical journal records; support legacy reads instead.
- Commit after each story or logical group when implementation begins.

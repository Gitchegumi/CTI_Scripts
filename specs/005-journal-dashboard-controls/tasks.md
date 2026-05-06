# Tasks: Journal and Dashboard Controls

**Input**: Design documents from `specs/005-journal-dashboard-controls/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required by the feature specification. Write or update focused tests for each issue before implementation where practical.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish shared helpers and test surfaces that multiple stories will use.

- [X] T001 [P] Review current strategy metrics range parsing behavior in `src/tradegumi/strategy_metrics.py` and document observed inclusive/exclusive boundary assumptions in `docs/strategy-metrics.md`
- [X] T002 [P] Review current Signal Journal JSONL fields and malformed-line behavior in `src/tradegumi/journal.py` and `dashboard/src/app/journal/page.tsx`
- [X] T003 [P] Review current mode label usage across `dashboard/src`, `docs`, and `src/tradegumi` for user-facing "Alert Only" text
- [X] T004 [P] Review dashboard trade-history load path in `src/tradegumi/api_server.py`, `dashboard/src/app/api/trades/history/route.ts`, `dashboard/src/hooks/useData.ts`, and `dashboard/src/components/TradeHistory.tsx`
- [X] T005 [P] Create or update Signal Journal test module scaffold in `src/tradegumi/tests/test_journal.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared utilities and contracts needed by multiple user stories.

- [X] T006 Create shared date range normalization helper with docstring in `src/tradegumi/strategy_metrics.py`
- [X] T007 [P] Create shared mode display label helper in `dashboard/src/lib/api.ts`
- [X] T008 [P] Create shared Signal Journal read/write helper functions with docstrings in `src/tradegumi/journal.py`
- [X] T009 [P] Add journal proxy routing structure for non-GET actions in `dashboard/src/app/api/journal/route.ts`
- [X] T010 Add dashboard API error parsing helper reuse or equivalent behavior in `dashboard/src/lib/api.ts`
- [X] T011 Verify Python docstring coverage expectations for new/modified helpers in `src/tradegumi/strategy_metrics.py`, `src/tradegumi/journal.py`, `src/tradegumi/manual_trades.py`, and `src/tradegumi/api_server.py`

**Checkpoint**: Shared foundations are ready; user story implementation can proceed.

---

## Phase 3: User Story 1 - Review Strategy Metrics Through Selected End Date (Priority: P1)

**Goal**: Strategy Metrics includes the selected end date consistently across summary, opportunities, comparison, and export.

**Independent Test**: Seed metrics on a selected date and the following date; verify selected-day records are included and following-day records excluded.

### Tests for User Story 1

- [X] T012 [P] [US1] Add inclusive end-date summary tests in `src/tradegumi/tests/test_strategy_metrics.py`
- [X] T013 [P] [US1] Add inclusive end-date opportunities/export tests in `src/tradegumi/tests/test_strategy_metrics.py`

### Implementation for User Story 1

- [X] T014 [US1] Apply shared date range normalization to `get_summary` in `src/tradegumi/strategy_metrics.py`
- [X] T015 [US1] Apply shared date range normalization to `get_opportunities` and `export_summary` in `src/tradegumi/strategy_metrics.py`
- [X] T016 [US1] Apply matching normalized period handling to `compare_periods` in `src/tradegumi/strategy_metrics.py`
- [X] T017 [US1] Ensure Strategy Metrics UI sends date-only selections consistently from `dashboard/src/app/strategy-metrics/page.tsx`
- [X] T018 [US1] Update range semantics documentation in `docs/strategy-metrics.md`
- [X] T019 [US1] Run focused metrics tests from `src/tradegumi/tests/test_strategy_metrics.py`

**Checkpoint**: Selected End date includes the full selected day.

---

## Phase 4: User Story 7 - Restore Main Dashboard Trade History (Priority: P1)

**Goal**: Main dashboard Trade History displays manual trades and avoids repeated 500/404/hydration failures.

**Independent Test**: Create manual trades, make broker/source history unavailable, and verify `/api/trades/history?count=50` plus the dashboard still show manual trades.

### Tests for User Story 7

- [X] T020 [P] [US7] Add backend trade-history fallback test in `src/tradegumi/tests/test_manual_trades.py`
- [X] T021 [P] [US7] Add dashboard-history API error/fallback test or documented verification in `dashboard/src/app/api/trades/history/route.ts`

### Implementation for User Story 7

- [X] T022 [US7] Fix `/api/trades/history` backend path to return local manual history when source history fails in `src/tradegumi/api_server.py`
- [X] T023 [US7] Ensure source trade-history failures are logged but do not poison local manual history in `src/tradegumi/api_server.py`
- [X] T024 [US7] Handle missing trade correlation data as an intentional empty fallback in `dashboard/src/hooks/useData.ts`
- [X] T025 [US7] Update Trade History rendering to distinguish load failure from no trades in `dashboard/src/components/TradeHistory.tsx`
- [X] T026 [US7] Investigate and fix or isolate hydration-sensitive date/client-only rendering in `dashboard/src/components/TradeHistory.tsx` and `dashboard/src/app/page.tsx`
- [X] T027 [US7] Validate dashboard console has no repeated `/data/trade_correlations.json` 404, `/api/trades/history` 500, or React #418 errors per `specs/005-journal-dashboard-controls/quickstart.md`

**Checkpoint**: Dashboard Trade History is populated and console noise is resolved.

---

## Phase 5: User Story 2 - Export Signal Journal Data for Optimization (Priority: P1)

**Goal**: Signal Journal exports filtered optimization-ready CSV data.

**Independent Test**: Filter journal entries, export CSV, and verify required fields and scope.

### Tests for User Story 2

- [X] T028 [P] [US2] Add Signal Journal CSV export tests for empty, filtered, and legacy records in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 2

- [X] T029 [US2] Implement Signal Journal export helper with CSV output and docstring in `src/tradegumi/journal.py`
- [X] T030 [US2] Add backend Signal Journal export endpoint in `src/tradegumi/api_server.py`
- [X] T031 [US2] Add dashboard proxy support for Signal Journal export in `dashboard/src/app/api/journal/route.ts`
- [X] T032 [US2] Add Export CSV action respecting active grade filter in `dashboard/src/app/journal/page.tsx`
- [X] T033 [US2] Add Signal Journal export types in `dashboard/src/types/index.ts`
- [X] T034 [US2] Document Signal Journal export fields in `docs/signal-journal.md`
- [X] T035 [US2] Run focused Signal Journal export tests from `src/tradegumi/tests/test_journal.py`

**Checkpoint**: Filtered Signal Journal CSV export works independently.

---

## Phase 6: User Story 3 - Purge Stale Signal Journal Entries Safely (Priority: P1)

**Goal**: Signal Journal entries can be purged after confirmation without touching manual trade history.

**Independent Test**: Cancel purge once, confirm purge once, and verify only scoped Signal Journal entries are removed.

### Tests for User Story 3

- [X] T036 [P] [US3] Add Signal Journal purge scope and idempotency tests in `src/tradegumi/tests/test_journal.py`
- [X] T037 [P] [US3] Add manual-trade preservation test during journal purge in `src/tradegumi/tests/test_manual_trades.py`

### Implementation for User Story 3

- [X] T038 [US3] Implement scoped Signal Journal purge helper with docstring in `src/tradegumi/journal.py`
- [X] T039 [US3] Add backend Signal Journal purge endpoint in `src/tradegumi/api_server.py`
- [X] T040 [US3] Add dashboard proxy support for Signal Journal purge in `dashboard/src/app/api/journal/route.ts`
- [X] T041 [US3] Add confirmed Purge action and cleared-state refresh in `dashboard/src/app/journal/page.tsx`
- [X] T042 [US3] Document purge scope and destructive behavior in `docs/signal-journal.md`
- [X] T043 [US3] Run focused Signal Journal purge tests from `src/tradegumi/tests/test_journal.py`

**Checkpoint**: Confirmed Signal Journal purge works independently and safely.

---

## Phase 7: User Story 4 - Reset Accidentally Graded Signals to Pending (Priority: P2)

**Goal**: Graded Signal Journal entries can return to Pending while preserving signal evidence.

**Independent Test**: Grade an entry, reset it, and verify original signal data and notes remain.

### Tests for User Story 4

- [X] T044 [P] [US4] Add reset-to-pending tests for graded, pending, and legacy records in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 4

- [X] T045 [US4] Implement reset-to-pending helper with docstring in `src/tradegumi/journal.py`
- [X] T046 [US4] Add backend reset-to-pending endpoint in `src/tradegumi/api_server.py`
- [X] T047 [US4] Add dashboard proxy support for reset-to-pending in `dashboard/src/app/api/journal/route.ts`
- [X] T048 [US4] Add row-level Reset to Pending action in `dashboard/src/app/journal/page.tsx`
- [X] T049 [US4] Document reset semantics in `docs/signal-journal.md`
- [X] T050 [US4] Run focused reset-to-pending tests from `src/tradegumi/tests/test_journal.py`

**Checkpoint**: Reset to Pending works independently.

---

## Phase 8: User Story 5 - Correct Manual Trade P&L in Developing Mode (Priority: P2)

**Goal**: Developing-mode manual trade P&L corrections are accepted and reflected consistently.

**Independent Test**: Edit P&L in `alert_only`, verify saved/displayed/exported; attempt protected edit outside `alert_only`.

### Tests for User Story 5

- [X] T051 [P] [US5] Add manual P&L edit permission tests in `src/tradegumi/tests/test_manual_trades.py`
- [X] T052 [P] [US5] Add dashboard-history/export reflection tests for P&L corrections in `src/tradegumi/tests/test_manual_trades.py`

### Implementation for User Story 5

- [X] T053 [US5] Extend manual trade update normalization to accept explicit `pnl` and `pnl_percent` corrections in `src/tradegumi/manual_trades.py`
- [X] T054 [US5] Preserve demo/live protected-field rejection for P&L in `src/tradegumi/manual_trades.py`
- [X] T055 [US5] Expose P&L editing controls only in Developing mode in `dashboard/src/app/manual-trades/page.tsx`
- [X] T056 [US5] Ensure manual trade summaries, dashboard history, and exports reflect corrected P&L in `src/tradegumi/manual_trades.py`
- [X] T057 [US5] Run focused manual trade P&L tests from `src/tradegumi/tests/test_manual_trades.py`

**Checkpoint**: Developing-mode P&L correction works independently.

---

## Phase 9: User Story 6 - See Developing Label Instead of Alert Only (Priority: P3)

**Goal**: User-facing UI displays Developing while internal values stay `alert_only`.

**Independent Test**: Set mode to `alert_only`, verify UI labels show Developing and raw data compatibility remains.

### Tests for User Story 6

- [X] T058 [P] [US6] Add mode label mapping tests or documented UI verification in `dashboard/src/lib/api.ts`

### Implementation for User Story 6

- [X] T059 [US6] Add user-facing mode label mapping in `dashboard/src/lib/api.ts`
- [X] T060 [US6] Update mode labels and badges in `dashboard/src/components/SettingsPanel.tsx`
- [X] T061 [US6] Update manual trades mode copy in `dashboard/src/app/manual-trades/page.tsx`
- [X] T062 [US6] Update any remaining user-facing Alert Only labels in `dashboard/src`
- [X] T063 [US6] Update relevant documentation to explain Developing maps to internal `alert_only` in `docs/signal-journal.md` or related docs
- [X] T064 [US6] Verify existing stored `alert_only` records still load, filter, edit, and export

**Checkpoint**: Developing label is consistent without internal migration.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Verify the full feature, documentation, and release hygiene.

- [X] T065 [P] Update or create final documentation for Strategy Metrics and Signal Journal in `docs/strategy-metrics.md` and `docs/signal-journal.md`
- [X] T066 Run full focused Python test set for metrics, journal, and manual trades with `NUMBA_DISABLE_JIT=1`
- [X] T067 Run dashboard lint/typecheck or document unavailable dashboard validation command from `dashboard/package.json`
- [X] T068 Run quickstart validation steps in `specs/005-journal-dashboard-controls/quickstart.md`
- [X] T069 Review changed Python code for required module/function/helper docstrings and intention-revealing names in `src/tradegumi`
- [X] T070 Review changed UI for text overflow, hydration-sensitive rendering, and clear destructive-action confirmation in `dashboard/src`
- [X] T071 Commit completed work in logical Conventional Commits matching the implemented slices for `specs/005-journal-dashboard-controls/tasks.md`
- [X] T072 Submit PR with DockeGumi as reviewer for `specs/005-journal-dashboard-controls/tasks.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **P1 Stories**: US1, US7, US2, and US3 may proceed after Foundational. US7 should be addressed early because it affects dashboard trust.
- **P2 Stories**: US4 and US5 may proceed after Foundational; US4 depends on Signal Journal shared helpers from US2/US3 if those are already changed.
- **P3 Story**: US6 may proceed after Foundational and can run alongside backend stories because it is mostly presentation-layer.
- **Polish**: Depends on all selected stories.

### User Story Dependencies

- **US1**: Independent after T006.
- **US7**: Independent after T004 and T010.
- **US2**: Independent after T008 and T009.
- **US3**: Independent after T008 and T009.
- **US4**: Independent after T008 and T009; easiest after US2/US3 journal helpers are in place.
- **US5**: Independent after T004 and T010.
- **US6**: Independent after T007.

### Parallel Opportunities

- Setup review tasks T001-T005 can run in parallel.
- Foundational tasks T007-T010 can run in parallel after T006 is understood.
- US1 tests T012-T013 can run in parallel.
- US7 tests T020-T021 can run in parallel.
- US2/US3/US4 journal tests can be drafted in parallel if they use isolated temp journal files.
- US5 and US6 can proceed in parallel because they touch mostly different files.

---

## Parallel Example: Signal Journal Work

```text
Task: "Add Signal Journal CSV export tests in src/tradegumi/tests/test_journal.py"
Task: "Add Signal Journal purge tests in src/tradegumi/tests/test_journal.py"
Task: "Add reset-to-pending tests in src/tradegumi/tests/test_journal.py"
```

## Parallel Example: Dashboard Work

```text
Task: "Handle missing trade correlation data in dashboard/src/hooks/useData.ts"
Task: "Add mode label mapping in dashboard/src/lib/api.ts"
Task: "Update Strategy Metrics date request behavior in dashboard/src/app/strategy-metrics/page.tsx"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Complete US1 and US7 first to restore metrics and dashboard trust.
3. Stop and validate with focused tests and quickstart checks.

### Incremental Delivery

1. Add Signal Journal export (US2).
2. Add Signal Journal purge (US3).
3. Add reset-to-pending (US4).
4. Add Developing-mode P&L correction (US5).
5. Add Developing label sweep (US6).
6. Run full focused validation and prepare Conventional Commit history.


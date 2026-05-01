# Tasks: Strategy Metrics

**Input**: Design documents from `specs/002-strategy-metrics/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include focused pytest coverage for backend diagnostic storage and aggregation because the feature depends on preserved signal behavior, correct near-miss classification, deterministic blocker ranking, and bounded performance.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare shared configuration, route directories, and type locations for strategy metrics.

- [ ] T001 Add strategy metrics retention and display defaults to `src/tradegumi/config.py`
- [ ] T002 Create dashboard route directories under `dashboard/src/app/strategy-metrics/` and `dashboard/src/app/api/strategy-metrics/`
- [ ] T003 [P] Add empty strategy metrics backend test module in `src/tradegumi/tests/test_strategy_metrics.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core diagnostic data model, persistence, proxy auth, and state-output infrastructure required before any user story can work.

**CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T004 Create `EvaluatedOpportunity`, `CriterionResult`, `DiagnosticSummary`, `CriterionSummary`, `BlockerSummary`, and `ComparisonPeriod` dataclasses in `src/tradegumi/strategy_metrics.py`
- [ ] T005 Implement SQLite schema initialization for diagnostic opportunities and criterion results in `src/tradegumi/strategy_metrics.py`
- [ ] T006 Implement diagnostic record validation, JSON serialization, and 90-day retention pruning in `src/tradegumi/strategy_metrics.py`
- [ ] T007 Implement compact diagnostic state writer for `src/tradegumi/data/strategy_metrics.json` in `src/tradegumi/strategy_metrics.py`
- [ ] T008 Implement stable threshold-version serialization helpers for active signal thresholds in `src/tradegumi/signal_engine.py`
- [ ] T009 [P] Add TypeScript interfaces for strategy metric summaries, opportunities, criteria, blockers, and comparisons in `dashboard/src/types/index.ts`
- [ ] T010 [P] Add strategy metrics API client method stubs in `dashboard/src/lib/api.ts`
- [ ] T011 Add shared auth helper for strategy metrics dashboard proxy routes in `dashboard/src/app/api/strategy-metrics/_auth.ts`
- [ ] T012 Add pytest coverage for schema creation, near-miss validation, serialization, retention pruning, state writing, and threshold-version helpers in `src/tradegumi/tests/test_strategy_metrics.py`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Review No-Signal Periods (Priority: P1) MVP

**Goal**: Let the strategy owner select a no-signal period and see evaluated opportunities, final decisions, blocked criteria, and near-miss counts.

**Independent Test**: Select a date range with evaluated opportunities and no emitted signals; verify the dashboard shows total evaluated count, zero emitted count, rejection/skip counts, near-miss count, and opportunity drill-down with criterion-level pass/fail details.

### Implementation for User Story 1

- [ ] T013 [US1] Add diagnostic result structures and helper builders beside the existing `Signal` dataclass in `src/tradegumi/signal_engine.py`
- [ ] T014 [US1] Update `SignalEngine.check_symbol` in `src/tradegumi/signal_engine.py` to return both the existing signal result and a diagnostic result without changing signal pass/fail behavior
- [ ] T015 [US1] Capture criterion pass/fail values, thresholds, margins, confidence rejection, cooldown rejection, threshold version, and data-quality notes in `src/tradegumi/signal_engine.py`
- [ ] T016 [US1] Persist one evaluated opportunity per checked symbol from `check_and_execute` in `src/tradegumi/main.py`
- [ ] T017 [US1] Mark market-closed, rollover, engine-error, no-trend, criteria-failed, confidence-failed, cooldown, risk-blocked, and emitted decisions in `src/tradegumi/main.py`
- [ ] T018 [US1] Log risk-blocked actionable candidates and engine diagnostic errors through existing observable alert/log paths in `src/tradegumi/main.py`
- [ ] T019 [US1] Write latest diagnostic summary snapshots to `src/tradegumi/data/strategy_metrics.json` from `src/tradegumi/main.py`
- [ ] T020 [US1] Implement `record_opportunity`, `get_summary`, and `get_opportunities` storage/query functions in `src/tradegumi/strategy_metrics.py`
- [ ] T021 [US1] Surface threshold-version changes and malformed metric exclusions as data-quality warnings in `src/tradegumi/strategy_metrics.py`
- [ ] T022 [US1] Add `GET /api/strategy-metrics/summary` and `GET /api/strategy-metrics/opportunities` handlers in `src/tradegumi/api_server.py`
- [ ] T023 [US1] Add authenticated summary proxy route in `dashboard/src/app/api/strategy-metrics/summary/route.ts`
- [ ] T024 [US1] Add authenticated opportunities proxy route in `dashboard/src/app/api/strategy-metrics/opportunities/route.ts`
- [ ] T025 [US1] Add `getStrategyMetricsSummary`, `getStrategyMetricOpportunities`, and `useStrategyMetricsSummary` in `dashboard/src/lib/api.ts` and `dashboard/src/hooks/useData.ts`
- [ ] T026 [US1] Build the `/strategy-metrics` summary page with date range controls, headline counts, empty states, threshold-version warnings, and near-miss/opportunity tables in `dashboard/src/app/strategy-metrics/page.tsx`
- [ ] T027 [US1] Add pytest coverage for no-signal summaries, rejected opportunities, skipped opportunities, threshold-version warnings, and opportunity drill-downs in `src/tradegumi/tests/test_strategy_metrics.py`

**Checkpoint**: User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Compare Criterion Strictness (Priority: P2)

**Goal**: Show criterion pass/fail behavior and combined blocker ranking so the user can identify strictness candidates without automatic strategy changes.

**Independent Test**: Review a completed analysis period and verify each criterion shows pass count, fail count, pass rate, fail rate, near-miss contribution, average margin, incomplete count, and combined blocker ranking.

### Implementation for User Story 2

- [ ] T028 [US2] Implement criterion summary aggregation in `src/tradegumi/strategy_metrics.py`
- [ ] T029 [US2] Implement deterministic combined blocker scoring with 40 percent frequency, 30 percent normalized margin closeness, 30 percent opportunity quality, and stable tie-breakers in `src/tradegumi/strategy_metrics.py`
- [ ] T030 [US2] Include criterion summaries, top blockers, threshold-version warnings, and data-quality warnings in summary responses from `src/tradegumi/api_server.py`
- [ ] T031 [US2] Add blocker ranking and criterion diagnostic fields to dashboard API parsing in `dashboard/src/lib/api.ts`
- [ ] T032 [US2] Add criterion diagnostics table, top-three blocker panel, threshold-version warning display, and incomplete-data warnings to `dashboard/src/app/strategy-metrics/page.tsx`
- [ ] T033 [US2] Ensure `dashboard/src/app/strategy-metrics/page.tsx` labels diagnostics as review candidates without rendering threshold-change actions
- [ ] T034 [US2] Add pytest coverage for criterion pass/fail rates, near-miss contribution, average failure margin, data-quality warnings, threshold-version grouping, and blocker ranking tie-breakers in `src/tradegumi/tests/test_strategy_metrics.py`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Track Changes Over Time (Priority: P3)

**Goal**: Let the strategy owner compare two time windows and see changes in opportunity volume, signal volume, near-misses, and top blockers.

**Independent Test**: Select two date ranges and verify comparison output shows baseline and comparison summaries, deltas, blocker-rank changes, and insufficient-data messaging when either range has no usable diagnostics.

### Implementation for User Story 3

- [ ] T035 [US3] Implement `compare_periods` aggregation and delta calculation in `src/tradegumi/strategy_metrics.py`
- [ ] T036 [US3] Add `GET /api/strategy-metrics/compare` handler in `src/tradegumi/api_server.py`
- [ ] T037 [US3] Add authenticated comparison proxy route in `dashboard/src/app/api/strategy-metrics/compare/route.ts`
- [ ] T038 [US3] Add `getStrategyMetricsComparison` and `useStrategyMetricsComparison` in `dashboard/src/lib/api.ts` and `dashboard/src/hooks/useData.ts`
- [ ] T039 [US3] Add comparison mode controls, baseline/comparison date ranges, delta cards, and blocker-rank change display in `dashboard/src/app/strategy-metrics/page.tsx`
- [ ] T040 [US3] Add pytest coverage for comparison deltas, top-blocker changes, threshold-version differences, and empty-period warnings in `src/tradegumi/tests/test_strategy_metrics.py`

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, export, documentation, and final review tasks that affect multiple stories.

- [ ] T041 [P] Add JSON export helper for selected diagnostic summaries and optional opportunity details in `src/tradegumi/strategy_metrics.py`
- [ ] T042 Add `GET /api/strategy-metrics/export` handler in `src/tradegumi/api_server.py`
- [ ] T043 Add authenticated Next.js export proxy in `dashboard/src/app/api/strategy-metrics/export/route.ts`
- [ ] T044 Add export action to `dashboard/src/app/strategy-metrics/page.tsx`
- [ ] T045 [P] Add a navigation link to the Strategy Metrics page in `dashboard/src/components/Header.tsx`
- [ ] T046 Add seeded 90-day diagnostic dataset performance checks for summary aggregation in `src/tradegumi/tests/test_strategy_metrics.py`
- [ ] T047 Run backend validation commands and record signal-loop diagnostic overhead from `specs/002-strategy-metrics/quickstart.md`
- [ ] T048 Run dashboard validation commands and verify 90-day summary load timing from `specs/002-strategy-metrics/quickstart.md`
- [ ] T049 Update documentation notes for strategy metrics usage in `README.md`
- [ ] T050 Submit PR with DockeGumi as reviewer using `specs/002-strategy-metrics/tasks.md` as the completion checklist

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 6)**: Depends on desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational; provides MVP no-signal review.
- **User Story 2 (P2)**: Starts after Foundational; can be developed after or alongside US1 but integrates into the same summary response/page.
- **User Story 3 (P3)**: Starts after Foundational; depends on summary aggregation concepts from US1/US2 for useful comparison output.

### Within Each User Story

- Backend models and storage before backend endpoints.
- Backend endpoints before Next.js proxy and dashboard hooks.
- Auth helper before all dashboard proxy routes.
- Data hooks before dashboard UI integration.
- Story-specific tests after the implementation they validate, unless using a local TDD workflow.

---

## Parallel Opportunities

- T003 can run in parallel with T001 and T002.
- T009 and T010 can run in parallel with backend foundational work after T004 shape is understood.
- Within US1, T023 and T024 can proceed after T022 contract shape is clear, while T026 waits for hook/client methods.
- Within US2, T031 can run in parallel with T028/T029 after response shape is agreed.
- Within US3, T037 and T038 can run in parallel after T036 response shape is agreed.
- T041 and T045 can run in parallel during polish.

## Parallel Example: User Story 1

```text
Task: "Add authenticated summary proxy route in dashboard/src/app/api/strategy-metrics/summary/route.ts"
Task: "Add authenticated opportunities proxy route in dashboard/src/app/api/strategy-metrics/opportunities/route.ts"
```

## Parallel Example: User Story 2

```text
Task: "Implement criterion summary aggregation in src/tradegumi/strategy_metrics.py"
Task: "Add blocker ranking and criterion diagnostic fields to dashboard API parsing in dashboard/src/lib/api.ts"
```

## Parallel Example: User Story 3

```text
Task: "Add authenticated comparison proxy route in dashboard/src/app/api/strategy-metrics/compare/route.ts"
Task: "Add getStrategyMetricsComparison and useStrategyMetricsComparison in dashboard/src/lib/api.ts and dashboard/src/hooks/useData.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundation.
3. Complete Phase 3 User Story 1.
4. Validate that no-signal periods show evaluated opportunities, blockers, near-misses, threshold-version warnings, and JSON state output.
5. Stop and review before adding strictness ranking or period comparison.

### Incremental Delivery

1. Setup + Foundation: diagnostic storage, JSON state, auth helper, and shared types.
2. US1: collect and review no-signal diagnostics.
3. US2: add strictness and blocker ranking.
4. US3: add period comparison.
5. Polish: export, navigation, docs, performance validation, and PR.

### Quality Gates

- Existing signal emission, risk-check, and execution behavior must remain unchanged.
- Every evaluated opportunity must have a final decision or incomplete-data reason.
- Rejected opportunities with exactly one failed required criterion must be marked `near_miss`.
- Diagnostic visibility must satisfy constitution observability through JSON state output plus existing alert/log paths for significant signal events.
- Dashboard must distinguish no evaluated opportunities from evaluated opportunities with no emitted signals.
- Final task must submit PR with DockeGumi as reviewer.

---
description: "Task list for Strategy Metrics Dashboard Usability & Criterion Drilldown"
---

# Tasks: Strategy Metrics Dashboard Usability & Criterion Drilldown

**Input**: Design documents from `specs/022-metrics-dashboard-drilldown/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED. The feature ships two explicit test contracts (`contracts/api-strategy-metrics.md` backend tests, `contracts/ui-report-state.md` UI behavior) and the constitution requires coverage of non-obvious behavior (controlled-execution state machine, availability semantics, criterion filtering).

**Organization**: Tasks are grouped by user story (US1–US5 from spec.md) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 (user-story phases only)
- Exact file paths are included.

## Path Conventions

- **Frontend** (Next.js 16 / React 19 / Tailwind v4): `dashboard/src/...`
- **Backend** (Python): `src/tradegumi/...`; pytest in `src/tradegumi/tests/`
- **Frontend tests**: Vitest colocated under `__tests__/` next to the unit under test.

> ⚠️ Per `dashboard/AGENTS.md`, this Next.js version has breaking changes — consult `node_modules/next/dist/docs/` before editing App Router/config code; verify shadcn against the installed Next/Tailwind versions, not from memory.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install and theme the UI foundation; create feature folders.

- [X] T001 Initialized shadcn/ui in `dashboard/` (`npx shadcn@latest init -d`); `components.json` created (style radix-nova). ✅ build-clean.
- [X] T002 [P] Added shadcn primitives to `dashboard/src/components/ui/` (button, card, table, sheet, dialog, badge, skeleton, tabs, input, label, separator, select, chart) and installed `recharts`. (MagicUI animated-number deferred — charts implemented as SSR-safe CSS bars; recharts available.)
- [X] T003 [P] Rewrote `dashboard/src/app/globals.css` so shadcn tokens map onto the slate dark palette (`--background:#020617`, `--foreground:#e2e8f0`) and added `dark` to `<html>`; extends, not replaces, the theme (FR-025). ✅
- [X] T004 [P] Created `dashboard/src/components/strategy-metrics/` with a `charts/` subfolder.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared, additive type changes consumed by multiple stories. Additive/no-op for stories that don't use the new fields.

**⚠️ CRITICAL**: Complete before US2 and US4 (US1/US3/US5 do not depend on it).

- [X] T005 Additive TS type updates in `dashboard/src/types/index.ts`: add `layer: string` to `StrategyCriterionSummary`; add optional `pipeline_funnel`, `near_miss_reason_counts`, `signal_type_counts`, `strategy_counts` to `StrategyMetricsSummary` (per `data-model.md` / `contracts/api-strategy-metrics.md`). ✅ tsc-clean.

**Checkpoint**: Shared types ready — user stories can proceed.

---

## Phase 3: User Story 1 - Run a Report on Demand (Priority: P1) 🎯 MVP

**Goal**: Edit dates/filters freely and fetch only on an explicit Apply, with a loading state, in-flight guard, and the last successful report kept on screen (incl. on error).

**Independent Test**: Change start, then end, then a filter → zero fetches until Apply; Apply shows loading and runs one fetch; double-click runs one fetch; force an error → last report stays visible.

### Tests for User Story 1

> Write these FIRST and ensure they FAIL before implementation.

- [X] T006 [P] [US1] Vitest for the report hook in `dashboard/src/hooks/__tests__/useStrategyMetricsReport.test.ts`: no fetch on draft edits; one fetch per `run()`; in-flight guard; keep-last-on-error. ✅ 4 tests pass.
- [X] T007 [P] [US1] Vitest for controls in `dashboard/src/components/strategy-metrics/__tests__/ReportControls.test.tsx`: no fetch on edit; Apply disabled while loading; invalid range blocks Apply + message. ✅ 4 tests pass.

### Implementation for User Story 1

- [X] T008 [US1] Added `useStrategyMetricsReport()` to `dashboard/src/hooks/useData.ts` — manual `run()`, `inFlight` guard, `seq` stale-drop, keeps `summary`/`opportunities` on error; `loadMore` retained. (FR-002–FR-005, SC-009) ✅
- [X] T009 [US1] Created `dashboard/src/components/strategy-metrics/ReportControls.tsx`: draft filters, Apply, range validation, loading-disabled, dirty hint. (FR-001/FR-003/FR-006/FR-035) ✅
- [X] T010 [US1] Rewrote `dashboard/src/app/strategy-metrics/page.tsx` to draft-vs-applied; only Apply calls `run()`; Export preserved. (FR-001–FR-005, FR-024) ✅
- [X] T011 [US1] Added shadcn `Skeleton` first-load placeholders; last report stays visible during fetch/error. (FR-028/FR-005) ✅

**Checkpoint**: US1 complete — the existing dashboard now runs reports only on Apply and never blanks on error. Shippable MVP.

---

## Phase 4: User Story 2 - Drill Into a Criterion's Failures (Priority: P2)

**Goal**: Click a criterion to inspect its failed opportunities with measured value / threshold / operator / blocker context, filterable inside the drilldown.

**Independent Test**: Click a criterion → overlay with name/layer/counts/rates; failed-first list with measured vs threshold and operator; inner filters narrow; expand a failure → full criteria list; a zero-evaluated criterion shows "no data".

### Tests for User Story 2

- [X] T012 [P] [US2] pytest in `src/tradegumi/tests/test_strategy_metrics.py`: `criterion` filter on `get_opportunities` returns only opportunities where that criterion `passed=false`, failed-first, respects `limit/offset`, combinable with `symbol`/`near_miss`; unknown criterion → `[]`. (contract api §1) ⏭️ collects clean; runs under Postgres DSN (skipped locally — no PG).
- [X] T013 [P] [US2] pytest in `src/tradegumi/tests/test_strategy_metrics.py`: `criterion_summaries[].layer` present and correct via `get_summary`. (contract api §2, FR-012) ⏭️ skipped locally (no PG).
- [X] T014 [P] [US2] pytest in `src/tradegumi/tests/test_strategy_metrics_backend.py`: durable criterion filter the endpoint forwards. ⏭️ skipped locally (no PG).
- [X] T015 [P] [US2] Vitest in `dashboard/src/components/strategy-metrics/__tests__/CriterionDrilldown.test.tsx`: loads criterion-scoped failures (asserts `criterion` param), shows measured/threshold/layer, no-data state. ✅ 2 tests pass.

### Implementation for User Story 2

- [X] T016 [P] [US2] In `src/tradegumi/strategy_metrics.py`, thread an optional `criterion` arg through `get_opportunities` / `_get_opportunities_db` — restrict via `EXISTS` on persisted criteria rows where `criterion_name IN (canonical+legacy spellings) AND passed = 0`; added `_stored_criterion_names` helper; docstrings added. (contract api §1, FR-023) ✅ import-verified.
- [X] T017 [P] [US2] In `src/tradegumi/strategy_metrics.py`, added `layer: str` to `CriterionSummary` and populate via `MAX(c.layer)` in `_criterion_summaries_db`; docstring. (contract api §2, FR-012) ✅ import-verified.
- [X] T018 [US2] In `src/tradegumi/api_server.py` opportunities handler, read `criterion` query param and pass `criterion=criterion or None` to `get_opportunities`. ✅ AST-verified.
- [X] T019 [P] [US2] In `dashboard/src/lib/api.ts`, added optional `criterion` to `getStrategyMetricOpportunities` params. ✅ tsc-clean.
- [X] T020 [US2] Created `dashboard/src/components/strategy-metrics/CriterionDrilldown.tsx` (shadcn `Sheet`, keyed body): lazy-loads via `criterion`; header stats incl. `layer`; failed-first list with measured/threshold/operator/expected-vs-actual/blocker; inner filters; expand to full criteria; no-data state; Radix focus-management + Esc. (FR-011–FR-017, FR-030) ✅
- [X] T021 [US2] Criterion rows (table + top-blocker bars) are clickable/keyboard-activatable to open the drilldown; report preserved on open/close. (FR-011, SC-013) ✅

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 - Trust the Executive Summary Numbers (Priority: P3)

**Goal**: Every summary card is backed by real data; unavailable metrics are hidden/marked (distinct from a real `0`); dead/hardcoded cards removed.

**Independent Test**: Audit each card → all map to a `summary` field; a `null`/absent metric renders "unavailable" distinct from `0`; no card is stuck at a hardcoded value.

### Tests for User Story 3

- [X] T022 [P] [US3] Vitest in `dashboard/src/components/strategy-metrics/__tests__/ExecutiveSummary.test.tsx`: `0` renders as `0`; `null` renders "Unavailable" distinctly; populated value shown. ✅ 4 tests pass.

### Implementation for User Story 3

- [X] T023 [P] [US3] Created `dashboard/src/lib/metrics-availability.ts`: `metricDisplay` distinguishes real-zero (`0`) from unavailable (`null`/`undefined`/NaN). (FR-008/FR-009) ✅
- [X] T024 [US3] Created `dashboard/src/components/strategy-metrics/ExecutiveSummary.tsx`: every card bound to a `DiagnosticSummary` field via the availability helper; unavailable shown distinctly; no hardcoded cards. (FR-007–FR-010, FR-027) ✅
- [X] T025 [US3] Replaced the inline `Stat`/`ManagedLifecycleStats` blocks in `page.tsx` with `ExecutiveSummary`. (FR-007, FR-010) ✅

**Checkpoint**: US1–US3 independently functional.

---

## Phase 6: User Story 4 - Read the Dashboard at a Glance, Polished and Presentable (Priority: P4)

**Goal**: Clear section hierarchy, restrained charts, one cohesive accessible visual language extending the dark theme, with non-color status cues and reduced-motion support.

**Independent Test**: Sections appear controls→exec summary→failure diagnosis→drilldown→explorer; diagnosis shows ranked blockers, pass/fail table, near-miss reasons, funnel; status uses color + a non-color cue; keyboard operable; reduced-motion suppresses decorative animation.

### Tests for User Story 4

- [X] T026 [P] [US4] Vitest in `dashboard/src/components/strategy-metrics/__tests__/status.test.tsx`: every `StatusBadge` pairs color with a non-color cue (icon + text label) across all statuses. (FR-026/SC-011) ✅ 6 cases pass. (Section order verified statically in `page.tsx`; reduced-motion via global CSS.)
- [X] T027 [P] [US4] Created `dashboard/src/components/strategy-metrics/charts/` (`BarList.tsx`, `PipelineFunnel.tsx`) — SSR-safe accessible CSS bar visualizations (pass/fail, ranked blockers, near-miss reasons, funnel) with status colors + `tabular-nums`. (FR-031, FR-020) [recharts installed for future use; CSS bars chosen for reliable render without a visual loop]
- [X] T028 [US4] Created `dashboard/src/components/strategy-metrics/FailureDiagnosis.tsx`: ranked top blockers, clickable criterion pass/fail table → drilldown, near-miss reason counts, pipeline funnel. (FR-019, FR-020) ✅ (symbol breakdown omitted — no per-symbol field, per R8)
- [X] T029 [US4] Finalized section hierarchy in `page.tsx` (controls→exec summary→diagnosis→drilldown→explorer); one cohesive shadcn dark-theme language; status via badges (color + icon/label). (FR-018, FR-025, FR-026) ✅
- [X] T030 [US4] Accessibility & motion: keyboard-operable filters/Apply/criteria-rows/drilldown/pagination with visible focus rings; sticky table headers + contained scroll; global `prefers-reduced-motion` rule in `globals.css`. (FR-032–FR-035, SC-011/SC-012/SC-015) ✅ [WCAG-AA contrast + laptop no-h-scroll to confirm in live verification T038]

**Checkpoint**: US1–US4 independently functional; dashboard is polished and accessible.

---

## Phase 7: User Story 5 - Browse Opportunities Without Overload (Priority: P5)

**Goal**: Searchable, paginated opportunity explorer with expandable detail; never loads the full set at once.

**Independent Test**: With many opportunities, the explorer pages/bounds loading; search/filter narrows; a row expands to full detail + criteria list.

### Tests for User Story 5

- [X] T031 [P] [US5] Vitest in `dashboard/src/components/strategy-metrics/__tests__/OpportunityExplorer.test.tsx`: lists + search narrows; row expands to criteria; "Load more (n/total)" only when more remain. ✅ 3 tests pass.

### Implementation for User Story 5

- [X] T032 [US5] Created `dashboard/src/components/strategy-metrics/OpportunityExplorer.tsx`: bounded list reusing `loadMore` (200/page), search narrowing, expandable rows with full criteria. (FR-021/FR-022, SC-006) ✅
- [X] T033 [US5] Replaced the inline "Evaluated Opportunities" block in `page.tsx` with `OpportunityExplorer`. (FR-021) ✅

**Checkpoint**: All user stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Compatibility guard, quality, docs, validation, PR.

- [X] T034 [P] Added export-parity test in `src/tradegumi/tests/test_strategy_metrics_backend.py`: `export_summary["summary"]` equals `get_summary` for a fixed range and carries `layer`. (FR-024, SC-007) ⏭️ collects clean; runs under Postgres DSN.
- [X] T035 [P] Reviewed changed code — intention-revealing names, simple control flow, named constants (`REPORT_PAGE_SIZE`, `DRILLDOWN_LIMIT`); helper docstrings on components. ✅
- [X] T036 [P] Python docstrings added/verified for new/modified functions in `strategy_metrics.py` (`_stored_criterion_names`, `get_opportunities`, `CriterionSummary.layer`) and the `api_server.py` handler change. ✅
- [X] T037 Ran suites: `vitest` 31/31 pass; `next build` clean (`/strategy-metrics` generated); `tsc` + `eslint` clean; pytest collects 67 (skip — no local Postgres). ✅
- [ ] T038 Run the `specs/022-metrics-dashboard-drilldown/quickstart.md` manual verification checklist (US1–US5 + export compatibility). ⏳ **Pending** — needs the live backend + browser (and ideally a throwaway Postgres for the backend tests). Not runnable in this session.
- [X] T039 Opened PR [#138](https://github.com/Gitchegumi/CTI_Scripts/pull/138) — author **DockeGumi**, reviewer **Gitchegumi** requested, base `master`. (Constitution: Pull Request Policy) ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup; blocks US2 and US4 (additive/no-op for US1/US3/US5).
- **US1 (Phase 3)**: depends on Setup. MVP.
- **US2 (Phase 4)**: depends on Setup + Foundational (uses `layer`/types). Independent of US1 behavior.
- **US3 (Phase 5)**: depends on Setup. Independent.
- **US4 (Phase 6)**: depends on Setup + Foundational (uses funnel/counts) + US2 (clickable rows open drilldown) for AC2.
- **US5 (Phase 7)**: depends on Setup. Independent.
- **Polish (Phase 8)**: depends on all targeted stories.

### Shared-file note (page.tsx)

`dashboard/src/app/strategy-metrics/page.tsx` is edited by T010, T021, T025, T029, T033. These are **not** parallelizable with each other; sequence them in story-priority order. All other component/test files are story-isolated and parallelizable as marked.

### Within Each User Story

- Tests written first and failing before implementation.
- Backend filter/types before the components that consume them.
- Components before the page wiring that mounts them.

### Parallel Opportunities

- Setup: T002, T003, T004 in parallel after T001.
- US2 backend: T012–T015 (tests) in parallel; T016 and T017 in parallel (same file, different additions — coordinate or sequence if editing simultaneously); T019 parallel with backend.
- Across stories: once Setup + Foundational are done, US1/US3/US5 can proceed in parallel with US2 (different files), with the page.tsx edits serialized.

---

## Parallel Example: User Story 2

```bash
# Tests first (all parallel — different files):
Task: "pytest criterion filter in src/tradegumi/tests/test_strategy_metrics.py"
Task: "pytest layer field in src/tradegumi/tests/test_strategy_metrics.py"
Task: "pytest endpoint param in src/tradegumi/tests/test_strategy_metrics_backend.py"
Task: "Vitest CriterionDrilldown in dashboard/src/components/strategy-metrics/__tests__/CriterionDrilldown.test.tsx"

# Then backend + api-client in parallel:
Task: "criterion filter in src/tradegumi/strategy_metrics.py"
Task: "layer on CriterionSummary in src/tradegumi/strategy_metrics.py"
Task: "criterion param in dashboard/src/lib/api.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → 4. **STOP & VALIDATE** controlled execution (no fetch on edit, one fetch on Apply, keep-last-on-error) → 5. Demo.

### Incremental Delivery

Setup + Foundational → US1 (MVP: controlled execution) → US2 (drilldown) → US3 (trustworthy summary) → US4 (hierarchy + polish + a11y) → US5 (explorer) → Polish. Each story is an independently testable, shippable increment.

---

## Notes

- [P] = different files, no incomplete dependencies. [Story] maps each task to its user story.
- Tests precede implementation within each story; verify they fail first.
- `dashboard/AGENTS.md`: consult `node_modules/next/dist/docs/` before App Router/config edits.
- No signal/risk/execution logic is touched; backend changes are additive (criterion filter, `layer`), export parity is regression-guarded (T034).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.

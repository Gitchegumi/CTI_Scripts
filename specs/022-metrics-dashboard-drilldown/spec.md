# Feature Specification: Strategy Metrics Dashboard Usability & Criterion Drilldown

**Feature Branch**: `024-metrics-dashboard-drilldown`
**Spec Directory**: `specs/022-metrics-dashboard-drilldown`
**Created**: 2026-06-16
**Status**: Draft
**Input**: GitHub issue [#109](https://github.com/Gitchegumi/CTI_Scripts/issues/109) — "Improve Strategy Metrics dashboard usability and criterion drilldown"

## User Scenarios & Testing *(mandatory)*

The Strategy Metrics dashboard already collects evaluated-opportunity and criterion data (see feature `002-strategy-metrics`). Today it presents that data as an undifferentiated wall of numbers, refreshes on every filter keystroke, and shows some summary values that appear stuck at zero. The strategy owner cannot quickly answer "why are signals failing?" This feature makes the dashboard usable as a tuning tool by controlling when reports run, guaranteeing displayed numbers are real, and letting the owner drill into any criterion to see exactly which opportunities failed and why.

### User Story 1 - Run a Report on Demand (Priority: P1)

As the strategy owner, I want to edit the date range and filters freely and then trigger the report myself, so that I can set up a complete query (both start and end dates, plus filters) without the dashboard thrashing through repeated refreshes while I am still deciding.

**Why this priority**: Auto-refresh on every field change is the most acute daily pain — it makes the dashboard frustrating to use at all and makes multi-field changes (especially date ranges) nearly impossible. Fixing report execution makes every other capability usable. This slice delivers a viable, demonstrably better dashboard on its own.

**Independent Test**: Open the dashboard, change the start date, then the end date, then a filter, and confirm no data is fetched until the explicit "Apply Filters" control is used; confirm a loading state appears during the fetch and the previously loaded report stays on screen until the new one arrives.

**Acceptance Scenarios**:

1. **Given** a loaded report, **When** the owner changes the start date and then the end date, **Then** no report fetch occurs until the owner activates the Apply Filters / Run Report control.
2. **Given** edited filters, **When** the owner activates Apply Filters, **Then** a clear loading state is shown while the report is calculated and the control is disabled (or duplicate activations are ignored) until the fetch completes.
3. **Given** a report is being fetched, **When** the new report has not yet returned, **Then** the most recently completed report remains visible rather than blanking the screen.
4. **Given** a report fetch fails, **When** the error is detected, **Then** the owner sees an error indication and the last successful report stays visible.

---

### User Story 2 - Drill Into a Criterion's Failures (Priority: P2)

As the strategy owner, I want to click a criterion and inspect the opportunities it failed — including the measured value, the threshold, the comparison operator, and any blocker context — so that I can judge whether a threshold is too strict, too loose, or rarely the deciding factor.

**Why this priority**: This is the core analytical payoff named in the issue title. Once reports run on demand (US1), drilldown is what actually answers "why did signals fail/nearly pass?" It is independently testable against any loaded report.

**Independent Test**: From a loaded report, open the detail view for a criterion and confirm it lists failed opportunities first, each showing measured value, threshold, operator, expected-vs-actual pass, and blocker context where available; confirm the drilldown can be filtered by symbol, decision, signal type, near-miss, and blocker.

**Acceptance Scenarios**:

1. **Given** a report with criterion summaries, **When** the owner selects a criterion, **Then** a detail view opens showing the criterion name, layer, evaluated/pass/fail counts, pass/fail rate, near-miss contribution, average failure margin, and incomplete/malformed count.
2. **Given** an open criterion detail view, **When** the owner reviews it, **Then** failed opportunities are listed first, each showing measured value, threshold value, threshold operator, expected pass vs. actual pass, and blocker reason/context when available.
3. **Given** an open criterion detail view, **When** the owner applies an in-drilldown filter (symbol, decision, signal type, near-miss, blocker), **Then** the listed opportunities narrow to match without re-running the whole report.
4. **Given** a failed opportunity in the drilldown, **When** the owner expands it, **Then** they can see the underlying evaluated-opportunity detail including its full criteria list.
5. **Given** a criterion with no evaluated opportunities in the current report, **When** the owner opens its detail view, **Then** the view clearly states there is no data rather than showing misleading zeros.

---

### User Story 3 - Trust the Executive Summary Numbers (Priority: P3)

As the strategy owner, I want every summary metric at the top of the dashboard to reflect real data — and unavailable metrics to be hidden or marked unavailable rather than shown as a misleading zero — so that I can trust what I read before drilling down.

**Why this priority**: Incorrect or hardcoded top-line numbers erode trust in the whole tool, but the dashboard remains usable for diagnosis via drilldown even before every card is audited. Correctness is essential but can ship after the execution and drilldown slices.

**Independent Test**: Audit each summary card against the report data; confirm every displayed value traces to actual report data, that no value is a hardcoded placeholder, and that any metric the data cannot supply is hidden or explicitly marked unavailable (distinct from a real zero).

**Acceptance Scenarios**:

1. **Given** the dashboard summary cards, **When** a report loads, **Then** every displayed metric (e.g., total evaluated, emitted/rejected/skipped/indeterminate, near-misses, strategy-stat-eligible opportunities, suppressed signals, lifecycle/continuation/managed-outcome counts where applicable) is populated from the report data.
2. **Given** a metric the current data cannot supply, **When** the dashboard renders, **Then** that metric is hidden or marked "unavailable" instead of displaying a zero.
3. **Given** a metric whose true value is zero, **When** the dashboard renders, **Then** it is shown as zero in a way distinguishable from "unavailable".
4. **Given** the prior dashboard contained hardcoded/placeholder values, **When** this feature ships, **Then** no hardcoded placeholder metric remains on the page.

---

### User Story 4 - Read the Dashboard at a Glance, Polished and Presentable (Priority: P4)

As the strategy owner, I want the dashboard organized into a clear top-to-bottom hierarchy with simple charts and tables and a polished, professional visual treatment, so that I can move from high-level diagnosis to specific failing criteria without parsing a raw data dump — and so the tool feels trustworthy and pleasant to use, not like a debug screen.

**Why this priority**: Layout, visualization, and visual polish sharpen the experience and speed up diagnosis, but the underlying answers are already reachable through US1–US3. This is a refinement slice — high value for daily use, but not the MVP.

**Independent Test**: Confirm the page is arranged as report controls → executive summary → failure diagnosis → criterion drilldown → opportunity explorer; that the failure-diagnosis section includes digestible views such as pass/fail rate by criterion, top blockers by impact, near-miss reason counts, signal outcome breakdown, and an evaluated→candidate→rules-evaluated→emitted/rejected funnel; and that the page presents a single cohesive, accessible visual style consistent with the rest of the application.

**Acceptance Scenarios**:

1. **Given** the dashboard, **When** it loads, **Then** sections appear in the order: report controls, executive summary, failure diagnosis, criterion drilldown, opportunity explorer.
2. **Given** a loaded report, **When** the owner views the failure-diagnosis section, **Then** they see ranked top blockers by impact, a criterion pass/fail table, near-miss reason counts, and a pipeline funnel.
3. **Given** the report data supports a symbol-level breakdown, **When** the owner views the diagnosis section, **Then** a symbol-level breakdown is presented; **otherwise** it is omitted rather than shown empty.
4. **Given** the redesigned dashboard, **When** the owner uses it, **Then** controls, cards, tables, charts, and the drilldown share one consistent visual language (typography, spacing, and color) that extends the application's existing dark theme, and status meaning (pass / fail / near-miss / blocker / unavailable) is conveyed by both color and a non-color cue (label, icon, or shape).
5. **Given** the dashboard, **When** the owner navigates it by keyboard, **Then** every interactive element (filters, Apply control, clickable criteria, drilldown open/close, pagination) is reachable and operable with a visible focus indicator and adequate text contrast.

---

### User Story 5 - Browse Opportunities Without Overload (Priority: P5)

As the strategy owner, I want a searchable, paginated explorer of evaluated opportunities with expandable detail, so that I can investigate individual opportunities without the page loading every record at once.

**Why this priority**: The explorer rounds out investigation but is the least urgent slice; diagnosis and drilldown already surface representative failed examples. Pagination matters mainly for large result sets.

**Independent Test**: Load a report with many evaluated opportunities and confirm the explorer presents them in pages (or otherwise bounded batches) rather than loading all records at once, supports search/filter, and lets the owner expand an opportunity to see its criteria list.

**Acceptance Scenarios**:

1. **Given** a report with more evaluated opportunities than a single page, **When** the owner opens the explorer, **Then** opportunities are paginated (or batched) and the full set is not loaded at once.
2. **Given** the explorer, **When** the owner searches or filters, **Then** the listed opportunities narrow accordingly.
3. **Given** an opportunity row, **When** the owner expands it, **Then** the full evaluated-opportunity detail and its criteria list are shown.

---

### Edge Cases

- The owner activates Apply Filters repeatedly (double-click or rapid clicks) while a fetch is in progress — duplicate activations must be ignored, debounced, or disabled so only one fetch runs.
- The owner sets an end date earlier than the start date — the dashboard must validate the range and prevent or clearly reject the run rather than fetching nonsensical data.
- A report fetch fails or times out — the last successful report must remain visible and the failure must be surfaced.
- A selected range yields zero evaluated opportunities — summary, diagnosis, and drilldown must state there is nothing to analyze rather than render misleading zeros.
- A criterion is missing/incomplete for some opportunities — the incomplete/malformed count must be shown distinctly from pass and fail.
- A metric value is genuinely zero versus unavailable — these two states must be visually distinguishable.
- An evaluated-opportunity set is very large — the explorer and drilldown must avoid loading the entire set in one request.
- A criterion has many failed opportunities — the drilldown must bound how many examples it loads at once.
- The viewport is a narrower laptop rather than a wide monitor — dense tables must remain usable (sticky headers / contained scroll) without breaking the page chrome.
- The operator has reduced-motion enabled — decorative animation must be suppressed while all data and interactions remain fully available.

## Requirements *(mandatory)*

### Functional Requirements

**Report execution control**

- **FR-001**: The dashboard MUST allow editing the date range and all filters without fetching or recalculating data on field change.
- **FR-002**: The dashboard MUST provide an explicit control (e.g., "Apply Filters" / "Run Report") that is the only trigger for fetching/recalculating a report.
- **FR-003**: The dashboard MUST show a clear loading state while a report is being calculated.
- **FR-004**: The dashboard MUST prevent duplicate concurrent fetches by disabling, debouncing, or ignoring repeat activations while a fetch is in progress.
- **FR-005**: The dashboard MUST keep the last successfully loaded report visible until the next report completes, including when a fetch fails.
- **FR-006**: The dashboard MUST validate the date range (start not after end) before running and reject invalid ranges with a clear message.

**Executive summary correctness**

- **FR-007**: Every summary metric displayed MUST be backed by actual report data; no metric may be a hardcoded or static placeholder.
- **FR-008**: When the data cannot supply a metric, the dashboard MUST hide that metric or mark it "unavailable" instead of displaying a zero.
- **FR-009**: The dashboard MUST visually distinguish a metric whose real value is zero from a metric that is unavailable.
- **FR-010**: The summary MUST cover total evaluated; emitted, rejected, skipped, and indeterminate counts; near-misses; strategy-stat-eligible opportunities; and data-quality warnings, populating any of suppressed-signal, lifecycle, continuation-management, and managed-outcome counts that the data supports.

**Criterion drilldown**

- **FR-011**: Each criterion summary MUST be interactive (clickable or expandable) and open a detail view (panel, drawer, modal, or expanded section).
- **FR-012**: The criterion detail view MUST display: criterion name, layer, evaluated count, pass count, fail count, pass/fail rate, near-miss contribution, average failure margin, and incomplete/malformed count.
- **FR-013**: The criterion detail view MUST list failed opportunities first.
- **FR-014**: For each failed opportunity, the detail view MUST show measured value, threshold value, threshold operator, expected pass vs. actual pass, and blocker reason/context when available.
- **FR-015**: The criterion detail view MUST support filtering its listed opportunities by symbol, decision, signal type, near-miss, and blocker.
- **FR-016**: The detail view MUST allow expanding/linking into the underlying evaluated-opportunity detail, including that opportunity's full criteria list.
- **FR-017**: When a criterion has no evaluated opportunities in the current report, the detail view MUST state there is no data rather than show zeros that imply evaluation occurred.

**Visual hierarchy & digestion views**

- **FR-018**: The dashboard MUST present sections in the order: report controls, executive summary, failure diagnosis, criterion drilldown, opportunity explorer.
- **FR-019**: The failure-diagnosis section MUST include top blockers ranked by impact, a criterion pass/fail table, near-miss reason counts, and a pipeline funnel (evaluated → candidate → rules evaluated → emitted/rejected).
- **FR-020**: The dashboard MUST present digestion-friendly views including pass/fail rate by criterion, top blockers by count/impact, near-miss reason counts, and signal outcome breakdown; a symbol-level breakdown MUST be shown only when the data supports it.

**Opportunity explorer**

- **FR-021**: The opportunity explorer MUST be searchable/filterable and MUST paginate or otherwise bound how many records load at once rather than loading the full evaluated set.
- **FR-022**: The explorer MUST allow expanding an opportunity to view its full detail and criteria list.

**Data access & compatibility**

- **FR-023**: The system MUST provide a way to retrieve criterion-specific failures and individual opportunity detail without loading all evaluated opportunities at once; data-access capabilities MUST be extended only as needed to support the drilldown and explorer efficiently.
- **FR-024**: Existing JSON export / report behavior MUST continue to work unchanged.

**Presentation & visual design**

- **FR-025**: The dashboard MUST present a single cohesive visual system — consistent typography scale, spacing, control styling, and color tokens — across controls, cards, tables, charts, and the drilldown, extending the application's existing dark theme rather than introducing a clashing look.
- **FR-026**: Status meaning (pass, fail, near-miss, blocker, unavailable, zero) MUST be conveyed by a consistent semantic treatment that does not rely on color alone; each status MUST pair its color with a non-color cue such as a label, icon, or shape.
- **FR-027**: The executive summary MUST render as scannable stat cards — each with a clear label, a prominent value, and supporting context — visually distinct from the denser tables below.
- **FR-028**: Loading states MUST use placeholders/skeletons that preserve page layout (no full-screen blanking), consistent with keeping the last successful report visible (FR-005).
- **FR-029**: Empty, real-zero, unavailable, and error states MUST each have an explicit, visually distinct treatment so the owner can tell them apart at a glance.
- **FR-030**: The criterion drilldown MUST be surfaced as an overlay, drawer, or expandable region that preserves the underlying report context, with clear open and dismiss affordances (including keyboard dismissal) and managed focus.
- **FR-031**: Charts and tables MUST be legible and labeled, use the same status color semantics throughout, align numeric values for easy comparison, and degrade gracefully when data is sparse or absent.
- **FR-032**: The dashboard MUST be optimized for wide desktop viewing and remain usable down to a standard laptop width, with dense tables handling overflow gracefully (e.g., sticky headers and contained scrolling) rather than breaking the page layout.
- **FR-033**: All interactive elements MUST be keyboard operable with a visible focus indicator, carry accessible labels for assistive technology, and meet WCAG AA text-contrast guidance.
- **FR-034**: Motion and transitions (expand/collapse, hover, filter-apply, drilldown open/close) MUST be subtle and purposeful, MUST NOT delay reading the data, and MUST honor the operating system / browser reduced-motion preference.
- **FR-035**: The Apply control and clickable rows MUST expose clear hover, active, and disabled states, and the dashboard MUST make the distinction between pending (edited but not yet applied) and applied filters visually obvious.

### Key Entities *(include if feature involves data)*

- **Report**: The result of running the current filter set over a date range. Aggregates the executive-summary metrics, the criterion summaries, the diagnosis views (top blockers, near-miss reasons, funnel), and the evaluated-opportunity set.
- **Filter Set**: The owner-editable query inputs — date range (start/end), symbol, strategy, signal type, decision, and first blocker — that are applied only when the report is run.
- **Criterion Summary**: Per-criterion diagnostics — name, layer, evaluated/pass/fail counts, pass/fail rate, near-miss contribution, average failure margin, and incomplete/malformed count.
- **Evaluated Opportunity**: A single graded market opportunity — identity, symbol, signal type, decision/outcome, near-miss flag, deciding blocker, and the full list of evaluated criteria with their measured value, threshold, and operator.
- **Criterion Evaluation**: One criterion's result for one opportunity — measured value, threshold value, threshold operator, expected pass vs. actual pass, failure margin, and blocker reason/context when applicable.
- **Blocker**: A reason an otherwise-viable opportunity was rejected, with supporting context, rankable by how many opportunities it killed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Changing both the start and end date and one filter, then running the report, results in exactly one report fetch (zero intermediate fetches during editing).
- **SC-002**: 100% of summary metrics shown on the dashboard trace to actual report data; an audit finds zero hardcoded/placeholder metrics remaining.
- **SC-003**: For any metric the data cannot supply, it is hidden or marked unavailable in 100% of cases, and a real-zero metric is never confused with an unavailable one.
- **SC-004**: The owner can identify the single most impactful blocking criterion and view at least one concrete failed example opportunity (with its measured value and threshold) within 3 interactions of a loaded report.
- **SC-005**: For a representative failing criterion, the owner can see the measured value, threshold, and operator for failed opportunities in 100% of cases where that data exists.
- **SC-006**: Loading any single page of the opportunity explorer or any single criterion's failed examples does not require fetching the entire evaluated-opportunity set.
- **SC-007**: Existing JSON export produces the same output it did before this feature for an equivalent report.
- **SC-008**: After this feature, the owner can answer "which criteria are failing most often and which are close to passing?" using the on-screen diagnosis and drilldown without manually inspecting raw records.
- **SC-009**: When a report fetch fails, the previously loaded report remains visible 100% of the time (the screen never blanks on error).
- **SC-010**: A visual audit finds one consistent design system in use across the page — zero ad-hoc or clashing control/card/table styles — and the page reads as part of the same application as the rest of the dashboard.
- **SC-011**: 100% of status indicators (pass/fail/near-miss/blocker/unavailable) convey meaning through both color and a non-color cue, so the page remains interpretable without color perception.
- **SC-012**: 100% of interactive elements (filters, Apply control, criterion rows, drilldown open/close, pagination) are reachable and operable by keyboard with a visible focus state, and all primary text meets WCAG AA contrast.
- **SC-013**: Opening and closing the criterion drilldown never navigates away from or discards the loaded report; the owner returns to the same scroll/report context every time.
- **SC-014**: The dashboard renders without page-level horizontal scrolling at a standard laptop width and above.
- **SC-015**: With the reduced-motion preference enabled, non-essential animations are suppressed while all information and interactions remain fully available.

## Design & UI Constraints

This feature is explicitly a presentation upgrade as well as a functional one — the dashboard should look and feel like a polished, professional analysis tool, not a debug page.

- The implementation MAY adopt a UI component and/or animation library to achieve this polish. **ShadCN UI and MagicUI are both explicitly approved** for use here. Final selection between them (or use of both — MagicUI builds on the same foundation as ShadCN) and the integration approach are deferred to `/speckit-plan`.
- Any adopted library MUST integrate with the application's existing Tailwind-based dark theme and token system and MUST **extend, not replace**, the established visual language, so this page stays visually consistent with the rest of the dashboard.
- Visual polish MUST NOT come at the expense of the functional requirements: controlled report execution (US1), correct metrics (US3), and drilldown clarity (US2) take precedence over decorative flourish. Motion and effects stay subtle and purposeful (FR-034).
- Accessibility (keyboard operation, focus management, contrast, non-color status cues) is a hard requirement, not a nice-to-have (FR-026, FR-033) — a benefit that mature component libraries like the approved ones help deliver.

## Assumptions

- This dashboard is an internal, single-operator analysis tool for the strategy owner; multi-user concerns (concurrent editing, per-user permissions) are out of scope.
- The evaluated-opportunity and criterion data described in feature `002-strategy-metrics` (and related diagnostics features) already exists or is the authoritative source; this feature surfaces and reorganizes that data rather than redefining how grading works.
- "If needed" data-access additions are in scope: new query options or endpoints may be added where the current interface cannot efficiently supply criterion-specific failures or paginated opportunities, but no change to grading logic or thresholds is implied.
- Pagination/batch sizes for the explorer and per-criterion examples will use sensible defaults appropriate to the data volume; exact page size is an implementation detail.
- Chart/visualization styling stays restrained and data-first — the goal is fast comprehension for tuning. "Polished and presentable" here means clean, consistent, and accessible, not flashy; subtle motion is welcome but never required to read the data.
- The dashboard is viewed primarily on desktop/laptop; small-phone layouts are a graceful-degradation concern, not a primary target.
- A UI component/animation library may be introduced specifically to deliver the visual polish; ShadCN UI and MagicUI are pre-approved candidates (see Design & UI Constraints), with the final choice and wiring decided during planning.
- The existing date-range, symbol, strategy, signal-type, decision, and first-blocker filter concepts remain the filter vocabulary; this feature changes *when* they apply, not their meaning.
- "Last successful report stays visible" applies within a single dashboard session; persistence across full page reloads is not required.

## Dependencies

- Builds on the existing Strategy Metrics dashboard and its underlying metrics/diagnostics data (features `002-strategy-metrics`, `004-metrics-diagnostics`, and related signal-diagnostics work).
- Relies on the existing JSON export/report capability remaining available for backward-compatibility verification.

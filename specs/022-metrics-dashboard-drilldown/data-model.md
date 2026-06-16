# Phase 1 Data Model: Strategy Metrics Dashboard Usability & Criterion Drilldown

This feature is presentation-and-access focused; it introduces **no new persisted entities**. It reuses the existing strategy-metrics model and makes two small additive field changes plus exposes already-computed-but-unsurfaced fields. Below: the reused entities, the additive changes, and the new client-side (non-persisted) view-state entities.

## Reused persisted/domain entities (unchanged shape unless noted)

### EvaluatedOpportunity
Source: `tradegumi.strategy_metrics.EvaluatedOpportunity` → TS `StrategyMetricOpportunity`.
Key fields used: `id`, `evaluated_at`, `symbol`, `strategy`, `signal_type`(via `strategy`/`signal_type_counts`), `direction`, `trend`, `final_decision` (`emitted|rejected|skipped|indeterminate`), `decision_reason`, `confidence`, `failed_criteria_count`, `near_miss`, `data_complete`, `data_quality_notes`, `threshold_version`, `usable_for_strategy_stats`, `stats_exclusion_reason`, managed-lifecycle fields, and `criteria[]`.
**No change.**

### CriterionResult (per opportunity)
Source: TS `StrategyMetricCriterion`. Carries the drilldown detail the spec requires per failed opportunity: `criterion_name`, `layer`, `measured_value`, `threshold_value`, `threshold_operator`, `passed` (`true|false|null`), `margin`, `normalized_margin`, `required`, `blocked_signal`, `data_quality` (`complete|missing|malformed|not_applicable`). Maps to FR-014/FR-016.
**No change** (already complete for drilldown).

### CriterionSummary (aggregate)
Source: `tradegumi.strategy_metrics.CriterionSummary` → TS `StrategyCriterionSummary`.
Existing: `criterion_name`, `evaluated_count`, `pass_count`, `fail_count`, `pass_rate`, `fail_rate`, `near_miss_contribution`, `average_failure_margin`, `incomplete_count`.
**ADDITIVE CHANGE (R5)**: add `layer: string`. Populated during aggregation from the criterion's recorded layer. Required by FR-012.

### BlockerSummary
Source: TS `StrategyBlockerSummary`. Fields: `criterion_name`, `blocked_count`, `frequency_component`, `margin_component`, `quality_component`, `combined_score`, `example_opportunity_ids[]`. Used for "top blockers ranked by impact" (FR-019) and seed examples for the drilldown.
**No change.**

### DiagnosticSummary (the Report payload)
Source: `tradegumi.strategy_metrics.DiagnosticSummary` → TS `StrategyMetricsSummary`.
Already computes the full executive-summary count set, `criterion_summaries[]`, `top_blockers[]`, `data_quality_warnings[]`, **plus** these computed-but-currently-unexposed fields:
- `pipeline_funnel: Record<string, number>` (evaluated → candidate → rules evaluated → emitted/rejected) — FR-019.
- `near_miss_reason_counts: Record<string, number>` — FR-019/FR-020.
- `signal_type_counts: Record<string, number>` and `strategy_counts: Record<string, number>` — FR-020 signal-outcome breakdown.
- `threshold_version_counts`, `stats_exclusion_counts` — supporting context.
**CHANGE (R7)**: expose these in the TS `StrategyMetricsSummary` type and render them. **No backend computation change.**

**Availability semantics (R6, FR-008/FR-009)**: a metric value of `null`/absent ⇒ *unavailable* (hide or mark); numeric `0` ⇒ *real zero* (display as zero). Any executive-summary card with no backing field in `DiagnosticSummary` is **removed** (dead placeholder, FR-007).

## New client-side view-state entities (not persisted)

These live in React state / hooks and define the controlled-execution behavior (US1). Documented here because they encode the feature's core state machine.

### FilterDraft
The user-editable query inputs, edited freely without fetching (FR-001).
Fields: `start: string (YYYY-MM-DD)`, `end: string`, `symbol?: string`, `strategy?: string`, `signal_type?: string`, `decision?: 'emitted'|'rejected'|'skipped'|'indeterminate'`, `first_blocker?: string`.
Validation (FR-006): `start <= end`; invalid ranges block `apply()` and surface a message.

### AppliedFilters
A snapshot of `FilterDraft` taken at the moment `apply()` runs; the only inputs a report fetch uses. `dirty = !shallowEqual(draft, applied)` drives the pending-vs-applied indication (FR-035).

### ReportState (hook: `useStrategyMetricsReport`)
State machine for controlled execution (FR-002–FR-005, SC-009).
Fields: `summary: StrategyMetricsSummary | null`, `opportunities: StrategyMetricOpportunity[]`, `status: 'idle' | 'loading' | 'success' | 'error'`, `error: string | null`, `requestSeq: number` (drops stale responses), `inFlight: boolean` (guards duplicate `run()`).
Transitions:
- `idle/success/error --run()--> loading` (ignored if `inFlight`).
- `loading --resolve(seq current)--> success` (replaces `summary`/`opportunities`).
- `loading --reject--> error` **while retaining previous `summary`/`opportunities`** (do not clear — FR-005/SC-009).
- stale resolve (`seq < current`) ⇒ ignored.

### CriterionDrilldownState
Per-open-criterion view state (lazy-loaded). Fields: `criterionName: string | null` (null = closed), `failedOpportunities: StrategyMetricOpportunity[]`, `page: { limit, offset }`, `innerFilters: { symbol?, decision?, signal_type?, near_miss?, blocker? }`, `status`. Opens as a sheet/dialog over the report (FR-030); loads via the `criterion`-scoped opportunities query (R4); shows no-data state when `evaluated_count === 0` (FR-017).

### ExplorerState
Opportunity explorer paging/search (FR-021/FR-022). Fields: `query: string`, `page: { limit, offset }`, `expandedId: string | null`. Reuses the existing `limit/offset` opportunities endpoint (already pageable; default 200/page).

## Field-to-requirement traceability (selected)

| Requirement | Backing data |
|-------------|--------------|
| FR-012 criterion detail header | `CriterionSummary` + **new** `layer` |
| FR-014 measured/threshold/operator/blocker per failed opp | `CriterionResult` (existing) + `decision_reason`/`first_blocker` |
| FR-019 funnel + near-miss reasons | `pipeline_funnel`, `near_miss_reason_counts` (exposed, R7) |
| FR-020 signal outcome breakdown | `signal_type_counts`, final-decision counts |
| FR-021 paginated explorer | opportunities `limit/offset` (existing) |
| FR-023 criterion-specific failures | **new** `criterion` filter param (R4) |
| FR-008/009 unavailable vs zero | `null` sentinel vs `0` (R6) |

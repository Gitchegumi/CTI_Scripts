# Phase 0 Research: Strategy Metrics Dashboard Usability & Criterion Drilldown

All open questions from the Technical Context are resolved below. Each item records the Decision, Rationale, and Alternatives considered.

## R1. Component/animation library on Next 16 + React 19 + Tailwind v4

**Decision**: Adopt **shadcn/ui** as the component foundation and **MagicUI** for selective, subtle motion. Initialize shadcn in "new-york" style against the existing CSS-first Tailwind v4 setup, generating `components.json` and adding design tokens into the existing `dashboard/src/app/globals.css` `@theme`/`:root` rather than a `tailwind.config.js`.

**Rationale**:
- shadcn/ui is copy-in source (not a runtime dependency lock-in), built on Radix primitives that provide focus management, keyboard interaction, and ARIA out of the box — directly satisfying FR-026/FR-030/FR-033 and SC-012/SC-013 with far less hand-rolled a11y code.
- shadcn supports Tailwind v4 and React 19 (its components are RSC/Client-safe; the strategy-metrics page is already `"use client"`). Tokens integrate with the existing `@theme inline` block, so the result *extends* the current slate dark theme (`--background:#020617`) rather than replacing it (Design & UI Constraints, FR-025).
- MagicUI builds on the same shadcn/Tailwind foundation and supplies the "presentable" polish (e.g., animated number tickers for stat cards, subtle reveals) without bespoke animation code, while staying restrained and reduced-motion-aware (FR-034, SC-015). The user explicitly pre-approved both.

**Alternatives considered**:
- *Hand-rolled components only* (status quo): rejected — re-implements accessibility and motion primitives the spec now requires; slower and more error-prone.
- *MUI / Mantine / Chakra*: rejected — heavier runtime, opinionated theming that would fight the existing Tailwind v4 tokens and the established visual language.
- *Headless UI alone*: rejected — fewer ready primitives than Radix/shadcn; more glue for tables, sheets, and charts.

**Integration notes / risks**:
- `dashboard/AGENTS.md` warns this Next.js version has breaking changes — consult `node_modules/next/dist/docs/` before writing/altering App Router or config code. The shadcn init must be verified against the installed Next/Tailwind versions, not assumed from training data.
- Pin added dependencies; keep the `ui/` primitives minimal (only what the page uses: button, card, table, sheet or dialog, badge, skeleton, tabs, input, select, chart).

## R2. Charting approach

**Decision**: Use **Recharts** via shadcn's Chart wrapper for the three visualizations (pass/fail rate by criterion, top blockers ranked, pipeline funnel). Render funnel as a horizontal stacked/ordered bar rather than a bespoke funnel shape. Use `tabular-nums` for all numeric columns.

**Rationale**: shadcn Chart standardizes theming/tooltips/legend with the design tokens, keeping charts legible and consistent (FR-031) and restrained/data-first (Assumptions). Recharts is React 19 compatible and lightweight enough for a handful of small charts.

**Alternatives considered**: Visx (more code), Chart.js (canvas, weaker theming integration), pure CSS bars (fine for blockers but inconsistent for grouped pass/fail). A CSS/flex bar is an acceptable fallback for the funnel if Recharts funnel ergonomics are poor.

## R3. Decoupling report execution (US1) — the core behavior change

**Decision**: Split filter state into **draft** (what the user is editing) and **applied** (what the last/next report runs on). Refactor the data hook into `useStrategyMetricsReport(appliedParams)` that:
- does **not** auto-fetch on every param change (remove the current `useEffect(refresh)` on param identity);
- exposes an explicit `run()`/`apply()` that copies draft→applied and triggers exactly one fetch;
- guards against concurrent/duplicate fetches with an in-flight ref (ignore `run()` while loading) and request-sequence guard to drop stale responses;
- **keeps the last successful `summary`/`opportunities` on error** (stop nulling them out — the current hook clears them on failure, violating FR-005/SC-009);
- surfaces `loading`, `error`, and a `dirty` flag (draft differs from applied) so the UI can show pending-vs-applied state (FR-035).

**Rationale**: Directly implements FR-001–FR-005 and the most acute pain (auto-refresh thrash, especially on date ranges). Keeping last-good data on error is a one-line behavior change with outsized UX value (SC-009).

**Alternatives considered**:
- *Debounce-only*: rejected — still fetches mid-edit; cannot satisfy "change both start and end before any fetch" (SC-001).
- *React Query/SWR*: viable but adds a dependency and its default refetch semantics fight the "only on Apply" requirement; the existing hand-rolled hook is small and already in place, so a focused refactor is lower risk. Revisit only if caching across navigations becomes a need.

## R4. Criterion drilldown data source (FR-013/FR-014/FR-023)

**Decision**: Add an **optional `criterion` query param** to `get_opportunities` / `/api/strategy-metrics/opportunities` that returns opportunities where the named criterion has `passed = false` (failed), ordered failed-first, reusing the existing `limit/offset` pagination. The drilldown panel queries this scoped, paginated endpoint on demand (lazy — only when a criterion is opened), combined with the per-criterion stats already in `criterion_summaries` and the `example_opportunity_ids` already on each `BlockerSummary`.

**Rationale**: The existing `first_blocker` filter only returns opportunities where the criterion was the *decisive* blocker; the spec wants *all* opportunities that failed the criterion (including non-decisive failures) with measured/threshold/operator detail (already present on each `StrategyMetricCriterion`). A criterion-scoped filter implemented via an `EXISTS`/JOIN on the already-persisted criteria rows avoids loading the full evaluated set (FR-023, SC-006) and needs **no new endpoint or schema change**.

**Alternatives considered**:
- *New `/criteria/:name` endpoint*: rejected as unnecessary surface area; the issue itself says "the existing opportunities endpoint may be enough if expanded with criterion filters."
- *Client-side filter of the loaded page*: rejected — only sees the currently loaded page, missing failures beyond it; breaks for large sets.

## R5. `layer` in the criterion table/drilldown (FR-012)

**Decision**: Add `layer: str` to the backend `CriterionSummary` dataclass (populated from the criterion's recorded layer during aggregation) and expose it in the TS `StrategyCriterionSummary`.

**Rationale**: The drilldown must show the criterion's layer; the per-opportunity `CriterionResult` already carries `layer`, but the aggregated summary drops it. Adding it at aggregation time is trivial and avoids client-side derivation.

**Alternatives considered**: Derive layer client-side from the first opportunity that contains the criterion — rejected as fragile and order-dependent.

## R6. Real-zero vs unavailable metrics (US3, FR-007–FR-010)

**Decision**: Treat a metric as **unavailable** when the backend value is `null`/absent, and as a **real zero** when it is the number `0`. Audit each executive-summary card against `DiagnosticSummary`: every displayed card must map to a field the backend actually computes. Cards with no backing computation are **removed**, not shown as `0`. Where a metric is conditionally computable (e.g., prime-suppression metrics that depend on journal availability), the backend already returns `0`-defaulted structures; the frontend renders those as real values and only marks "unavailable" when a field is `null`/missing. A small `metrics-availability.ts` helper centralizes the zero-vs-unavailable decision and the visual treatment.

**Rationale**: Satisfies FR-008/FR-009 and SC-002/SC-003 without a heavyweight contract change: most counts are genuine `0`s, and the only "stuck" values are cards bound to fields the backend never populates — those are dead placeholders to remove (FR-007). Using `null` as the unavailable sentinel is the minimal additive contract change for any metric that truly cannot be computed for a given range.

**Audit inputs** (from research): backend `DiagnosticSummary` genuinely computes the executive-summary set — `total_evaluated`, `emitted/rejected/skipped/indeterminate_count`, `near_miss_count`, `trade_opportunity_count`, `stats_excluded_count`, prime-suppression counts, continuation/managed-lifecycle counts, `data_quality_warnings` — **and also** `pipeline_funnel`, `near_miss_reason_counts`, `signal_type_counts`, `strategy_counts`, which the current page never renders. The implementer must reconcile the actual page cards against this list and flag any card with no source.

**Alternatives considered**: A dedicated `metric_availability: Record<string, bool>` map — rejected as over-engineered for the handful of fields involved; `null` sentinel is sufficient and idiomatic.

## R7. Diagnosis views that already have backend data (FR-019/FR-020)

**Decision**: Surface the **already-computed** `pipeline_funnel` and `near_miss_reason_counts` (and `signal_type_counts`/`strategy_counts` for the signal-outcome breakdown) by adding them to the TS `StrategyMetricsSummary` type and rendering them in `FailureDiagnosis`. No backend change for these.

**Rationale**: Lowest-cost path to FR-019/FR-020 — the data exists; only the type and UI are missing. Reduces backend risk to just R4 (criterion filter) and R5 (layer).

**Alternatives considered**: Recompute client-side from opportunities — rejected; redundant and only sees loaded pages.

## R8. Symbol-level breakdown ("if data supports it", FR-020/US4-AC3)

**Decision**: Treat the symbol-level breakdown as **conditional**. Present it when derivable; the cleanest source is a backend group-by, but to avoid scope creep, v1 derives a symbol breakdown from the loaded executive-summary counts only if a per-symbol field is available, otherwise the section is **omitted** (not shown empty). A backend per-symbol aggregation can be a follow-up if the operator wants it across the full set rather than the loaded page.

**Rationale**: The spec explicitly gates this on data support; omission-when-unsupported is compliant and avoids a larger backend aggregation in this slice.

**Alternatives considered**: Always compute server-side group-by — deferred; not required for acceptance and expands backend scope.

## Resolved unknowns summary

| Unknown | Resolution |
|---------|-----------|
| UI library on this stack | shadcn/ui + MagicUI, Tailwind v4 CSS-first tokens (R1) |
| Charts | Recharts via shadcn Chart; funnel as ordered bar (R2) |
| Stop auto-refresh | draft/applied split + manual `run()` + in-flight guard + keep-last-on-error (R3) |
| Criterion failures without loading everything | optional `criterion` filter on opportunities endpoint (R4) |
| Criterion `layer` | add to backend `CriterionSummary` + TS type (R5) |
| Zero vs unavailable | `null` = unavailable, `0` = real; remove dead cards (R6) |
| Funnel / near-miss reasons | already computed server-side; expose + render (R7) |
| Symbol breakdown | conditional; omit when unsupported (R8) |

No NEEDS CLARIFICATION markers remain.

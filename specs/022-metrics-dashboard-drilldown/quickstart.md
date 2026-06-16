# Quickstart: Strategy Metrics Dashboard Usability & Criterion Drilldown

Setup and verification for the redesign. Assumes the repo is checked out on branch `024-metrics-dashboard-drilldown` and the Python backend can serve `/api/strategy-metrics/*` on `:8199`.

> ⚠️ Before editing App Router/config code, read the note in `dashboard/AGENTS.md`: this Next.js version has breaking changes — consult `node_modules/next/dist/docs/` rather than relying on memory.

## 1. Install the UI foundation (shadcn/ui + MagicUI)

From `dashboard/`:

```powershell
# shadcn init — answer prompts for Tailwind v4 / React 19; this creates components.json
npx shadcn@latest init
# add only the primitives the page uses
npx shadcn@latest add button card table sheet dialog badge skeleton tabs input select chart
# charts dependency (pulled by shadcn chart, pin it)
npm install recharts
# MagicUI components are added via its CLI/registry as needed (e.g., animated number)
```

- Confirm `components.json` was created and that shadcn tokens were merged into `src/app/globals.css` **inside the existing `@theme`/`:root`** — do not introduce a `tailwind.config.js`; this project is Tailwind v4 CSS-first.
- Verify the added token values keep the slate dark theme (`--background:#020617`, `--foreground:#e2e8f0`). The page must still look like the rest of the app (FR-025).

## 2. Backend changes (additive)

Edit `src/tradegumi/strategy_metrics.py`:
- Add `layer: str` to `CriterionSummary`; populate it during aggregation.
- Thread an optional `criterion` arg through `_opportunity_filter_clauses` / `get_opportunities` / `_get_opportunities_db` → restrict to opportunities with a `CriterionResult` where `criterion_name == criterion AND passed == false` (EXISTS/JOIN), failed-first ordering.

Edit `src/tradegumi/api_server.py` (opportunities handler ~line 346): read `criterion = self._get_query_param("criterion")` and pass it to `get_opportunities`.

Run backend tests:

```powershell
python -m pytest src/tradegumi/tests/test_strategy_metrics.py src/tradegumi/tests/test_strategy_metrics_backend.py -q
```

Expected new/updated assertions (see `contracts/api-strategy-metrics.md`): criterion filter behavior, `layer` present, summary exposes `pipeline_funnel`/`near_miss_reason_counts`/`signal_type_counts`/`strategy_counts`, and **export parity unchanged**.

## 3. Frontend changes

- `src/types/index.ts`: add `layer` to `StrategyCriterionSummary`; add `pipeline_funnel`, `near_miss_reason_counts`, `signal_type_counts`, `strategy_counts` to `StrategyMetricsSummary`.
- `src/lib/api.ts`: add optional `criterion` to `getStrategyMetricOpportunities` params.
- `src/lib/metrics-availability.ts` (new): helpers for real-zero vs unavailable (`null`) rendering.
- `src/hooks/useData.ts`: refactor `useStrategyMetricsSummary` → `useStrategyMetricsReport` with manual `run()`, in-flight guard, sequence guard, and **keep-last-on-error** (stop nulling `summary`/`opportunities` on failure).
- `src/app/strategy-metrics/page.tsx`: rewrite to compose `ReportControls` (draft state + Apply + validation) → `ExecutiveSummary` → `FailureDiagnosis` (top blockers, pass/fail table, near-miss reasons, pipeline funnel) → `CriterionDrilldown` (sheet) → `OpportunityExplorer`.

Run frontend tests:

```powershell
npm run test   # vitest
```

## 4. Manual verification (maps to acceptance scenarios)

Start backend + dashboard, open `/strategy-metrics`, and confirm:

**US1 — controlled execution**
- [ ] Change start, then end, then a filter → no data fetches until "Apply Filters". (SC-001)
- [ ] Apply shows a loading state; double-clicking Apply runs only one fetch.
- [ ] While loading, the previous report stays visible (no blank).
- [ ] Force an error (stop backend) and Apply → error shown, **last report still visible**. (SC-009)
- [ ] Set end before start → Apply blocked with a message.

**US2 — drilldown**
- [ ] Click a criterion → overlay opens with name, layer, counts, rates, near-miss, avg margin, incomplete.
- [ ] Failed opportunities listed first; each shows measured value, threshold, operator, expected-vs-actual, blocker context.
- [ ] Inner filters (symbol/decision/signal type/near-miss/blocker) narrow the list.
- [ ] Expand a failed opportunity → full criteria list. Close drilldown → same report/scroll. (SC-013)
- [ ] Open a criterion with zero evaluated → "no data", not zeros. (FR-017)

**US3 — trustworthy summary**
- [ ] Every stat card maps to real data; no card stuck at a hardcoded value. (SC-002)
- [ ] A genuinely unavailable metric is hidden/marked unavailable, distinct from a real `0`. (SC-003)

**US4 — hierarchy & polish**
- [ ] Sections appear in order: controls → exec summary → diagnosis → drilldown → explorer. (FR-018)
- [ ] Diagnosis shows ranked blockers, pass/fail table, near-miss reasons, pipeline funnel.
- [ ] One cohesive style extending the dark theme; status uses color **plus** a non-color cue. (SC-010, SC-011)
- [ ] Keyboard: tab through filters/Apply/criteria/drilldown/pagination with visible focus. (SC-012)
- [ ] With OS reduced-motion on, decorative animation is suppressed. (SC-015)
- [ ] No page-level horizontal scroll at laptop width. (SC-014)

**US5 — explorer**
- [ ] Explorer paginates; full set not loaded at once. (SC-006)
- [ ] Search/filter narrows; rows expand to detail + criteria list.

**Compatibility**
- [ ] Export still downloads the same JSON as before for an equivalent range. (SC-007)

## 5. Definition of done
- All Vitest + pytest suites pass (incl. contract tests and export-parity test).
- Manual checklist above complete.
- New Python has docstrings; new TS uses intention-revealing names (Constitution: Code Quality).
- Final PR task names the reviewer per the dual-account workflow (or asks the user if unset).

# Analysis: DB-backed page performance and signal pipeline progression

## Artifact Consistency

- `spec.md`, `plan.md`, and `tasks.md` are aligned with the required workflow and acceptance criteria.
- No constitution conflicts were found. Signal thresholds remain out of scope unless proven mathematically wrong.
- Task coverage exists for every functional requirement and success criterion.

## Codebase Findings

### API endpoints used by DB-backed pages

- Strategy metrics dashboard proxies through `dashboard/src/app/api/strategy-metrics/*` to:
  - `GET /api/strategy-metrics/summary`
  - `GET /api/strategy-metrics/opportunities`
  - `GET /api/strategy-metrics/compare`
  - `GET /api/strategy-metrics/export`
- Signal journal proxies through `dashboard/src/app/api/journal/route.ts` to `GET /api/data/journal` and authenticated journal mutation/export endpoints.
- Manual trade journal proxies through `dashboard/src/app/api/manual-trades/*` to `/api/trades/manual`, `/api/trades/manual/stats`, and `/api/trades/manual/export`.
- Dashboard trade history proxies through `dashboard/src/app/api/trades/history/route.ts` to `/api/trades/history`.

### ORM models and query patterns

- The backend uses direct SQLite access, not an ORM.
- `src/tradegumi/strategy_metrics.py:get_opportunities()` previously selected opportunity rows and then queried `criterion_results` once per opportunity. This was an N+1 query pattern on the strategy metrics page.
- `src/tradegumi/strategy_metrics.py:get_summary()` reads all selected opportunities and criteria for broad date ranges. This is acceptable for bounded local ranges but needs indexes and careful default ranges.
- `src/tradegumi/manual_trades.py` builds unified histories by merging source trades, manual rows, annotations, and overrides. Stats/update paths use large limits such as `10_000`, which can be expensive under large local history.

### Migrations/indexes

- `strategy_metrics.py:init_schema()` already had single-column indexes for evaluated time, symbol, decision, and criterion opportunity.
- Added composite indexes for common range + symbol/decision filters and criterion name + opportunity aggregation.
- Existing SQLite schema setup is idempotent with `CREATE INDEX IF NOT EXISTS`.

### Frontend fetch patterns

- `dashboard/src/hooks/useData.ts:useStrategyMetricsSummary()` already fetches summary and opportunities in parallel.
- `useStrategyMetricsComparison()` fetched comparison data whenever the strategy metrics page rendered, even when the Compare view was disabled. This caused an unnecessary default page request.
- Journal and manual trade pages use no-store fetches and periodic reloads; no response-shape change was made in this pass.

### Signal evaluation flow

- `SignalEngine.check_symbol()` runs watchlist, trend filter, cooldown, then `_get_signal()`.
- `_get_signal()` runs M5 signal stack criteria after a candle close gate.
- Trend-valid candidates could become indeterminate before signal rules because short data windows raised or were classified as missing signal engine data.

### Candle close gate logic

- The gate used the latest returned candle (`candles[-1]`) as the candidate candle. If that candle was the current in-progress candle, the system waited for close; if data retrieval kept returning current/stale candles, the gate could repeatedly record waiting/failed states with zero passes.
- Added helper logic to select the latest fully closed M5 candle and build the indicator window ending at that candle.
- Boundary behavior is now test-covered before close, exactly at close, and after close.

### Indicator/candle window generation

- Signal stack indicators index recent values such as `iloc[-1]`, `iloc[-4:]`, `iloc[-6:-1]`, and last-five Keltner/candlestick windows.
- Added an explicit minimum closed-window guard before indicator calculation so insufficient candle sets produce `signal_engine_data:missing` diagnostics rather than `IndexError: list index out of range`.

### Diagnostic recording logic

- `strategy_metrics.py` already records blockers, pipeline state, and funnel counts.
- Added canonical diagnostic-name handling so legacy `singal_engine_data` input is stored/exported as `signal_engine_data`.
- Diagnostics remain additive and response-shape compatible.

### Spelling mismatch

- No active source references to `singal_engine_data` were found during inspection.
- A compatibility normalizer was added for persisted or future malformed records that use the misspelling.

## Root Causes Addressed

- Strategy metrics opportunities had an N+1 criteria lookup.
- Strategy metrics indexes did not include composite range/filter patterns.
- Strategy metrics default view made an unnecessary comparison request when Compare mode was off.
- Signal data preparation relied on indexing indicator windows before proving enough closed candles existed.
- Candle-close gating evaluated against the latest candle rather than a deterministic last-closed candle window.
- Legacy diagnostic spelling could fragment metrics if encountered.

## Verification Notes

- Signal regression tests: `python -m pytest tradegumi/tests/test_signal_engine.py -q` passed with 5 tests.
- Strategy metrics regression tests: `python -m pytest tradegumi/tests/test_strategy_metrics.py -q` passed with 41 tests when run outside the sandbox so Python could write temporary SQLite files.
- The metrics suite includes the seeded summary performance test and now includes diagnostic typo normalization.

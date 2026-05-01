# Research: Strategy Metrics

## Finding 1 - Diagnostic Capture Boundary

**Decision**: Add a structured diagnostic result beside the existing `Signal` result instead of changing signal pass/fail behavior.

**Rationale**: Today `SignalEngine.check_symbol()` returns `None` for watchlist skip, no trend, failed mandatory criteria, candle gate, cooldown, and confidence rejection. That makes no-signal periods indistinguishable. A diagnostic result can capture every decision while preserving the current signal contract for alert/execution.

**Alternatives considered**:

- Modify `Signal` to represent both emitted and rejected signals: rejected because it conflates actionable signals with diagnostics and risks weakening Signal Integrity.
- Infer blockers from logs: rejected because logs do not contain complete criterion margins and are harder to aggregate reliably.

## Finding 2 - Storage Format

**Decision**: Store diagnostics in a local SQLite table managed by a new `strategy_metrics.py` module, with JSON-compatible response objects for the dashboard.

**Rationale**: The feature requires date-range queries, criterion aggregation, near-miss counts, blocker ranking, and 90-day retention. SQLite is already used locally for manual trade data, avoids external infrastructure, and is better than JSONL for aggregate queries.

**Alternatives considered**:

- Append-only JSONL only: simple and observable, but expensive and fragile for date-range aggregation and retention pruning.
- Extend `signal_journal.jsonl`: rejected because the journal records emitted signals, while this feature must record non-emitted opportunities too.
- External database: rejected because the project is single-user and constitutionally favors local deployment simplicity.

## Finding 3 - Near-Miss Logic

**Decision**: A near-miss is a rejected opportunity that failed exactly one grading criterion.

**Rationale**: The user selected this definition. It is simple, testable, and directly answers whether one strict criterion prevented a signal.

**Alternatives considered**:

- Minimum total grade: useful for weighted strategies but less direct for strict layer gating.
- Small numeric margin: useful for threshold tuning but requires per-criterion margin semantics before the first implementation.

## Finding 4 - Blocker Ranking

**Decision**: Rank blockers with a combined score balancing blocker frequency, failure margin, and opportunity quality.

**Rationale**: The user selected combined ranking. Frequency alone can overemphasize common but obvious failures; miss distance alone can overemphasize rare outliers. A combined score better identifies criteria worth reviewing first.

**Proposed scoring basis**:

- Frequency component: how often the criterion failed among rejected opportunities.
- Margin component: how close failed values were to threshold, normalized per criterion.
- Quality component: whether the rest of the opportunity was strong enough to be promising.

**Initial formula**:

`combined_score = (frequency_component * 0.40) + (margin_component * 0.30) + (quality_component * 0.30)`

- `frequency_component` is the criterion's blocked count divided by total rejected opportunities.
- `margin_component` is normalized closeness to threshold, with closer misses scoring higher.
- `quality_component` is the average pass rate of all other required criteria on opportunities blocked by this criterion.
- Ties sort by blocked count descending, then criterion name ascending.

**Alternatives considered**:

- Frequency only: easiest to explain but can miss high-impact near-threshold blockers.
- Average miss distance only: useful for calibration but can ignore criteria that matter often.

## Finding 5 - Retention

**Decision**: Retain at least 90 days of diagnostic history by default.

**Rationale**: The user selected 90 days. It supports week-over-week and month-over-month comparison while keeping local storage bounded.

**Alternatives considered**:

- 30 days: lightweight but too short for trend review.
- All local history: maximizes research value but needs pruning controls before data volume is known.

## Finding 6 - Dashboard Shape

**Decision**: Add a dedicated Strategy Metrics page with date range, headline counts, criterion diagnostics, near-miss table, blocker ranking, opportunity drill-down, comparison mode, and export.

**Rationale**: The existing dashboard already has multiple focused views. A dedicated page keeps repeated review ergonomic and avoids overloading the signal journal, which is focused on emitted signals and grading.

**Alternatives considered**:

- Add cards to the main dashboard only: useful for status but insufficient for drill-down and comparison.
- Fold into Signal Journal: rejected because the journal intentionally contains only emitted signals.

## Finding 7 - API Pattern

**Decision**: Add Python backend endpoints for summary/detail/export and Next.js proxy routes under `/api/strategy-metrics`.

**Rationale**: This matches the existing dashboard architecture: Python owns trading data and dashboard API routes proxy browser requests with existing auth behavior.

**Alternatives considered**:

- Static JSON-only dashboard data: would support simple display but not interactive date ranges and comparisons.
- Browser-side aggregation: rejected because downloading 90 days of raw diagnostic records for every review is inefficient.

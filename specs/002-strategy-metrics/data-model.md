# Data Model: Strategy Metrics

## EvaluatedOpportunity

Represents one strategy evaluation for one symbol at one point in time, regardless of whether a signal was emitted.

**Fields**:

- `id`: stable unique identifier.
- `evaluated_at`: timestamp of the evaluation.
- `symbol`: configured trading symbol.
- `timeframe`: primary signal timeframe, usually `M5`.
- `mode`: active operating mode at evaluation time.
- `strategy`: strategy label, default `CTI-v1`.
- `direction`: `BUY`, `SELL`, or `none`.
- `trend`: `Uptrend`, `Downtrend`, `flat`, or `unknown`.
- `final_decision`: `emitted`, `rejected`, `skipped`, or `indeterminate`.
- `decision_reason`: concise reason such as `no_trend`, `criteria_failed`, `confidence_failed`, `cooldown`, `risk_blocked`, `market_closed`, or `engine_error`.
- `confidence`: aggregate confidence when available.
- `failed_criteria_count`: number of failed grading criteria.
- `near_miss`: true when final decision is rejected and exactly one grading criterion failed.
- `data_complete`: true when all expected criteria were evaluated.
- `data_quality_notes`: list of warnings for missing, malformed, or excluded values.
- `threshold_version`: version/hash of relevant strategy thresholds at evaluation time.
- `created_at`: persistence timestamp.

**Relationships**:

- Has many `CriterionResult` rows.
- Appears in zero or one `DiagnosticSummary` result sets.

**Validation Rules**:

- `final_decision` must be one of the allowed states.
- `near_miss` must be false unless `final_decision` is `rejected` and `failed_criteria_count` is exactly 1.
- `symbol`, `evaluated_at`, `final_decision`, and `decision_reason` are required.

## CriterionResult

Represents one grading criterion outcome for an evaluated opportunity.

**Fields**:

- `id`: stable unique identifier.
- `opportunity_id`: parent evaluated opportunity.
- `criterion_name`: stable name such as `trend_1h`, `trend_15m`, `trend_5m`, `stoch_rsi`, `macd`, `keltner`, `candlestick`, `confidence`, `cooldown`, or `risk`.
- `layer`: strategy layer or diagnostic category.
- `measured_value`: numeric or text value captured at evaluation time.
- `threshold_value`: threshold or target used for the decision.
- `threshold_operator`: comparison operator such as `gte`, `lte`, `cross`, or `boolean`.
- `passed`: true, false, or null when not applicable.
- `margin`: numeric distance from threshold when meaningful.
- `normalized_margin`: normalized distance for combined blocker ranking.
- `required`: true for mandatory criteria, false for optional confirmation.
- `blocked_signal`: true when this criterion contributed to rejection.
- `data_quality`: `complete`, `missing`, `malformed`, or `not_applicable`.

**Relationships**:

- Belongs to one `EvaluatedOpportunity`.

**Validation Rules**:

- Required failed criteria must set `blocked_signal` unless another earlier skip prevented evaluation.
- Missing or malformed criterion data must not be counted as pass.

## DiagnosticSummary

Represents aggregated metrics for a selected period.

**Fields**:

- `start_date`: inclusive start timestamp/date.
- `end_date`: exclusive end timestamp/date.
- `total_evaluated`: count of evaluated opportunities.
- `emitted_count`: count of emitted signals.
- `rejected_count`: count of rejected opportunities.
- `skipped_count`: count of skipped opportunities.
- `indeterminate_count`: count of indeterminate opportunities.
- `near_miss_count`: count of near-miss opportunities.
- `criterion_summaries`: list of `CriterionSummary`.
- `top_blockers`: ordered list of `BlockerSummary`.
- `data_quality_warnings`: list of warnings affecting interpretation.

**Validation Rules**:

- Counts must add up to `total_evaluated`.
- Empty periods must return zero counts and a clear no-data warning.

## CriterionSummary

Aggregates one criterion across a date range.

**Fields**:

- `criterion_name`
- `evaluated_count`
- `pass_count`
- `fail_count`
- `pass_rate`
- `fail_rate`
- `near_miss_contribution`
- `average_failure_margin`
- `incomplete_count`

## BlockerSummary

Ranks criteria that blocked otherwise promising opportunities.

**Fields**:

- `criterion_name`
- `blocked_count`
- `frequency_component`
- `margin_component`
- `quality_component`
- `combined_score`
- `example_opportunity_ids`

**Validation Rules**:

- `combined_score` must be deterministic for the same input data.
- Ranking ties must use `blocked_count` and criterion name as stable tie-breakers.

## ComparisonPeriod

Represents a before/after or period-over-period comparison.

**Fields**:

- `baseline`: `DiagnosticSummary`.
- `comparison`: `DiagnosticSummary`.
- `deltas`: differences for evaluated count, signal count, near-miss count, rejected count, and top blocker rank.

## State Transitions

```text
evaluating -> emitted
evaluating -> rejected
evaluating -> skipped
evaluating -> indeterminate
```

Diagnostics are append-only after creation except for retention pruning. Strategy threshold changes create new `threshold_version` values rather than rewriting old records.

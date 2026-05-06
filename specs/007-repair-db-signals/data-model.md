# Data Model: Repair DB-backed page performance and signal pipeline progression

## DB-backed Page View

**Purpose**: Represents an operator-facing dashboard or journal page that reads persisted history or metrics.

**Fields/attributes**:
- Page name: strategy metrics, signal journal, manual trade journal, dashboard trade history, or related page.
- Default filters: date range, symbol, status, strategy outcome, or page-specific defaults.
- Result bounds: default limit, offset/page cursor, or export/full-history mode.
- Timing measurement: page/API path, elapsed time, row count, and optional query label.

**Validation rules**:
- Default views must avoid unbounded full-history reads.
- Export/full-history reads must be explicit and documented.
- Response shape must remain compatible unless a documented exception is made.

## Strategy Metrics

**Purpose**: Stores and summarizes opportunity evaluation, signal-stage diagnostics, and aggregate funnel counts.

**Fields/attributes**:
- Opportunity identity and timestamp.
- Symbol, timeframe, trend direction, decision outcome, and decision reason.
- Criteria diagnostics including trend, signal data, candle gate, rules evaluated, and emitted/rejected states.
- Aggregated counts including total evaluated, signal-rule evaluated, signal emitted, incomplete signal data, candle gate pass/fail/waiting, and indeterminate.

**Validation rules**:
- `signal_engine_data` is the canonical diagnostic name.
- Legacy misspellings must be normalized or interpreted without fragmenting metrics.
- Diagnostics must be additive/backward-compatible for existing exports.

## Signal Candidate

**Purpose**: Represents a potential trade opportunity moving through the strategy pipeline.

**Fields/attributes**:
- Symbol and timeframe.
- Direction and trend state.
- Trend criteria results.
- Signal engine input state.
- Candle gate state.
- Rule evaluation state and final emitted/rejected/indeterminate outcome.

**State transitions**:
```text
trend_detected
  -> signal_data_prepared
  -> candle_gate_waiting
  -> candle_gate_passed
  -> signal_rules_evaluated
  -> signal_emitted | signal_rejected
```

**Alternate transitions**:
```text
trend_detected
  -> signal_data_missing
  -> indeterminate_with_diagnostics

signal_data_prepared
  -> candle_gate_waiting
  -> eligible_for_later_closed_candle_evaluation
```

## Signal Engine Data

**Purpose**: Provides the complete candle and indicator context needed for candle-close gating and signal rules.

**Fields/attributes**:
- Candidate symbol/timeframe/direction.
- Candles available and candles required.
- Last closed candle.
- Complete indicator window.
- Missing input name and diagnostic state when incomplete.

**Validation rules**:
- Zero, insufficient, and exactly sufficient candle sets must be handled explicitly.
- Missing data must include a precise reason and must not raise indexing errors.
- Current in-progress candle must not be treated as the last closed candle.

## Candle Close Gate

**Purpose**: Determines whether signal rules may evaluate for a fully closed M5 candle.

**Fields/attributes**:
- Candidate candle open time.
- Candidate candle close time.
- Evaluation time.
- Timezone-aware timeframe boundary.
- Gate state: passed, waiting, failed, or diagnostic error.
- Seconds until close when waiting.

**Validation rules**:
- Before close: gate waits and keeps candidate eligible.
- Exact close: gate passes.
- After close: gate passes for the relevant last closed candle.
- Naive or stale times must be normalized or rejected diagnostically.

## Diagnostic Event

**Purpose**: Records why a candidate progressed, waited, failed data preparation, evaluated rules, emitted, rejected, or became indeterminate.

**Fields/attributes**:
- Stage name.
- Diagnostic state.
- Reason code.
- Missing input, error type, or gate rule where applicable.
- Counts or timing context needed for troubleshooting.

**Validation rules**:
- Diagnostics collection must never break signal evaluation.
- Broad catch-all masking is not allowed; explicit guards should handle expected missing inputs.

## Performance Measurement

**Purpose**: Captures before/after evidence for slow data paths.

**Fields/attributes**:
- Measured page or endpoint.
- Data volume context.
- Elapsed time.
- Row count or result size.
- Query/index observation when relevant.
- Before/after note or repeatable command.

**Validation rules**:
- Measurement must be lightweight and reproducible locally.
- Measurements must avoid secrets and raw credential-bearing payloads.

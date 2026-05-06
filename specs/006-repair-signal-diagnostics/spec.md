# Feature Specification: Repair Signal Pipeline Diagnostics

**Feature Branch**: `006-repair-signal-diagnostics`  
**Created**: 2026-05-06  
**Status**: Draft  
**Input**: User description: "Repair signal pipeline diagnostics and unblock valid candidate evaluation"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Attribute Missing Signal Data (Priority: P1)

As the strategy operator, I need directional trend candidates that cannot evaluate the signal stack to be classified with explicit data-quality blockers so the next export shows whether valid candidates are dying because required inputs are missing.

**Why this priority**: Missing `signal_engine_data` accounts for thousands of indeterminate opportunities and currently hides the true blocker behind generic or empty diagnostics.

**Independent Test**: Use an opportunity where 1h, 15m, and 5m trend criteria all pass with aligned direction, but one required signal-stack input is unavailable. The export must keep the final decision indeterminate and identify the missing input as the blocker.

**Acceptance Scenarios**:

1. **Given** all required trend strengths pass and directions agree, **When** the signal stack cannot evaluate because required data is missing, **Then** the opportunity is indeterminate with a specific `decision_reason`, populated `first_blocker`, populated `all_blockers`, populated `blocking_layer`, and `signal_engine_data.blocked_signal = true`.
2. **Given** signal stack evaluation raises or would previously surface "list index out of range", **When** metrics are exported, **Then** the export contains a structured missing-input reason and compact debugging context instead of only the raw exception text.

---

### User Story 2 - Clarify Candle Close Gate Behavior (Priority: P2)

As the strategy operator, I need each candle close gate decision to explain what was checked and whether the candidate was waiting, failed, or passed so open-candle evaluation is not mistaken for a strategy rejection or near miss.

**Why this priority**: The latest export shows 1,412 candle close gate failures, 0 passes, and all near misses tied to this gate, making rejected and near-miss metrics unreliable.

**Independent Test**: Evaluate one candidate before candle close and one candidate after candle close. The before-close case must be classified according to the documented gate rule, and the after-close case must include timing fields and a pass or explicit failure reason.

**Acceptance Scenarios**:

1. **Given** a trend candidate reaches candle-close gating before its candle has closed, **When** the export is produced, **Then** the gate diagnostic includes current time, candle open time, candle close time, seconds until close, timeframe, gate rule, margin units, and a specific reason such as `candle_close_gate:waiting_for_close`.
2. **Given** a trend candidate is evaluated after the relevant candle has closed, **When** the gate passes or fails, **Then** the export includes seconds since close, the gate rule, margin units, and a specific pass or failure reason.
3. **Given** a candidate is merely waiting for a candle to close, **When** summary counts are calculated, **Then** it is not automatically counted as a near miss unless it satisfies the documented near-miss rule.

---

### User Story 3 - Make Pipeline Counts Explainable (Priority: P3)

As the strategy operator, I need the export summary to show a clear funnel from total evaluations through trend, data completeness, candle-close gating, signal rules, rejection, emission, and indeterminate outcomes so tuning decisions are based on trustworthy classifications.

**Why this priority**: The current totals show zero emitted signals even though valid trend candidates exist, but the summary does not separate trend skips, data-quality indeterminates, gate waiting/failures, rule rejections, and near misses.

**Independent Test**: Generate an export containing examples of trend skip, missing signal data, candle-close waiting or failure, signal rule rejection, emitted signal, and indeterminate outcome. The funnel, top blockers, and near-miss summaries must reconcile with the opportunity-level diagnostics.

**Acceptance Scenarios**:

1. **Given** opportunities with data-quality blockers, trend blockers, candle-close gate blockers, and signal rule blockers, **When** top blockers are exported, **Then** stable blocker names include data-quality blockers, candle-close subreasons, and existing trend blockers.
2. **Given** near misses are present, **When** summary metrics are exported, **Then** `near_miss_count` is explainable by `near_miss_reason` summary counts and does not include ordinary open-candle waiting.
3. **Given** threshold version counts include unknown versions, **When** the export is produced, **Then** unknown threshold versions include a practical unknown reason when available.

### Edge Cases

- A required criterion fails but is explicitly non-blocking for the current decision path; the criterion must explain why `blocked_signal` is false.
- Multiple blockers occur on the same opportunity; `first_blocker` must identify the first blocker in pipeline order while `all_blockers` retains all applicable stable blocker names.
- Missing data prevents a criterion from producing a true or false pass result; the criterion must provide an explicit diagnostic state rather than silently returning `passed = null` with `expected_pass = true`.
- The candle close gate lacks one or more timestamps; the opportunity must surface a structured missing-timing-data blocker rather than producing misleading margin values.
- Existing exported JSON consumers must continue to parse exports with added fields.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The metrics export MUST distinguish these pipeline states: trend skipped because no valid trend exists, trend candidate found but signal stack data missing, trend candidate found but candle close gate failed or is waiting, trend candidate found and signal stack evaluated, signal rejected by a strategy rule, and signal emitted.
- **FR-002**: Every indeterminate opportunity caused by missing or incomplete signal data MUST keep `final_decision = indeterminate` and include a specific `decision_reason`, populated `first_blocker`, populated `all_blockers`, and populated `blocking_layer`.
- **FR-003**: A required criterion with missing data that prevents signal progression MUST set `blocked_signal = true` and identify the missing data-quality reason.
- **FR-004**: `signal_engine_data` diagnostics MUST replace or supplement generic "list index out of range" failures with structured reasons naming the missing input category, such as candles, indicators, last closed candle, current candle, ATR, stochastic RSI, price data, or another required signal-stack input.
- **FR-005**: `signal_engine_data` diagnostics MUST include compact context sufficient to debug the missing source without dumping excessive raw candle data.
- **FR-006**: An exported required criterion MUST NOT show `passed = null` while `expected_pass = true` unless it also includes an explicit diagnostic state explaining why evaluation was impossible.
- **FR-007**: `candle_close_gate` diagnostics MUST include current time, candle open time, candle close time, seconds until close or seconds since close, timeframe, gate rule, margin, margin units, normalized margin, and a specific gate reason whenever those values are available.
- **FR-008**: The export MUST document whether `candle_close_gate` is intended to pass only after the relevant candle has closed and whether an open candle is rejected, skipped, deferred, or treated as waiting.
- **FR-009**: Candle-close evaluations that occur before the candle has closed MUST be recorded as waiting for candle close, deferred, skipped, or another explicit non-misleading state unless the project intentionally defines them as rejection.
- **FR-010**: `near_miss_count` MUST only include opportunities that satisfy a documented near-miss rule and MUST NOT automatically count every candle-close gate failure.
- **FR-011**: The export MUST include a `near_miss_reason` field or equivalent opportunity-level reason and summary counts by near-miss reason.
- **FR-012**: Rejected opportunities MUST clearly separate rule blockers from open-candle waiting and data-quality indeterminate outcomes.
- **FR-013**: Any required trend, signal-engine-data, candle-close-gate, or later signal-rule criterion failure that blocks progression MUST set `blocked_signal = true`.
- **FR-014**: Any failed criterion that does not block progression MUST explain why it is non-blocking.
- **FR-015**: `top_blockers` MUST include stable names for data-quality blockers such as `signal_engine_data:missing`, candle-close subreasons such as `candle_close_gate:waiting_for_close` or `candle_close_gate:stale_candle`, and existing trend blockers.
- **FR-016**: Existing `threshold_version_counts` output MUST remain present, and unknown threshold versions SHOULD include `threshold_version_unknown_reason` when practical.
- **FR-017**: The export MUST include a summary funnel with counts for total evaluated, trend skipped, trend candidate found, signal data complete, signal data missing, candle close gate passed, candle close gate waiting or failed, signal rules evaluated, signal rejected, signal emitted, and indeterminate.
- **FR-018**: Metrics documentation MUST define skipped, rejected, indeterminate, near miss, candle close gate, signal engine data, blocked signal, first blocker, all blockers, and blocking layer.
- **FR-019**: The feature MUST NOT tune trend thresholds, loosen trend rules, change entry strategy to force trades, change trade execution, optimize profitability, or add broad architecture unrelated to diagnostics, data completeness, or gating.
- **FR-020**: Existing metrics exports MUST remain JSON-compatible, with new information added through additive fields or compatible value refinements.

### Key Entities *(include if feature involves data)*

- **Pipeline State**: The stage-level classification for an evaluated opportunity, including trend skip, trend candidate, signal data completeness, candle-close gate result, signal-rule result, rejection, emission, and indeterminate status.
- **Criterion Diagnostic**: A single requirement evaluation with required status, expected pass state, actual pass state, blocker status, data-quality status, diagnostic reason, and compact context.
- **Blocker**: A stable reason that prevents an opportunity from progressing, including the first blocker in pipeline order and all blockers observed for the opportunity.
- **Candle Close Gate Diagnostic**: Timing and rule evidence for the candle-close gate, including current time, candle open and close times, seconds until or since close, timeframe, gate rule, margins, units, normalized margin, and reason.
- **Near Miss Classification**: An opportunity-level and summary-level explanation of why a candidate is counted as near miss, separate from open-candle waiting and indeterminate data-quality states.
- **Summary Funnel**: Aggregate counts that reconcile total evaluated opportunities through the signal pipeline stages and final outcomes.
- **Threshold Version Summary**: Counts by threshold version plus practical reasons for unknown versions when available.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a validation export with missing signal stack data, 100% of indeterminate missing-data opportunities include populated `decision_reason`, `first_blocker`, `all_blockers`, `blocking_layer`, and a blocking required criterion.
- **SC-002**: In a validation export with candle-close gate outcomes, 100% of candle-close gate diagnostics include the available timing fields, timeframe, gate rule, margin units, and a specific gate reason.
- **SC-003**: `near_miss_count` reconciles exactly to the sum of near-miss reason summary counts in every generated export.
- **SC-004**: `rejected_count` excludes opportunities classified as waiting for candle close, skipped for no valid trend, or indeterminate due to missing required data.
- **SC-005**: The summary funnel reconciles with total evaluated opportunities and makes the largest dropout stage identifiable without inspecting individual records.
- **SC-006**: Existing JSON export consumers can parse exports after the change without requiring removal or renaming of existing fields.
- **SC-007**: Automated tests cover missing signal data blocker assignment, candle-close before-close behavior, candle-close after-close behavior, near-miss classification, blocked-signal assignment, top-blocker aggregation, summary funnel counts, and threshold-version unknown handling if implemented.

## Assumptions

- The primary user is the strategy operator reviewing JSON metrics exports before deciding whether any strategy parameters should be tuned.
- Open-candle evaluation should be classified as waiting or deferred unless existing project behavior explicitly documents it as a rejection.
- `blocking_layer` may use the existing project naming if it already distinguishes `data_quality` and `signal_engine`; otherwise the closest existing layer name should be used consistently.
- Missing signal input context should summarize source, timeframe, expected input, observed availability, and compact counts or timestamps rather than raw candle arrays.
- Threshold version unknown reasons are best effort because some historical records may not contain enough provenance to explain the unknown value.

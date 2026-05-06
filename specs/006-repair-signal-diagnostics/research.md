# Research: Repair Signal Pipeline Diagnostics

## Decision: Treat Open Candle Evaluation As Waiting, Not Near Miss

**Rationale**: The observed export has every near miss tied to `candle_close_gate`, with 0 gate passes and a large average failure margin. The most conservative diagnostic repair is to classify before-close checks as `candle_close_gate:waiting_for_close` unless existing code explicitly proves the gate means rejection.

**Alternatives considered**: Keep current rejected near-miss behavior, but that preserves the misleading metric. Disable the gate, but that changes strategy behavior and is out of scope.

## Decision: Keep `final_decision = indeterminate` For Missing Signal Stack Data

**Rationale**: Missing candles, indicators, last closed candle, current candle, ATR, stochastic RSI, or price data means the strategy did not actually reject a valid candidate. It cannot evaluate, so indeterminate with a data-quality blocker is the truthful classification.

**Alternatives considered**: Count missing data as skipped or rejected. Both would distort strategy tuning decisions and hide infrastructure/data completeness issues.

## Decision: Add Stable Blocker Reasons Rather Than Raw Exception Strings

**Rationale**: Stable names such as `signal_engine_data:missing`, `signal_engine_data:missing:last_closed_candle`, and `candle_close_gate:waiting_for_close` allow reports to be compared over time. Raw exception strings can remain compact context, but not the primary blocker name.

**Alternatives considered**: Export raw exceptions only. This is hard to aggregate, unstable across code paths, and currently produces unhelpful "list index out of range" noise.

## Decision: Use Additive JSON Fields And Additive SQLite Columns

**Rationale**: Existing consumers already depend on the metrics export. The feature can add diagnostic context, near-miss reasons, funnel counts, and threshold unknown reasons without removing or renaming current fields.

**Alternatives considered**: Replace the export schema. This would break compatibility and expand scope beyond diagnostic repair.

## Decision: Aggregate Top Blockers From Rejected, Skipped, And Indeterminate Outcomes With Blockers

**Rationale**: Data-quality blockers currently vanish from top blockers because aggregation only considers rejected and skipped rows. Including indeterminate opportunities with populated blockers makes missing signal data visible without reclassifying them as rejections.

**Alternatives considered**: Keep top blockers limited to rejected/skipped outcomes. This would fail the primary need to expose `signal_engine_data:missing`.

## Decision: Preserve Threshold Version Counts And Explain Unknowns Best Effort

**Rationale**: The export already has `threshold_version_counts`, and old rows may legitimately contain `unknown`. A separate reason summary clarifies whether unknown means legacy record, missing diagnostic provenance, or unavailable threshold metadata.

**Alternatives considered**: Drop unknown rows or force a version. Both would make historical reporting less honest.

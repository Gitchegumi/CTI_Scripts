# Research: Signal Setup Outcomes

## Decision: Use Additive Journal Outcome Fields

Add the requested setup/outcome fields to new Signal Journal records and CSV exports while leaving legacy records readable with blank or defaulted display values.

**Rationale**: The Signal Journal is the permanent emitted-signal evidence. Additive fields preserve historical evidence and let operators compare old and new records without a migration step.

**Alternatives considered**:

- Rewrite historical JSONL records: rejected because it mutates existing evidence and violates the feature boundary.
- Store outcome fields only in strategy metrics DB: rejected because journal review/export must explain each emitted signal outcome.

## Decision: Group Setups by Symbol, Direction, Strategy, and Time Window

Create `setup_group_id` from same-symbol, same-direction, same-strategy records inside the active grouping window. Default the window to 10 minutes and expose it via configuration.

**Rationale**: The user explicitly needs repeated emissions from one market condition grouped so only the first active setup is a tradable opportunity. The 10-minute default is specified in the feature and is longer than the current 5-minute cooldown, so it catches repeated setup emissions that can still occur after cooldown.

**Alternatives considered**:

- Group by symbol and direction only: rejected because different strategies may intentionally produce independent setups.
- Group by signal ID only: rejected because it cannot identify duplicates.
- Use a fixed hardcoded window: rejected because the spec requires configurability.

## Decision: Treat Entry Tolerance as Existing Strategy/Journal Context

Record `entry_valid_at_signal`, absolute `entry_miss_distance`, ATR-normalized distance when ATR is available, and `late_signal` using the recommended entry, signal-time price, ATR, and existing valid-entry tolerance context.

**Rationale**: The constitution forbids casual strategy retuning. This feature should surface whether the signal was usable at signal time, not invent new entry thresholds.

**Alternatives considered**:

- Add a new strategy threshold for entry tolerance: rejected for planning because it would change trading semantics unless separately governed.
- Only record a boolean: rejected because optimization needs magnitude via absolute and ATR-normalized distance.

## Decision: Count Signal Age in M5 Bars

Record `signal_age_bars` as the count of M5 bars since the setup condition first became true, using existing signal diagnostic timing context when available and a safe default for unavailable legacy context.

**Rationale**: The feature names M5 bars specifically. Using bars rather than elapsed minutes makes the value comparable across market pauses and candle-close-gated signal evaluation.

**Alternatives considered**:

- Store elapsed seconds only: rejected because it does not satisfy the requested field.
- Infer age from wall-clock time alone: rejected because M5 bar count is the user-facing measure.

## Decision: Introduce Normalized `trade_grade` Alongside Existing Journal Grade

Use `trade_grade` for setup outcome classification with allowed values `TP_HIT`, `SL_HIT`, `BE`, `MISSED_ENTRY`, `LATE_SIGNAL`, `DUPLICATE`, `INVALID`, and `PENDING`. Preserve existing `grade` behavior during transition and map dashboard/manual actions to the new normalized grade where applicable.

**Rationale**: Existing journal grade values include `MANUAL_CLOSE` and `EXPIRED`, which do not match the requested strategy-outcome vocabulary. A separate normalized field avoids breaking current review workflows while enabling cleaner analysis.

**Alternatives considered**:

- Replace `grade` immediately: rejected because existing dashboard, Discord, export, and tests rely on current grade values.
- Keep only old grades: rejected because the new required values need distinct meanings.

## Decision: Gate Strategy Opportunity Counts on `usable_for_strategy_stats`

Strategy metrics must not count emitted signals as trade opportunities unless `usable_for_strategy_stats` is true. Existing emitted-count diagnostics can remain as signal-emission counts, but opportunity-count language must use the eligibility flag.

**Rationale**: This directly satisfies the user's rule and prevents duplicates, missed entries, stale signals, late unusable signals, and invalidated signals from inflating opportunity analysis.

**Alternatives considered**:

- Continue using `final_decision = emitted` as opportunity count: rejected because emitted signal volume is not the same as tradable setup volume.
- Exclude only duplicates: rejected because the spec also excludes missed, stale, and invalid signals.

## Decision: Manual Invalidation Updates Eligibility and Trade Grade

Manual invalidation must set `trade_grade` to `INVALID`, set `usable_for_strategy_stats` to false, and preserve the original signal evidence plus notes.

**Rationale**: Operators need a clean way to remove bad or stale signals from stats without deleting evidence.

**Alternatives considered**:

- Purge invalid signals: rejected because deletion loses evidence.
- Notes-only invalidation: rejected because stats need a structured exclusion flag.

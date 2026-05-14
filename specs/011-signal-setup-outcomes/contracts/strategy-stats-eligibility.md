# Contract: Strategy Stats Eligibility

## Opportunity Counting Rule

Strategy statistics must count trade opportunities with this rule:

```text
trade_opportunity_count = count(signal_journal_records where usable_for_strategy_stats is true)
```

Raw emitted signal count may continue to be reported separately, but emitted count must not be described or used as trade opportunity count unless every counted record is eligible.

## Required Summary Fields

Strategy metrics responses or dashboard summaries that currently expose opportunity-like counts must distinguish:

| Field | Meaning |
| --- | --- |
| `emitted_count` | Number of raw emitted signals or emitted opportunities |
| `trade_opportunity_count` | Number of records eligible for strategy stats |
| `stats_excluded_count` | Number of emitted signals excluded from strategy trade opportunity stats |

## Exclusion Reasons

When available, stats summaries should expose counts by exclusion reason:

```json
{
  "stats_exclusion_counts": {
    "duplicate_setup": 4,
    "missed_entry": 2,
    "late_signal": 1,
    "stale_signal": 1,
    "manual_invalidated": 1
  }
}
```

## Legacy Compatibility

Records without `usable_for_strategy_stats` must not silently inflate trade opportunity counts. They may be:

- Reported as unknown eligibility.
- Excluded from trade opportunity counts until re-evaluated.
- Shown in raw emitted counts for historical context.

The selected behavior must be documented in tests and user-facing docs.

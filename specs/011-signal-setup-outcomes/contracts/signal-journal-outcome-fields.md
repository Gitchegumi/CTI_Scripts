# Contract: Signal Journal Outcome Fields

## Journal Append Contract

Every newly appended Signal Journal record must include these fields:

| Field | Contract |
| --- | --- |
| `setup_group_id` | Non-empty string identifying the active setup group |
| `is_duplicate_setup` | Boolean |
| `entry_valid_at_signal` | Boolean when entry context is available; false when entry is known to be invalid |
| `entry_miss_distance` | Object with `absolute`, `atr_normalized`, and `units` keys when entry distance can be evaluated |
| `signal_age_bars` | Integer greater than or equal to 0 |
| `late_signal` | Boolean |
| `usable_for_strategy_stats` | Boolean |
| `trade_grade` | One of `TP_HIT`, `SL_HIT`, `BE`, `MISSED_ENTRY`, `LATE_SIGNAL`, `DUPLICATE`, `INVALID`, `PENDING` |

## Duplicate Setup Contract

Given existing active record:

```json
{
  "symbol": "EURUSD",
  "direction": "BUY",
  "strategy": "CTI-v1",
  "signal_timestamp": "2026-05-14T14:00:00Z",
  "setup_group_id": "setup-1",
  "is_duplicate_setup": false
}
```

When a new same-symbol, same-direction, same-strategy signal is journaled at `2026-05-14T14:07:00Z` with the default 10-minute window, then the new record must include:

```json
{
  "setup_group_id": "setup-1",
  "is_duplicate_setup": true,
  "usable_for_strategy_stats": false,
  "trade_grade": "DUPLICATE"
}
```

When a new same-symbol, same-direction, same-strategy signal is journaled at `2026-05-14T14:10:00Z` or later, it starts a new setup group unless the configured boundary rule is changed during implementation and documented in tests.

## Entry Validity Contract

When signal-time price remains inside the valid entry tolerance:

```json
{
  "entry_valid_at_signal": true,
  "late_signal": false,
  "trade_grade": "PENDING",
  "usable_for_strategy_stats": true
}
```

When signal-time price has already exceeded the valid entry tolerance:

```json
{
  "entry_valid_at_signal": false,
  "late_signal": true,
  "trade_grade": "LATE_SIGNAL",
  "usable_for_strategy_stats": false
}
```

## Export Contract

Signal Journal CSV export must include stable columns for:

```text
setup_group_id
is_duplicate_setup
entry_valid_at_signal
entry_miss_distance
signal_age_bars
late_signal
usable_for_strategy_stats
trade_grade
stats_exclusion_reason
```

Nested `entry_miss_distance` may be JSON-encoded in a deterministic flat CSV cell.

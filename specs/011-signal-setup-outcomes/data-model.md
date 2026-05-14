# Data Model: Signal Setup Outcomes

## Signal Journal Record

Represents one emitted signal in the permanent Signal Journal JSONL file.

| Field | Type | Required for New Records | Notes |
| --- | --- | --- | --- |
| `signal_id` | string | Yes | Existing emitted signal identifier |
| `symbol` | string | Yes | Used in setup grouping |
| `direction` | string | Yes | Used in setup grouping |
| `strategy` | string | Yes | Used in setup grouping; falls back to existing strategy identity |
| `entry_price` | number | Yes when available | Recommended entry for distance calculation |
| `signal_timestamp` | timestamp | Yes | Signal-time timestamp for grouping and age calculations |
| `setup_group_id` | string | Yes | Stable group ID shared by duplicate setup emissions |
| `is_duplicate_setup` | boolean | Yes | True when this signal joins an existing active setup group |
| `entry_valid_at_signal` | boolean | Yes when entry can be evaluated | True when signal-time price is inside valid entry tolerance |
| `entry_miss_distance` | object | Yes when entry can be evaluated | Contains absolute and ATR-normalized distance |
| `signal_age_bars` | integer | Yes | M5 bars since setup condition first became true; 0 allowed |
| `late_signal` | boolean | Yes | True when price already moved beyond valid entry tolerance |
| `usable_for_strategy_stats` | boolean | Yes | Sole gate for trade-opportunity statistics |
| `trade_grade` | enum | Yes | One of the normalized trade grades |
| `stats_exclusion_reason` | string | Conditional | Explains false eligibility when available |
| `grade` | enum/string | Existing | Existing dashboard/manual grade retained for compatibility |
| `notes` | string | Existing | Operator notes, including manual invalidation rationale |

### `entry_miss_distance`

| Field | Type | Notes |
| --- | --- | --- |
| `absolute` | number | Absolute price distance between signal-time price and suggested entry |
| `atr_normalized` | number or null | `absolute / ATR` when ATR is finite and greater than zero |
| `units` | string | Price units for the absolute distance |

## Setup Group

Represents a logical tradable setup shared by repeated same-context emissions.

| Field | Type | Notes |
| --- | --- | --- |
| `setup_group_id` | string | Deterministic enough for repeated records in the active window |
| `symbol` | string | Grouping key |
| `direction` | string | Grouping key |
| `strategy` | string | Grouping key |
| `opened_at` | timestamp | Timestamp of the first active setup signal |
| `expires_at` | timestamp | `opened_at` plus configured setup grouping window |
| `first_signal_id` | string | First signal in group; not a duplicate |

Validation rules:

- Signals with the same symbol, direction, and strategy inside the active window share the same `setup_group_id`.
- Signals at or after the end of an expired grouping window start a new group.
- Matching symbol and direction with a different strategy starts a different group.

## Strategy Stats Eligibility

Represents whether a signal may be counted as a trade opportunity.

| Field | Type | Notes |
| --- | --- | --- |
| `usable_for_strategy_stats` | boolean | True only for usable tradable setups |
| `stats_exclusion_reason` | enum/string | Suggested values: `duplicate_setup`, `missed_entry`, `late_signal`, `stale_signal`, `manual_invalidated`, `missing_entry_context` |

Rules:

- Duplicate setup signals are not usable.
- Missed entries, late unusable signals, stale signals, and manually invalidated signals are not usable.
- Strategy opportunity statistics count only records where `usable_for_strategy_stats` is true.
- Raw emitted signal counts may still exist, but they must not be labeled as trade opportunities unless eligible.

## Trade Grade

Normalized outcome state for setup review and analysis.

Allowed values:

```text
TP_HIT
SL_HIT
BE
MISSED_ENTRY
LATE_SIGNAL
DUPLICATE
INVALID
PENDING
```

State transitions:

```text
PENDING -> TP_HIT
PENDING -> SL_HIT
PENDING -> BE
PENDING -> MISSED_ENTRY
PENDING -> LATE_SIGNAL
PENDING -> INVALID
PENDING -> DUPLICATE
TP_HIT | SL_HIT | BE | MISSED_ENTRY | LATE_SIGNAL | DUPLICATE -> INVALID
INVALID -> PENDING only through explicit reset
```

Transition notes:

- Duplicate setup records use `DUPLICATE`.
- Entry-invalid records use `MISSED_ENTRY` or `LATE_SIGNAL` based on lateness classification.
- Manual invalidation uses `INVALID` and sets eligibility false.
- Unresolved usable records remain `PENDING`.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| Setup grouping window | 10 minutes | Determines how long a same-symbol, same-direction, same-strategy setup group remains active |

The setting must be environment/config driven and documented without changing signal thresholds.

## Legacy Records

Legacy Signal Journal records may omit all new fields. Readers, exports, and dashboard views must:

- Preserve legacy records without rewriting them.
- Treat missing `usable_for_strategy_stats` as unknown rather than true for opportunity counting.
- Display blank or fallback values for missing setup fields.
- Avoid failing CSV export, dashboard load, or journal review when fields are absent.

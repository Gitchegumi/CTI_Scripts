# Contract: Signal Journal UI

## Journal Record Display

The journal page should be able to render records with these optional fields:

| Field | Display Expectation |
| --- | --- |
| `setup_group_id` | Available for inspection/export; may be shown as compact setup identity |
| `is_duplicate_setup` | Duplicate setup indicator |
| `entry_valid_at_signal` | Entry-valid or missed/late state |
| `entry_miss_distance` | Absolute and ATR-normalized miss distance when available |
| `signal_age_bars` | M5 bar age value |
| `late_signal` | Late signal indicator |
| `usable_for_strategy_stats` | Whether the record contributes to strategy stats |
| `trade_grade` | Normalized grade badge/filter value |
| `stats_exclusion_reason` | Human-readable explanation when excluded |

## Manual Invalidation

When an operator invalidates a signal:

- `trade_grade` becomes `INVALID`.
- `usable_for_strategy_stats` becomes false.
- Original signal evidence remains visible.
- Notes remain editable.

## Legacy Records

The UI must not fail when records lack setup outcome fields. Missing fields should render as blank, unknown, or legacy state without implying the record is usable for strategy stats.

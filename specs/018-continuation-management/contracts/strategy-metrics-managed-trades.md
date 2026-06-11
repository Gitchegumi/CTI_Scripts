# Contract: Strategy Metrics Managed Trades

## Summary Fields

Strategy metrics export must include these additive fields:

| Field | Type | Description |
| --- | --- | --- |
| `pullback_entries_opened` | integer | Number of pullback-originated trade entries |
| `continuation_management_events_observed` | integer | Continuation events evaluated for lifecycle management |
| `continuation_management_events_accepted` | integer | Management events that changed SL or TP |
| `continuation_management_events_rejected` | integer | Management events retained with rejection reasons |
| `tp_extension_count` | integer | Accepted TP extensions |
| `sl_tighten_count` | integer | Accepted SL tightenings |
| `break_even_move_count` | integer | SL moves to entry or equivalent break-even |
| `profit_protected_sl_win_count` | integer | SL exits beyond entry counted as wins |
| `opposite_direction_continuation_warning_count` | integer | Opposite-direction continuation warnings during active trades |
| `average_r_captured` | number or null | Average captured R over closed managed trades |
| `max_favorable_excursion_before_exit` | number or null | Maximum favorable excursion observed before exit |
| `managed_vs_original_result_delta` | object | Counts of improved, unchanged, worsened, and unknown comparisons |

## Export Requirements

- Fields are present in JSON exports even when zero.
- CSV opportunity rows include lifecycle identifiers where applicable.
- Continuation-only samples without pullback entries report zero pullback entries opened and zero continuation-created trade entries.
- Existing prime suppression metrics remain present.

## Acceptance Samples

- Issue #100 sample with 92 continuation-only rows: `pullback_entries_opened=0`.
- Current-week sample with 101 continuation-only rows: `pullback_entries_opened=0`.
- Mixed sample with active trades: each continuation is accepted, rejected, or warning-counted exactly once.

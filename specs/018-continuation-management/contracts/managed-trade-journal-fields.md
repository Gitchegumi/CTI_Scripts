# Contract: Managed Trade Journal Fields

## Scope

Journal records and CSV exports must distinguish lifecycle roles without breaking existing signal-review workflows.

## Additive Fields

| Field | Type | Applies To | Description |
| --- | --- | --- | --- |
| `lifecycle_role` | string | All new lifecycle records | `entry`, `management`, `outcome`, `warning`, or `legacy_signal` |
| `trade_id` | string or null | Entry, management, outcome | Stable lifecycle identifier |
| `entry_signal_id` | string or null | Entry, management, outcome | Pullback signal that opened the trade |
| `entry_signal_type` | string or null | Entry, management, outcome | `pullback` or `high_value_pullback` |
| `management_event_id` | string or null | Management | Unique continuation-management identifier |
| `source_signal_id` | string or null | Management | Continuation signal evaluated for management |
| `source_signal_type` | string or null | Management | `continuation` |
| `management_accepted` | boolean or null | Management | Whether SL/TP changed |
| `management_reason` | string or null | Management | Accepted/rejected reason |
| `management_rejection_reason` | string or null | Management | Required when rejected |
| `old_stop_loss` | number or null | Management | SL before event |
| `new_stop_loss` | number or null | Management | SL after event |
| `old_take_profit` | number or null | Management | TP before event |
| `new_take_profit` | number or null | Management | TP after event |
| `current_stop_loss` | number or null | Entry/outcome/latest state | Current managed SL |
| `current_take_profit` | number or null | Entry/outcome/latest state | Current managed TP |
| `managed_exit_reason` | string or null | Outcome | Final lifecycle exit reason |
| `managed_result_category` | string or null | Outcome | `win`, `loss`, or `breakeven` |
| `captured_r` | number or null | Outcome | Signed R captured |

## CSV Requirements

- Export headers include lifecycle fields even when values are blank for legacy records.
- Entry rows must be filterable separately from management rows through existing export data.
- Management rows must include enough fields to reconstruct old/new SL/TP changes.
- Continuation-only samples with no linked pullback entry must not emit lifecycle `entry` rows.

## Compatibility

- Legacy records missing `lifecycle_role` display as `legacy_signal`.
- Existing grade, outcome, prime, and pullback fields remain unchanged.

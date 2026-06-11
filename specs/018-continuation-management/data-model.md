# Data Model: Continuation Management Events

## Trade Entry Event

Represents a pullback-originated trade opening event.

| Field | Type | Required for New Records | Notes |
| --- | --- | --- | --- |
| `trade_id` | string | Yes | Stable lifecycle identifier, generated when a pullback opens a trade |
| `entry_signal_id` | string | Yes | Signal that opened the trade |
| `entry_signal_type` | string | Yes | Must be `pullback` or `high_value_pullback`; continuation is not an entry type |
| `symbol` | string | Yes | Trading symbol |
| `direction` | string | Yes | Buy/uptrend or sell/downtrend direction |
| `entry_price` | number | Yes | Entry level from signal |
| `initial_stop_loss` | number | Yes | Stop loss at entry |
| `initial_take_profit` | number | Yes | Take profit at entry |
| `current_stop_loss` | number | Yes | Managed stop loss, initialized from `initial_stop_loss` |
| `current_take_profit` | number | Yes | Managed take profit, initialized from `initial_take_profit` |
| `risk_at_entry` | number | Yes | Absolute entry-to-initial-stop distance used as 1R |
| `opened_at` | timestamp | Yes | Entry signal time |
| `status` | string | Yes | `open` or `closed` |

Validation rules:

- Continuation signals must not create `Trade Entry Event` records.
- At most one open trade may exist for the same symbol and direction.
- `risk_at_entry` must be positive.
- `current_stop_loss` must never move farther from entry than `initial_stop_loss`.
- Legacy records missing these fields are treated as unmanaged signal records.

## Trade Management Event

Represents a continuation-originated event evaluated against an active trade.

| Field | Type | Required for New Events | Notes |
| --- | --- | --- | --- |
| `management_event_id` | string | Yes | Unique event identifier |
| `trade_id` | string | Yes when linked | Active trade being managed |
| `source_signal_id` | string | Yes | Continuation signal that caused evaluation |
| `source_signal_type` | string | Yes | Must be `continuation` |
| `event_time` | timestamp | Yes | Continuation signal time |
| `price_at_event` | number | Yes | Price used for favorable-move evaluation |
| `old_stop_loss` | number or null | Yes | Current SL before event |
| `new_stop_loss` | number or null | Yes | New SL after accepted event; unchanged/null when rejected |
| `old_take_profit` | number or null | Yes | Current TP before event |
| `new_take_profit` | number or null | Yes | New TP after accepted event; unchanged/null when rejected |
| `reason` | string | Yes | Human-readable management rule outcome |
| `accepted` | boolean | Yes | True when SL/TP state changed |
| `rejection_reason` | string or null | Yes | Required when `accepted=false` |

Validation rules:

- Same-direction continuation may be accepted only when it improves protection and/or extends TP within limits.
- Same-direction continuation that fails thresholds must be retained with `accepted=false`.
- Opposite-direction continuation while a trade is open is retained as warning evidence and does not open a new trade.
- A management event must not increase accepted risk.
- Multiple close-together events must be processed idempotently by `management_event_id`.

## Managed Trade Outcome

Represents the final closed result of a managed trade.

| Field | Type | Notes |
| --- | --- | --- |
| `trade_id` | string | Closed lifecycle identifier |
| `close_time` | timestamp | Time outcome was determined |
| `close_price` | number | Final exit level |
| `exit_reason` | string | `tp_hit`, `sl_hit_with_loss`, `sl_hit_at_break_even`, `sl_hit_with_profit`, `manual_close_profit`, `manual_close_loss`, or compatible legacy reason |
| `result_category` | string | `win`, `loss`, or `breakeven` |
| `captured_r` | number | Captured distance from entry divided by `risk_at_entry`, signed by outcome |
| `max_favorable_excursion` | number or null | Best favorable move before exit, in price units or R |
| `original_tp_result` | string or null | What original unmanaged TP/SL accounting would have reported if known |
| `managed_result_delta` | string or null | Difference between original and managed result |

Outcome rules:

- TP hit is a win.
- SL hit worse than entry is a loss.
- SL hit at entry is break-even.
- SL hit beyond entry is a profit-protected win.
- Manual close is classified from actual profit/loss relative to entry and direction.

## Management Rule Configuration

Represents runtime-tunable lifecycle settings.

| Setting | Type | Baseline |
| --- | --- | --- |
| `CONTINUATION_MANAGEMENT_ENABLED` | boolean | `true` |
| `CONTINUATION_MANAGEMENT_BE_TRIGGER_R` | number | `1.0` |
| `CONTINUATION_MANAGEMENT_PROFIT_PROTECT_TRIGGER_R` | number | `1.5` |
| `CONTINUATION_MANAGEMENT_PROFIT_PROTECT_OFFSET_R` | number | `0.1` |
| `CONTINUATION_MANAGEMENT_TP_EXTENSION_MULTIPLE_R` | number | `0.5` |
| `CONTINUATION_MANAGEMENT_MAX_TP_EXTENSIONS` | integer | `2` |
| `CONTINUATION_MANAGEMENT_MAX_TARGET_R` | number | `4.0` |

Rules:

- Configuration names may be adjusted during implementation to match existing naming style, but all management thresholds and caps must be env-var configurable.
- Defaults must be documented in `.env.example` if new env vars are added.
- Setting management disabled must preserve continuation observation without applying SL/TP changes.

## State Transitions

```text
none
  -> open_trade_from_pullback
open_trade_from_pullback
  -> open_trade_with_rejected_management
  -> open_trade_with_tightened_sl
  -> open_trade_with_extended_tp
  -> open_trade_with_opposite_direction_warning
open_trade_with_management
  -> closed_tp_win
  -> closed_sl_loss
  -> closed_sl_breakeven
  -> closed_sl_profit_protected_win
  -> closed_manual_win
  -> closed_manual_loss
closed_trade
  -> none
```

## Legacy Compatibility

- Missing lifecycle fields normalize to unmanaged legacy values.
- Existing CSV/JSON export consumers keep receiving prior fields.
- New lifecycle fields are additive.
- Historical continuation-only rows remain signal evidence but do not create managed trades without a linked pullback entry.

# Contract: Managed Outcome Accounting

## Classification Inputs

- Trade direction
- Entry price
- Initial stop loss
- Initial take profit
- Current stop loss
- Current take profit
- Close price or inferred TP/SL touch
- Manual close profit/loss when provided

## Result Mapping

| Exit Condition | Result Category | Managed Exit Reason |
| --- | --- | --- |
| Current take profit hit | `win` | `tp_hit` |
| Current stop loss hit worse than entry | `loss` | `sl_hit_with_loss` |
| Current stop loss hit at entry | `breakeven` | `sl_hit_at_break_even` |
| Current stop loss hit beyond entry | `win` | `sl_hit_with_profit` |
| Manual close above BUY entry or below SELL entry | `win` | `manual_close_profit` |
| Manual close below BUY entry or above SELL entry | `loss` | `manual_close_loss` |

## Direction Rules

- BUY profit means exit price is greater than entry.
- SELL profit means exit price is less than entry.
- Equality at entry is break-even unless fees/spread accounting is explicitly available in the record.

## Metrics Requirements

- Profit-protected SL wins count as wins.
- Break-even exits do not count as wins or losses.
- Captured R uses `risk_at_entry`, not current stop distance.
- Managed result comparison preserves original TP/SL outcome when available.

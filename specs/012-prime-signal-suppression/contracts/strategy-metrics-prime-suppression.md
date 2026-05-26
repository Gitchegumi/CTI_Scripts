# Contract: Strategy Metrics Prime Suppression

## Summary Additions

Metrics responses and exports that summarize strategy evidence should include:

```json
{
  "total_prime_suppressed_signals": 4,
  "prime_suppressed_signals_by_symbol": {
    "AUDUSD": 3,
    "GBPJPY": 1
  },
  "prime_suppressed_same_direction_count": 2,
  "prime_suppressed_opposite_direction_count": 2,
  "inferred_tp_close_count": 1,
  "inferred_sl_close_count": 2,
  "ambiguous_prime_close_count": 1
}
```

Directional fields may be omitted only if directional counts are not stored.

## Counting Rules

- Suppressed signals are counted from prime suppression fields, not as emitted opportunity rows.
- `trade_opportunity_count` remains governed by existing strategy-stat eligibility.
- Inferred TP/SL close counts are based on `prime_closed_reason`.
- Ambiguous close count is based on `prime_close_ambiguous=true`.

## Compatibility Rules

- Legacy records with missing prime fields contribute zero to prime suppression metrics.
- Existing metrics fields remain present and retain their current meaning.

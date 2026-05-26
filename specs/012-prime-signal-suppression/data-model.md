# Data Model: Prime Signal Suppression

## Signal Journal Record

Represents one actionable emitted signal in the permanent Signal Journal JSONL file. Prime suppression adds fields to this existing record shape.

| Field | Type | Required for New Records | Notes |
| --- | --- | --- | --- |
| `prime_active` | boolean | Yes | True only while this record is the active unresolved prime for its symbol |
| `prime_suppressed_signal_count` | integer | Yes | Total same-symbol follow-on signals suppressed by this prime |
| `prime_suppressed_last_at` | timestamp or null | Yes | Timestamp of the most recent suppressed follow-on signal |
| `prime_closed_reason` | string or null | Yes | Suggested values: `inferred_tp`, `inferred_sl`, `manual_grade`, `manual_invalidated`, `stale_signal`, `expired_signal`, `reset`, `purged` where applicable |
| `prime_closed_at` | timestamp or null | Yes | Time prime activity ended |
| `prime_close_ambiguous` | boolean | Yes | True when target and stop were both touched in an unknowable interval and stop was chosen conservatively |
| `prime_suppressed_same_direction_count` | integer | Optional | Count of suppressed follow-on signals matching prime direction |
| `prime_suppressed_opposite_direction_count` | integer | Optional | Count of suppressed follow-on signals opposing prime direction |
| `prime_suppressed_signal_ids` | list/string or null | Optional | Compact suppressed signal identities if stored without noisy UI/export impact |

Validation rules:

- At most one record per symbol may have `prime_active` true.
- New actionable journal records must initialize `prime_active=true`, `prime_suppressed_signal_count=0`, `prime_suppressed_last_at=null`, `prime_closed_reason=null`, `prime_closed_at=null`, and `prime_close_ambiguous=false`.
- Suppression increments `prime_suppressed_signal_count` exactly once per suppressed follow-on signal.
- Suppression never creates a new actionable journal row.
- Legacy records missing prime fields are readable and are not active primes by default.

## Prime Signal

Represents the active unresolved journal entry for a symbol.

Identity:

- Symbol-specific only for suppression.
- Direction is used for TP/SL inference and directional suppression metrics, not for whether suppression applies.
- Strategy identity remains part of normal journal evidence but does not let same-symbol signals bypass an active prime.

State transitions:

```text
none -> active_prime
active_prime -> active_prime_with_suppression
active_prime -> closed_inferred_tp
active_prime -> closed_inferred_sl
active_prime -> closed_manual_grade
active_prime -> closed_manual_invalidated
active_prime -> inactive_stale_or_expired
active_prime -> reset_or_purged
closed_or_inactive -> none
closed_or_inactive + later signal -> active_prime
```

## Suppressed Signal Evidence

Represents a follow-on same-symbol emitted signal that was not journaled as actionable because a prime remained unresolved.

Minimum evidence:

| Field | Type | Notes |
| --- | --- | --- |
| `suppressed_at` | timestamp | The follow-on signal timestamp |
| `suppressed_direction` | string | Used for same/opposite direction counts |
| `prime_signal_id` | string | The active prime that suppressed it |

Rules:

- Suppressed evidence must not require manual grading.
- Suppressed evidence must not count as a trade opportunity.
- Suppressed evidence must not create duplicate setup rows.
- JSON export includes stored suppressed evidence when present; CSV may use compact serialized values or omit optional noisy details.

## Inferred Prime Closure

Represents a prime closed before accepting a later same-symbol signal.

BUY rules:

- Target: any candle high reaches or exceeds the prime take profit.
- Stop: any candle low reaches or falls below the prime stop loss.

SELL rules:

- Target: any candle low reaches or falls below the prime take profit.
- Stop: any candle high reaches or exceeds the prime stop loss.

Ambiguity rule:

- If target and stop are both touched in the same candle and order cannot be known, close as inferred stop and set `prime_close_ambiguous=true`.

## Prime Suppression Metrics

Aggregated counts used by strategy analysis.

| Metric | Source |
| --- | --- |
| `total_prime_suppressed_signals` | Sum of `prime_suppressed_signal_count` |
| `prime_suppressed_signals_by_symbol` | Sum grouped by journal symbol |
| `prime_suppressed_same_direction_count` | Sum when directional count exists |
| `prime_suppressed_opposite_direction_count` | Sum when directional count exists |
| `inferred_tp_close_count` | Count of records with `prime_closed_reason=inferred_tp` |
| `inferred_sl_close_count` | Count of records with `prime_closed_reason=inferred_sl` |
| `ambiguous_prime_close_count` | Count of records with `prime_close_ambiguous=true` |

## Legacy Compatibility

- Missing prime fields display as inactive/zero/blank.
- Export headers include prime fields even when records are legacy.
- Existing `usable_for_strategy_stats` and `stats_exclusion_reason` behavior remains the strategy-stat gate.
- Reset, manual grade, invalidation, stale/expired, and purge flows must deactivate active prime state when they resolve a prime.

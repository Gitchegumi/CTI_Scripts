# Contract: Continuation Management Flow

## Entry Flow

1. Pullback or high-value pullback passes signal evaluation.
2. If no active trade exists for the same symbol and direction, create an open trade entry.
3. If an active trade already exists for the same symbol and direction, do not create a duplicate entry; record suppression or rejection evidence according to existing journal behavior.

## Continuation Without Active Trade

1. Continuation passes signal evaluation.
2. Lookup active pullback-originated trade for the same symbol and direction.
3. If none exists, record non-entry signal evidence and do not create a trade entry.

## Same-Direction Continuation With Active Trade

1. Continuation passes signal evaluation.
2. Create a management event linked to the active trade.
3. Compute favorable movement from entry in R.
4. If favorable movement satisfies break-even or profit-protection thresholds, propose SL tightening.
5. If continuation strength qualifies for extension and caps allow it, propose TP extension.
6. Reject any proposal that increases risk or exceeds configured caps.
7. Persist accepted or rejected event with reason and old/new values.

## Opposite-Direction Continuation With Active Trade

1. Continuation passes signal evaluation in the opposite direction.
2. Do not open a new trade while the prime trade remains active.
3. Record warning or exit-management evidence linked to the active trade when possible.
4. Increment opposite-direction warning metrics.

## Idempotency

- Reprocessing the same continuation signal must not apply SL/TP changes twice.
- `source_signal_id` or `management_event_id` is the deduplication key.
- Accepted/rejected state must remain stable after replay.

# Contract: Prime Suppression Flow

## New Signal Reaches Journal

1. Determine the new signal timestamp and symbol.
2. Under the journal mutation lock, load persisted journal entries.
3. Find the active unresolved prime for the same symbol.
4. If no active prime exists, create the normal journal entry and initialize it as prime.
5. If an active prime exists, evaluate whether its target or stop was touched before the new signal.
6. If the prime closed by inferred target or stop, deactivate the old prime, record closure fields, create the new journal entry, and mark it prime.
7. If the prime did not close, update suppression fields on the active prime and do not create a new actionable journal row.

## Active Prime Resolution Inputs

Use the prime's original:

- `symbol`
- `direction`
- `entry_price`
- `stop_loss`
- `take_profit`
- `signal_timestamp`

Use the new signal timestamp as the upper bound for inference.

## Suppression Result

Suppression must update:

- `prime_suppressed_signal_count`
- `prime_suppressed_last_at`
- directional counts when present
- optional compact suppressed metadata when present

Suppression must not:

- append a new actionable row
- create a setup group row
- require grading
- count as usable strategy stats
- change strategy firing rules

## Replacement Result

Replacement must:

- set old prime `prime_active=false`
- set old prime `prime_closed_reason`
- set old prime `prime_closed_at`
- set old prime `prime_close_ambiguous` when applicable
- append the new signal as `prime_active=true`

## Manual and Existing Lifecycle Results

Manual grade, manual invalidation, stale/expired resolution, reset, and purge flows must not leave stale active primes behind. When they resolve or remove an active prime, later same-symbol signals can create a new prime.

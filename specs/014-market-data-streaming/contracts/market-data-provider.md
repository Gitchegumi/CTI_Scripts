# Contract: Market Data Provider

## Purpose

Define the provider-neutral lifecycle TradeGumi core depends on. This is a planning contract, not an implementation.

## Provider Lifecycle

### start(symbols)

**Input**

- `symbols`: CTI symbol list.

**Required behavior**

- Starts observation for the supplied symbol set.
- Publishes normalized `PriceObservation` records only.
- Records health state as `starting` then `running` or `fallback/failed`.
- Does not expose provider-specific event objects to journal, dashboard, or signal logic.

### stop()

**Required behavior**

- Stops active stream, polling timer, or worker.
- Releases network resources.
- Is safe to call more than once.
- Completes during graceful shutdown without leaving duplicate background workers.

### resubscribe(symbols, reason)

**Input**

- `symbols`: latest CTI symbol list.
- `reason`: startup, full rescan, periodic rescan, API rescan, fallback, or shutdown.

**Required behavior**

- Replaces the active symbol set with the new set.
- Avoids duplicate active streams.
- Uses the latest symbol set if resubscribe happens during reconnect.

### snapshot_health()

**Output**

```json
{
  "configured_mode": "streaming",
  "active_mode": "streaming",
  "provider": "oanda_stream",
  "active_symbol_count": 12,
  "observations_per_minute": 480,
  "last_observation_at": "2026-05-30T14:00:00Z",
  "last_heartbeat_at": "2026-05-30T14:00:00Z",
  "last_heartbeat_age_seconds": 1.2,
  "reconnect_count": 0,
  "fallback_active": false,
  "last_error_type": null,
  "last_error_at": null
}
```

## Dispatch Contract

For every accepted `PriceObservation`:

1. Publish to shared rolling price history.
2. Evaluate Signal Journal via existing observation evaluator.
3. Make latest observation available to dashboard/runtime state and signal live trigger checks.

Detailed observation logs remain DEBUG-level.

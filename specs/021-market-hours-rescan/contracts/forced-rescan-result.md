# Contract: Forced Rescan Result

## Purpose

Ensure a forced rescan reports forex market-session and per-symbol availability independently.

## Trigger

Existing API path:

```http
POST /api/action/rescan
```

The endpoint continues to return command acceptance, while the worker publishes the rescan outcome through existing runtime state, watchlist state, logs, and callbacks.

## Result Shape

```json
{
  "trigger": "api",
  "requested_at": "2026-06-14T21:40:00-05:00",
  "market_open": true,
  "symbols_checked": 12,
  "symbols_available": 10,
  "symbols_unavailable": 2,
  "availability": [
    {
      "symbol": "EURUSD",
      "market_open": true,
      "available": true,
      "reason": "available",
      "detail": null
    },
    {
      "symbol": "XAUUSD",
      "market_open": true,
      "available": false,
      "reason": "account_instrument_unavailable",
      "detail": "Instrument is not available for the configured account."
    }
  ],
  "watchlist_counts": {
    "tier1": 3,
    "tier2": 4,
    "below": 3
  }
}
```

## Required Behavior

- `market_open` is true when at least one configured, non-excluded forex symbol is in an open forex session.
- `symbols_available` counts only symbols that pass market-session and symbol-specific availability checks.
- `symbols_unavailable` must not be set to all symbols unless each symbol has a real unavailable reason.
- If all symbols are unavailable, the reasons must make clear whether the cause is true forex market closure or symbol/account availability.

## Backward Compatibility

Existing callback consumers that only read `trigger` must keep working. New fields are additive.

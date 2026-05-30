# Contract: Runtime State and Dashboard Consumption

## Runtime State Additions

Runtime state may expose market data health alongside existing loop state:

```json
{
  "market_data": {
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
}
```

## Dashboard Price State

- Loop state symbols keep `bid`, `ask`, and `spread` fields.
- In streaming mode, these fields are filled from latest shared observations.
- Dashboard/API routes must not call broker pricing endpoints for display-only price refreshes.

## Logging

INFO health summary fields:

- active mode
- configured mode
- active symbol count
- observations per minute
- reconnect count
- fallback status
- last heartbeat age

DEBUG-only detail:

- individual observation parse/publish timings
- malformed stream line details
- per-symbol observation dispatch

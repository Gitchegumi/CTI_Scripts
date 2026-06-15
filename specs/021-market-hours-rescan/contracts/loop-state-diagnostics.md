# Contract: Loop State Diagnostics

## Purpose

Keep the dashboard and API able to distinguish closed forex sessions from unavailable symbols.

## Existing Endpoint

```http
GET /api/data/loop_state
```

## Symbol Entry Additions

Fields are additive and may be omitted by older state files.

```json
{
  "symbol": "EURUSD",
  "state": "closed",
  "trend": "closed",
  "market_open": false,
  "availability_state": "market_closed",
  "availability_reason": "weekend_break",
  "session_boundary": "Next forex weekly open Sunday 16:00 CT / 17:00 ET"
}
```

## Required Behavior

- When a forex symbol is skipped because the forex market is closed, `availability_state` is `market_closed`.
- When a symbol is skipped because the account or provider does not support it, `availability_state` is `symbol_unavailable`.
- When a symbol is scanned normally, `availability_state` is `available`.
- Dashboard market-open derivation must not treat symbol-specific unavailable states as proof that the entire forex market is closed.

## Compatibility

The existing `state` field remains available for current dashboard behavior. Additive fields let newer UI and diagnostics avoid conflating closed forex sessions with unavailable symbols.

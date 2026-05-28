# Contract: Signal Outcome Evaluator

## Purpose

Evaluate unresolved alert-only/developing Signal Journal entries when new price observations arrive.

## Input

```json
{
  "observation": {
    "symbol": "EURUSD",
    "timestamp": "2026-05-27T14:05:01Z",
    "bid": 1.1042,
    "ask": 1.1043,
    "source": "dashboard_poll",
    "received_at": "2026-05-27T14:05:01.123456+00:00"
  }
}
```

## Behavior

- Load unresolved eligible journal entries for `observation.symbol`.
- Skip entries with manual override or manual lock.
- Update checked time and excursions for no-hit observations when possible.
- Close BUY target when `bid >= take_profit`.
- Close BUY stop when `bid <= stop_loss`.
- Close SELL target when `ask <= take_profit`.
- Close SELL stop when `ask >= stop_loss`.
- If target and stop are both hit in one unresolved cycle without ordering, mark ambiguous with reason.
- If midpoint is the only available price, grade only with midpoint-specific outcome source.
- Return a compact summary of updated signal ids and outcomes for logging/tests.

## Output

```json
{
  "evaluated_count": 2,
  "updated": [
    {
      "signal_id": "sig-123",
      "status": "closed",
      "outcome": "tp",
      "outcome_source": "live_price_observation_1s",
      "exit_price": 1.1042
    }
  ]
}
```

## Side Effects

- May rewrite Signal Journal entries through existing journal ownership helpers.
- Must not call broker pricing APIs.
- Must not execute trades or generate signals.

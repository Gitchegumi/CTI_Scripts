# Contract: Price Observation Service

## Purpose

Provide one shared in-process source of recent market price observations for dashboard-facing reads and alert-only outcome evaluation.

## Publisher Contract

Publisher input:

```json
{
  "symbol": "EURUSD",
  "timestamp": "2026-05-27T14:05:01Z",
  "bid": 1.08501,
  "ask": 1.08513,
  "mid": 1.08507,
  "source": "dashboard_poll",
  "received_at": "2026-05-27T14:05:01.123456+00:00"
}
```

Rules:

- The existing one-second pricing loop publishes observations with `source=dashboard_poll`.
- A future stream publisher must publish the same shape with `source=oanda_pricing_stream`.
- Historical or manual publishers use `historical_candle` or `manual_backfill`.
- Publishing prunes per-symbol history to bounded retention.

## Reader Contract

Readers can request:

- Latest observation for one symbol.
- Latest observations for many symbols.
- Recent observations for one symbol.

Rules:

- Readers receive copies or immutable records so callers cannot mutate shared history.
- Missing symbols return no observation rather than triggering provider calls.
- The reader path does not perform Oanda/API polling.

## Non-Goals

- No undocumented broker chart or browser endpoint use.
- No direct order execution or trade mutation.
- No unbounded tick persistence.

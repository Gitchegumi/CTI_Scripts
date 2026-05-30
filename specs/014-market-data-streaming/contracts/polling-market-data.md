# Contract: Polling Market Data Provider

## Purpose

Preserve the current `get_pricing()` behavior as an explicit market data provider and fallback path.

## Polling Behavior

### start(symbols)

- Begins polling the supplied CTI symbol set at `TRADEGUMI_PRICE_POLL_SECONDS`, default 1 second.
- Uses existing `ExecutionClient.get_pricing(symbols)`.
- Publishes resulting ticks as `PriceObservation` records with the polling source.

### resubscribe(symbols, reason)

- Replaces the next polling request's symbol list with the latest scan symbols.
- Does not create an additional polling loop.

### fallback activation

- Starts or resumes polling when streaming is disabled, unavailable, stale, or repeatedly failing.
- Records `fallback_active=true` in health state.
- Keeps Signal Journal evaluation and dashboard price display alive.

## Non-Duplication Rule

Polling must not make live price calls for dashboard/journal observation while streaming is healthy for the same symbol set.

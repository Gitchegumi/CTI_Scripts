# Quickstart: Validation Plan for Market Data Streaming

## Preconditions

- Use a non-funded environment for validation.
- Configure Oanda practice credentials in `.env`.
- Keep polling fallback enabled.
- Do not change strategy thresholds or risk settings while validating this feature.

## Scenario 1: Oanda Stream Publishes Shared Observations

1. Set `TRADEGUMI_MARKET_DATA_MODE=streaming`.
2. Start TradeGumi with an active watchlist.
3. Confirm startup logs show streaming mode, stream URL environment, heartbeat timeout, reconnect interval, and fallback enabled.
4. Confirm `PriceObservation` records are published with source `oanda_pricing_stream`.
5. Confirm dashboard loop state shows bid/ask/spread from shared observations.
6. Confirm REST `get_pricing()` is not called for dashboard/journal live price observation while stream is healthy.

## Scenario 2: Journal Outcome From Streamed Price

1. Seed or create an unresolved Signal Journal entry for a streamed symbol.
2. Publish or simulate a stream price that reaches TP or SL.
3. Confirm `evaluate_price_observation()` updates the entry immediately.
4. Confirm the update occurs within the 2-second success target used by tests.
5. Confirm manual override protections still hold.

## Scenario 3: Heartbeat and Stale Stream Reconnect

1. Simulate normal heartbeat events and verify liveness updates without observations.
2. Stop heartbeat/price events beyond `TRADEGUMI_STREAM_HEARTBEAT_TIMEOUT_SECONDS`.
3. Confirm reconnect begins with backoff.
4. Confirm reconnect attempts respect the no-more-than-2-new-connections-per-second constraint.
5. Confirm reconnect attempts stop or fall back after `TRADEGUMI_STREAM_MAX_RECONNECT_ATTEMPTS`.

## Scenario 4: Fallback to Polling

1. Simulate authentication failure, connection failure, or repeated reconnect failure.
2. Confirm logs report a safe error category without secrets.
3. Confirm polling fallback starts within the configured fallback window.
4. Confirm journal and dashboard behavior continue from polling observations.

## Scenario 5: Resubscribe on Watchlist Change

1. Start streaming with one scan symbol set.
2. Trigger full, periodic, or API rescan with a changed symbol set.
3. Confirm old stream workers stop cleanly.
4. Confirm exactly one active stream or polling loop observes the latest symbol set.

## Scenario 6: Graceful Shutdown

1. Start TradeGumi with streaming active.
2. Send shutdown signal.
3. Confirm stream worker exits and resources close cleanly.
4. Confirm no duplicate background worker remains after restart.

## Test Commands

```powershell
pytest src/tradegumi/tests/test_market_data.py
pytest src/tradegumi/tests/test_oanda_market_data.py
pytest src/tradegumi/tests/test_main_market_data.py
pytest src/tradegumi/tests/test_signal_outcomes.py
pytest src/tradegumi/tests/test_price_observations.py
```

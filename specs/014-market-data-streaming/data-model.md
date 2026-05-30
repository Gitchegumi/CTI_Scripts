# Data Model: Provider-Agnostic Market Data Streaming

## MarketDataProvider

Provider-neutral lifecycle participant for live price observations.

**Fields / properties**

- `name`: stable provider identifier such as `oanda_stream`, `polling`, or future provider name.
- `mode`: `streaming` or `polling`.
- `active_symbols`: current CTI symbol set.
- `status`: `stopped`, `starting`, `running`, `reconnecting`, `fallback`, or `failed`.
- `health`: current `MarketDataHealth`.

**Operations**

- `start(symbols)`: begins observation for the supplied CTI symbols.
- `stop()`: stops active observation and releases resources.
- `resubscribe(symbols)`: replaces active observation symbols with the latest scan symbol set.
- `restart(reason)`: restarts active observation after disconnect, heartbeat stale, or rescan.
- `snapshot_health()`: returns a safe serializable health view.

**Validation rules**

- Provider must not run duplicate active streams for the same process.
- Provider must accept an empty symbol set by stopping or entering a safe idle state.
- Provider must publish only normalized `PriceObservation` objects to core consumers.

## MarketDataSubscription

Represents the desired symbol set and provider generation.

**Fields**

- `symbols`: ordered or sorted CTI symbol list.
- `generation`: monotonic identifier incremented on resubscribe.
- `updated_at`: timestamp of last subscription change.
- `reason`: `startup`, `full_rescan`, `periodic_rescan`, `api_rescan`, `fallback`, or `shutdown`.

**State transitions**

- `startup` -> `running`
- `running` -> `resubscribing` -> `running`
- `running` -> `reconnecting` -> `running`
- `running` -> `fallback`
- any active state -> `stopped`

## MarketDataHealth

Serializable operational state for logs and runtime API.

**Fields**

- `active_mode`: `streaming` or `polling`.
- `configured_mode`: configured requested mode.
- `provider`: provider name.
- `active_symbol_count`: count of symbols currently observed.
- `observations_per_minute`: rolling count/rate.
- `last_observation_at`: timestamp of latest price observation.
- `last_heartbeat_at`: timestamp of latest stream heartbeat, if streaming.
- `last_heartbeat_age_seconds`: derived age for stale detection.
- `reconnect_count`: reconnect attempts since provider start.
- `fallback_active`: whether polling fallback is active.
- `last_error_type`: safe category of last provider error.
- `last_error_at`: timestamp of last provider error.

## OandaStreamEvent

Provider-specific raw event consumed only by the Oanda stream provider.

**Variants**

- `price`: includes `instrument`, `time`, bids array, asks array, and tradeability status.
- `heartbeat`: includes `type=HEARTBEAT` and `time`.
- `malformed`: invalid JSON or missing required fields.
- `provider_error`: HTTP response or transport exception.

**Mapping rules**

- `instrument` maps to CTI symbol via `config.from_oanda_symbol`.
- Best bid/ask use the first available bid/ask price from Oanda price arrays.
- Price events publish `PriceObservation(source=OANDA_PRICING_STREAM)`.
- Heartbeats update liveness only and do not publish observations.

## PollingObservationBatch

Fallback/current REST polling output.

**Fields**

- `symbols`: requested CTI symbols.
- `ticks`: provider-neutral `PriceTick` values from existing `get_pricing()`.
- `observations`: `PriceObservation` records with polling source.
- `fetched_at`: timestamp of REST fetch.

**Validation rules**

- Polling fallback must publish through the same observation path as streaming.
- Polling must not run concurrently with a healthy streaming provider for the same live price purpose.

## Observation Dispatch

Connects market data providers to existing consumers.

**Flow**

1. Provider parses or fetches provider price data.
2. Provider publishes one or more `PriceObservation` records to `RollingPriceHistory`.
3. Each published observation triggers Signal Journal evaluation.
4. Runtime loop/dashboard state reads latest observations for displayed prices.
5. Signal engine live trigger checks read latest shared observations, not provider-specific payloads.

**Correctness constraints**

- Manual journal overrides remain protected by existing evaluator rules.
- Provider failures must not cause duplicate journal evaluation for the same observation.
- Dashboard display must not trigger broker price calls.

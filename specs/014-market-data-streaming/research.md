# Research: Provider-Agnostic Market Data Streaming

## Decision: Use Oanda's documented streaming pricing endpoint as the first streaming source

**Rationale**: The official Oanda REST-V20 Development Guide documents separate REST and Streaming API base URLs for practice and live environments, and the Pricing endpoint documentation defines a streaming price endpoint that returns price and heartbeat objects over a persistent chunked response. TradeGumi already has `OANDA_STREAM_URL`, Oanda symbol mapping, and a shared `PriceObservation` model.

**Source facts**:

- Practice REST: `https://api-fxpractice.oanda.com`
- Live REST: `https://api-fxtrade.oanda.com`
- Practice Streaming: `https://stream-fxpractice.oanda.com/`
- Live Streaming: `https://stream-fxtrade.oanda.com/`
- Authentication uses bearer token in the HTTP `Authorization` header.
- REST limit is 120 requests per second per requesting IP.
- Streaming limit is 20 active streams per requesting IP.
- Connection limit is no more than 2 new connections per second.
- Streaming pricing response is `application/octet-stream`, chunked, one JSON object per line, containing price and/or heartbeat objects.
- Heartbeats are sent every 5 seconds.
- Oanda pricing stream may send up to four prices per second per instrument and may not send every price during rapid movement.

**Alternatives considered**:

- Continue optimized REST polling only: rejected because it does not address the remaining REST call and loop wakeup cost.
- Add Oanda streaming directly inside `main.py`: rejected because it would make MatchTrader portability harder and mix lifecycle concerns into the trading loop.

## Decision: Introduce provider-neutral market data lifecycle separate from `ExecutionClient`

**Rationale**: `ExecutionClient` currently covers execution, account state, candles, positions, and REST pricing. Market data streaming has a different lifecycle: start, stop, reconnect, heartbeat, resubscribe, and health reporting. A separate provider-neutral market data interface keeps signal, journal, dashboard, and future MatchTrader consumers broker-agnostic.

**Alternatives considered**:

- Extend `ExecutionClient` with streaming methods: rejected because execution and market data lifecycles are different, and future MatchTrader market data may not align with execution client semantics.
- Create an Oanda-only stream helper: rejected because it does not satisfy the provider-agnostic goal.

## Decision: Publish all live prices as `PriceObservation`

**Rationale**: `PriceObservation` and `RollingPriceHistory` already provide the shared provider-neutral observation layer. Journal evaluation already accepts a `PriceObservation`, and signal live trigger price checks can already read latest observations.

**Alternatives considered**:

- Add a separate streaming price model: rejected because it would duplicate existing observation contracts and increase consumer branching.

## Decision: Trigger journal evaluation on observation publish in streaming mode

**Rationale**: The current one-second path intentionally keeps Signal Journal outcomes fresh. Streaming can improve this by evaluating immediately when a new observation arrives. Polling mode preserves existing behavior.

**Alternatives considered**:

- Batch stream observations and evaluate once per second: rejected because it can delay TP/SL grading and gives away the primary benefit of streaming.

## Decision: Keep polling as an always-available provider and automatic fallback

**Rationale**: Streaming can fail because of authentication, network, provider, heartbeat, or connection-limit issues. The bot must remain alive and preserve journal outcome updates. Polling mode is already implemented through `client.get_pricing()`.

**Alternatives considered**:

- Fail closed if streaming fails: rejected because it risks missed Signal Journal outcome updates.
- Retry streaming forever without fallback: rejected because it can violate connection limits and keep the bot blind.

**Configuration implication**: The plan should include both a base reconnect interval and guardrails (`TRADEGUMI_STREAM_BACKOFF_MAX_SECONDS`, `TRADEGUMI_STREAM_MAX_RECONNECT_ATTEMPTS`) so reconnect behavior remains operator-tunable without changing code.

## Decision: Resubscribe by replacing the active subscription for the latest scan symbol set

**Rationale**: Full, periodic, and API-triggered rescans change `scan_symbols`. The provider must stop or update the old subscription and ensure only one active stream represents the latest symbol set.

**Alternatives considered**:

- Keep old symbols until next restart: rejected because it wastes provider limits and can display stale/non-watchlist observations.
- Open a second stream during resubscribe and close later: rejected unless strictly bounded, because duplicate active streams increase provider-limit risk.

## Decision: Use compact INFO health summaries and DEBUG detailed logs

**Rationale**: The recent CPU work already avoided per-loop INFO spam. Streaming should expose enough operational state to diagnose CPU/network issues without logging every price at INFO.

**Alternatives considered**:

- Log every price at INFO: rejected because it creates log churn and CPU overhead.
- No health summary: rejected because operators need visibility into fallback and stream liveness.

## Decision: Validation focuses on deterministic fake providers and Oanda payload fixtures

**Rationale**: Unit tests can validate parsing, heartbeat handling, fallback, resubscribe, and shutdown without live Oanda network access. Live credentials should not be required for CI or local test success.

**Alternatives considered**:

- Use live Oanda stream in tests: rejected because it requires secrets, network stability, and live provider availability.

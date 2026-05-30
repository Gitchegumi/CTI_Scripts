# Feature Specification: Provider-Agnostic Market Data Streaming

**Feature Branch**: `014-market-data-streaming`
**Created**: 2026-05-30
**Status**: Draft
**Input**: User description: "Add provider-agnostic market data streaming for TradeGumi with Oanda streaming first and REST polling fallback."

## Clarifications

### Session 2026-05-30

- No formal clarification questions were required. The user explicitly set streaming as the default Oanda mode once implemented, polling as fallback, Oanda as the first streaming provider, MatchTrader streaming as a non-goal, and preservation of fast journal/dashboard/signal behavior as mandatory.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stream Live Prices Without REST Polling Spikes (Priority: P1)

As a TradeGumi operator on a low-power host, I want live prices to arrive through a persistent provider stream so the bot can observe fast market movement without making repeated REST pricing calls every second during normal streaming operation.

**Why this priority**: This is the primary CPU-reduction path and must preserve the existing live price observation behavior that Signal Journal grading depends on.

**Independent Test**: Can be tested by running TradeGumi with Oanda streaming enabled for an active watchlist and verifying that live observations are published continuously, REST pricing calls are not made for the same live price data while the stream is healthy, and Signal Journal outcomes still resolve promptly.

**Acceptance Scenarios**:

1. **Given** TradeGumi is configured for streaming market data and Oanda credentials are valid, **When** the watchlist contains tradeable symbols, **Then** a single active Oanda pricing stream publishes provider-neutral price observations for those symbols.
2. **Given** a streamed price reaches an unresolved Signal Journal entry's stop loss or take profit, **When** the observation is received, **Then** the journal evaluator grades that entry without waiting for the next one-second polling tick.
3. **Given** the Oanda stream is healthy, **When** the dashboard requests loop state, **Then** dashboard prices come from shared observations/state and no separate broker price call is triggered for dashboard display.

---

### User Story 2 - Fallback Safely When Streaming Fails (Priority: P2)

As a TradeGumi operator, I want the bot to keep running with REST polling when streaming is disabled, unavailable, stale, or repeatedly failing so price observation and journal grading continue instead of silently stopping.

**Why this priority**: Streaming reliability must not create missed journal outcomes or bot downtime.

**Independent Test**: Can be tested by simulating stream authentication failure, dropped connections, stale heartbeats, and repeated reconnect failures, then verifying that polling mode takes over and publishes equivalent shared observations.

**Acceptance Scenarios**:

1. **Given** streaming is enabled but Oanda returns an authentication or unrecoverable provider error, **When** the stream cannot start, **Then** the bot logs the failure clearly and falls back to polling.
2. **Given** the stream stops receiving heartbeats for longer than the configured timeout, **When** stale-stream detection runs, **Then** the provider reconnects using backoff without exceeding Oanda connection limits.
3. **Given** streaming repeatedly fails beyond the configured tolerance, **When** fallback is activated, **Then** the existing polling behavior continues to publish observations and evaluate journal outcomes.

---

### User Story 3 - Resubscribe Cleanly as Watchlist Changes (Priority: P3)

As a TradeGumi operator, I want market data subscriptions to follow full, periodic, and API-triggered rescans so only the current scan symbols are observed and duplicate streams are not left running.

**Why this priority**: Watchlist changes are central to TradeGumi operation, and stale subscriptions waste resources and may violate provider stream limits.

**Independent Test**: Can be tested by changing the scan symbol set through a rescan and verifying that the active provider subscription changes exactly once, old stream workers stop cleanly, and observations continue for the new symbol set.

**Acceptance Scenarios**:

1. **Given** streaming is active for an initial scan symbol set, **When** a full rescan changes the symbols, **Then** the market data provider updates its active subscription to the new set and stops observing removed symbols.
2. **Given** an API-triggered rescan occurs while the stream is reconnecting, **When** the provider restarts, **Then** it subscribes to the latest symbol set rather than an older cached list.
3. **Given** the bot is shutting down, **When** shutdown handling runs, **Then** active stream workers stop cleanly without leaving duplicate background threads or tasks.

---

### User Story 4 - Preserve Provider Portability (Priority: P4)

As a future maintainer preparing for MatchTrader market data, I want TradeGumi core logic to consume normalized price observations rather than Oanda-specific stream objects so a future provider can be added without rewriting journal, dashboard, or signal logic.

**Why this priority**: The project constitution requires broker abstraction, and the feature should not make the MatchTrader migration harder.

**Independent Test**: Can be tested by using a fake market data provider that publishes normalized observations and verifying that journal evaluation, dashboard state, and signal trigger price reads work without importing Oanda-specific types.

**Acceptance Scenarios**:

1. **Given** a non-Oanda provider publishes a valid normalized observation, **When** TradeGumi receives it, **Then** the same journal, dashboard, and signal-engine consumers process it without provider-specific branching.
2. **Given** Oanda stream payloads include provider-specific instrument names and heartbeat objects, **When** they are processed, **Then** price payloads become TradeGumi CTI symbols and heartbeats update liveness without creating price observations.

### Edge Cases

- Oanda stream sends a heartbeat: liveness is refreshed, but no `PriceObservation` record is created.
- Oanda stream sends a price object for an instrument not present in the current scan symbols: the observation is ignored or recorded as filtered without affecting dashboard/journal state.
- Oanda stream sends malformed JSON, missing bid/ask arrays, or an unmapped instrument: the error is logged at a safe level and does not stop the bot unless failures exceed reconnect/fallback limits.
- Streaming is configured but the account is unavailable, the token is invalid, or the provider rejects the stream: the bot falls back to polling and clearly reports the reason.
- A rescan happens during an active reconnect backoff: the next subscription uses the latest scan symbol list.
- The active stream becomes stale while polling fallback is already active: no duplicate polling loops or duplicate streams are created.
- Price events arrive faster than dashboard update cadence: the latest shared observation is retained for consumers without requiring one file write per price event.
- The process receives shutdown while the stream request is open: stream resources close cleanly within a bounded time.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: TradeGumi MUST provide a provider-neutral market data capability that can start, stop, restart, and resubscribe using a supplied symbol list.
- **FR-002**: Market data providers MUST publish normalized `PriceObservation` records that include CTI symbol, timestamp, bid/ask or midpoint, source, observed time, and received time.
- **FR-003**: Oanda streaming MUST be the first streaming provider and MUST convert Oanda instrument names to CTI symbols using existing symbol mapping.
- **FR-004**: Oanda streamed price objects MUST publish observations with source `OANDA_PRICING_STREAM`.
- **FR-005**: Oanda heartbeat objects MUST update stream liveness and MUST NOT create price observations.
- **FR-006**: The system MUST retain REST polling as an available market data mode and fallback path.
- **FR-007**: When streaming is healthy, the system MUST avoid duplicate REST pricing calls for the same live price data consumed by the journal and dashboard.
- **FR-008**: Signal Journal outcome evaluation MUST run immediately for each new streaming price observation and MUST continue to use the existing journal evaluation behavior.
- **FR-009**: Polling mode MUST preserve the current one-second default outcome observation behavior.
- **FR-010**: Dashboard/API state MUST consume latest shared observations/state and MUST NOT trigger separate broker price calls for dashboard price display.
- **FR-011**: Signal evaluation MUST continue at the configured signal-engine cadence, defaulting to five seconds, and MUST retain intrabar opportunity detection.
- **FR-012**: Signal logic MUST consume provider-neutral observations for live trigger pricing where live prices are needed and MUST NOT depend on Oanda stream objects.
- **FR-013**: Full, periodic, and API-triggered rescans MUST update market data subscriptions when scan symbols change.
- **FR-014**: Resubscription MUST avoid duplicate active streams and MUST stop old stream workers cleanly.
- **FR-015**: Streaming disconnects MUST reconnect with bounded backoff, MUST respect provider connection limits, and MUST stop retrying or enter polling fallback when the configured reconnect tolerance is exceeded.
- **FR-016**: Stale heartbeat detection MUST trigger reconnect when no heartbeat or price event is received within the configured timeout.
- **FR-017**: Authentication errors, unrecoverable provider errors, repeated stream failures, and fallback activation MUST be logged clearly without exposing secrets.
- **FR-018**: If streaming repeatedly fails, the bot MUST fall back to polling and continue running.
- **FR-019**: Graceful shutdown MUST stop active market data providers and background workers cleanly.
- **FR-020**: The system MUST emit compact INFO-level streaming health summaries including observations per minute, reconnect count, last heartbeat age, active symbol count, and active mode.
- **FR-021**: Detailed per-observation and per-loop timing logs MUST remain DEBUG-level only.
- **FR-022**: Configuration MUST include `TRADEGUMI_MARKET_DATA_MODE=streaming|polling`, `TRADEGUMI_STREAM_RECONNECT_SECONDS`, `TRADEGUMI_STREAM_HEARTBEAT_TIMEOUT_SECONDS`, `TRADEGUMI_STREAM_BACKOFF_MAX_SECONDS`, and `TRADEGUMI_STREAM_MAX_RECONNECT_ATTEMPTS`.
- **FR-023**: Oanda streaming mode MUST default to streaming once implemented, with automatic fallback to polling on streaming failure.
- **FR-024**: The implementation MUST use persistent streaming connections and MUST avoid reconnect loops that exceed Oanda's documented connection limits.
- **FR-025**: The implementation MUST account for Oanda's documented REST and streaming limits: 120 REST requests per second per requesting IP, 20 active streams per requesting IP, and no more than 2 new connections per second.
- **FR-026**: Oanda stream handling MUST follow the documented stream response format: line-delimited JSON objects over a chunked streaming response containing price and heartbeat objects.
- **FR-027**: Oanda stream handling MUST use bearer-token authentication and the configured practice/live streaming base URL appropriate to the selected environment.

### Key Entities

- **Market Data Provider**: Provider-neutral lifecycle participant responsible for starting, stopping, restarting, resubscribing, reporting health, and publishing normalized observations.
- **Market Data Mode**: Runtime selection of streaming or polling behavior, including fallback state when configured streaming is unavailable.
- **Market Data Subscription**: Active symbol set for which live prices should be observed.
- **Stream Health State**: Liveness, heartbeat age, reconnect count, fallback status, active symbol count, and last error category.
- **Price Observation**: Provider-neutral price fact already used by journal, dashboard, and signal consumers.
- **Provider Stream Event**: Raw provider event such as Oanda price, heartbeat, malformed line, disconnect, or error response.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: During healthy streaming operation, REST pricing calls for watchlist price observation are reduced by at least 90% compared with one-second polling over the same 10-minute active-market window.
- **SC-002**: A streamed TP/SL hit updates the corresponding Signal Journal entry within 2 seconds of observation receipt in 95% of test cases.
- **SC-003**: Dashboard price display continues to refresh from shared state within the existing dashboard polling interval while streaming is active.
- **SC-004**: Signal evaluation continues to run at the configured cadence, defaulting to 5 seconds, with no forced slowdown introduced by streaming.
- **SC-005**: Streaming reconnect attempts never exceed 2 new connections per second and use persistent connections during healthy operation.
- **SC-006**: When streaming is unavailable, polling fallback begins within 30 seconds or the configured fallback window, whichever is lower.
- **SC-007**: Rescans that change the scan symbol set result in exactly one active market data subscription for the latest symbol set.
- **SC-008**: Streaming health summaries appear at INFO level no more frequently than the configured summary interval, while per-observation details remain DEBUG-only.
- **SC-009**: Unit and integration tests cover stream price parsing, heartbeat handling, reconnect/fallback behavior, symbol mapping, source correctness, journal evaluation from stream observations, resubscribe behavior, polling fallback, and graceful shutdown.
- **SC-010**: Core journal, dashboard, and signal-engine consumers can be tested against a fake provider without importing Oanda-specific stream types.
- **SC-011**: Oanda stream parser tests prove chunked line-delimited price, heartbeat, malformed-line, and unknown-event handling without requiring live network access or credentials.

## Current-State Findings

- `src/tradegumi/main.py` currently performs live price observation through `client.get_pricing(scan_symbols)` inside the one-second path.
- `src/tradegumi/price_observations.py` already provides `PriceObservation`, `RollingPriceHistory`, `DASHBOARD_POLL`, and `OANDA_PRICING_STREAM`.
- `src/tradegumi/signal_outcomes.py` already evaluates journal outcomes from a `PriceObservation`.
- `src/tradegumi/config.py` already defines `OANDA_STREAM_URL`.
- `src/tradegumi/api/oanda_client.py` stores `self.stream_url` but still uses REST `get_pricing()` for live prices.
- Recent loop optimizations cache watchlist data, reduce loop state writes, provide runtime API state for dashboard use, and add performance counters; streaming should build on those changes rather than replacing them.

## Assumptions

- Oanda documentation reviewed for this specification is the REST-V20 Development Guide, Authentication, Best Practices, and Pricing/Streaming Pricing endpoint documentation at `https://developer.oanda.com/rest-live-v20/`.
- Oanda practice REST base URL is `https://api-fxpractice.oanda.com`; live REST base URL is `https://api-fxtrade.oanda.com`.
- Oanda practice streaming base URL is `https://stream-fxpractice.oanda.com/`; live streaming base URL is `https://stream-fxtrade.oanda.com/`.
- Oanda stream heartbeats are expected approximately every 5 seconds, so heartbeat timeout should be configurable and larger than one heartbeat interval.
- Oanda may send up to four streamed prices per second per instrument and may not send every tick during rapid price movement; the feature relies on provider-documented stream behavior rather than tick-perfect reconstruction.
- Polling remains the safe fallback for any provider that cannot stream or while streaming is degraded.
- MatchTrader streaming is out of scope for this feature, but the provider interface must be suitable for a future MatchTrader implementation.
- Trading thresholds, risk rules, execution behavior, and dashboard redesign are out of scope unless a small dashboard state change is required to consume shared observations.

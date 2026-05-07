# Feature Specification: OANDA API Resilience

**Feature Branch**: `009-oanda-api-resilience`  
**Created**: 2026-05-07  
**Status**: Draft  
**Input**: User description: "Verify and harden OANDA v20 REST integration so transient candle fetch failures, especially 504 Gateway Timeout, retry and produce precise indeterminate diagnostics instead of missing signal inputs or normal no-signal decisions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recover From Transient OANDA Candle Failures (Priority: P1)

As an operator monitoring signal generation, I need transient OANDA candle retrieval failures to retry before the signal engine makes a decision, so short-lived provider errors do not suppress otherwise valid signal evaluation.

**Why this priority**: Recent diagnostics suggest upstream candle fetch failures may be preventing signal rules from evaluating and keeping signal firing unreliable.

**Independent Test**: Can be fully tested by simulating transient OANDA responses for candle retrieval and confirming the client retries before returning data or reporting an indeterminate API/data failure.

**Acceptance Scenarios**:

1. **Given** OANDA returns a gateway timeout during candle retrieval and then succeeds, **When** the signal engine requests candles, **Then** the retry succeeds and signal evaluation uses the returned complete candles.
2. **Given** OANDA repeatedly returns transient failures during candle retrieval, **When** retries are exhausted, **Then** the opportunity is indeterminate with a precise OANDA candle-fetch diagnostic rather than a normal no-signal, trend-failed, or strategy-rejected result.
3. **Given** OANDA returns a non-retryable client error, **When** candles are requested, **Then** the failure is not retried unnecessarily and the diagnostic includes enough context to troubleshoot the request.

---

### User Story 2 - Verify OANDA Endpoint and Response Contracts (Priority: P2)

As a maintainer of the OANDA integration, I need every OANDA REST path and response parser used by the bot to match the documented v20 API, so account, pricing, position, trade, order, and candle operations do not fail because of malformed paths or incorrect assumptions.

**Why this priority**: Incorrect paths and response parsing can produce upstream failures that look like signal-engine or strategy problems.

**Independent Test**: Can be tested by auditing each client operation against the documented OANDA v20 endpoint contract and by unit testing the paths and response shapes used by the client.

**Acceptance Scenarios**:

1. **Given** practice or live OANDA base URLs with or without trailing slashes, **When** any client request path is built, **Then** the final URL contains exactly one separator between the base URL and documented path.
2. **Given** the client performs candle, pricing, account summary, account instruments, open positions, single position, close position, trade dependent-order modification, and order creation operations, **When** paths are inspected, **Then** they match the documented OANDA v20 paths.
3. **Given** OANDA returns a transaction-based order creation response, **When** the client parses it, **Then** the parser handles create, fill, cancel, reject, related transaction, and last-transaction fields without assuming a top-level order object always exists.

---

### User Story 3 - Preserve Complete-Candle Signal Inputs and Diagnostics (Priority: P3)

As an operator reviewing strategy metrics, I need failed or incomplete OANDA candle data to be diagnosed as upstream data/API failure, while complete candle windows continue into indicator and signal-rule evaluation, so metrics explain whether the blocker is the provider, data readiness, or strategy rules.

**Why this priority**: Signal reliability cannot be debugged if upstream API failures are mixed with normal no-signal, trend-threshold, or strategy-rejection outcomes.

**Independent Test**: Can be tested by feeding complete, incomplete, partial, malformed, and failed candle responses through the client and signal path and confirming the final diagnostics and metrics classification.

**Acceptance Scenarios**:

1. **Given** OANDA candle responses include complete and incomplete candles, **When** candles enter the signal engine, **Then** only complete candles are eligible for indicator windows and signal evaluation.
2. **Given** a failed or partial candle fetch prevents indicator calculation or required indicator columns from existing, **When** diagnostics are recorded, **Then** the failure is classified as an upstream OANDA/API/data failure rather than a strategy rejection.
3. **Given** complete, indicator-enriched candle data is available, **When** the signal engine evaluates a trend-valid candidate, **Then** signal-rule evaluation is not blocked by OANDA failure diagnostics.

### Edge Cases

- OANDA REST base URL configured with a trailing slash.
- OANDA stream URL configured with a trailing slash.
- Practice versus live OANDA environments.
- HTTP 429 rate-limited responses.
- HTTP 500, 502, 503, and 504 transient server or gateway responses.
- Non-retryable HTTP 4xx responses.
- Network timeouts and connection errors.
- Candle response missing the expected candle array.
- Candle response missing midpoint prices after midpoint candles were requested.
- Candle response containing incomplete active candles.
- Candle response containing fewer complete candles than the signal stack requires.
- Order creation response with create/fill transactions.
- Order creation response with reject or cancel transactions.
- Position lookup or dependent-order modification using a stale or wrong identifier.
- Metrics collection observing failures without mutating signal-engine inputs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST audit every OANDA REST path used by the integration against the official OANDA v20 documentation referenced for this feature.
- **FR-002**: The system MUST normalize configured OANDA REST and streaming base URLs so appending request paths never creates double slashes.
- **FR-003**: The system MUST use the documented OANDA practice REST base URL, live REST base URL, practice stream URL, and live stream URL defaults.
- **FR-004**: The system MUST apply a bounded request timeout to all OANDA REST calls.
- **FR-005**: The system MUST retry transient OANDA REST failures for rate limit, server error, bad gateway, service unavailable, and gateway timeout responses before surfacing failure.
- **FR-006**: The system MUST apply retry/backoff behavior to candle retrieval before the signal engine classifies the opportunity as indeterminate.
- **FR-007**: The system MUST fail non-retryable client errors promptly while preserving precise diagnostic context.
- **FR-008**: Candle requests MUST explicitly request midpoint candle data.
- **FR-009**: The internal candle representation MUST preserve whether the provider marked each candle complete.
- **FR-010**: Signal evaluation MUST build indicator windows only from candles that are complete according to provider data when that field is available.
- **FR-011**: Repeated OANDA candle retrieval failures MUST NOT be classified as valid no-signal, trend-failed, or strategy-rejected outcomes.
- **FR-012**: Repeated OANDA candle retrieval failures MUST produce precise diagnostics such as gateway timeout, rate limited, candle fetch failed, or malformed response categories.
- **FR-013**: OANDA failure diagnostics MUST include method, path, status code when available, instrument when applicable, granularity when applicable, and retry attempt metadata without exposing API tokens or secrets.
- **FR-014**: The system MUST use the documented OANDA candle, pricing, account summary, account instruments, open positions, single position, close position, trade dependent-order modification, and order creation paths.
- **FR-015**: Single-position lookup MUST target the documented instrument position resource, not an open-position identifier path.
- **FR-016**: Position close requests MUST target the documented instrument close resource.
- **FR-017**: Trade stop-loss/take-profit dependent-order modification MUST target the documented trade dependent-order resource.
- **FR-018**: Order creation response parsing MUST safely handle transaction-based response fields and MUST NOT assume a top-level order object is always present.
- **FR-019**: Missing indicator columns caused by failed, partial, or incomplete upstream candle data MUST be diagnosed as upstream data/API failure rather than strategy rejection.
- **FR-020**: Metrics collection MUST remain passive and MUST NOT mutate signal-engine inputs while recording OANDA/API/data diagnostics.
- **FR-021**: The implementation MUST NOT change signal thresholds, trend thresholds, MACD rules, entry criteria, or strategy logic unless a later separately approved feature proves complete data still fails strategy validation.
- **FR-022**: Automated tests MUST cover URL normalization, documented endpoint paths, transient retry behavior, non-retryable failures, complete candle preservation, incomplete candle exclusion, failed candle diagnostics, missing indicator-column diagnostics, and passive metrics collection.

### Key Entities

- **OANDA Endpoint Contract**: The documented method and path expected for each OANDA operation used by the bot.
- **OANDA Request Attempt**: One outbound provider request with method, path, status, attempt number, and contextual identifiers.
- **OANDA Failure Diagnostic**: A structured, non-secret record describing provider, network, timeout, rate-limit, gateway, or malformed-response failures.
- **Provider Candle**: A candle returned by OANDA, including timestamp, midpoint prices, volume, and completion status.
- **Complete Candle Window**: The provider-complete candles eligible for indicator calculation and signal evaluation.
- **Order Transaction Response**: The transaction-based response shape returned by OANDA order creation, including create, fill, cancel, reject, related transaction, and last-transaction fields.
- **Strategy Metrics Observation**: A passive diagnostic record describing the signal path outcome without changing the signal-engine inputs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of OANDA REST paths used by the client match the documented v20 endpoint paths listed in the feature request.
- **SC-002**: 100% of tested base URL variants with trailing slashes produce request URLs with no double slash after the host.
- **SC-003**: 100% of tested transient provider statuses are retried before final failure is reported.
- **SC-004**: 100% of tested non-retryable client failures fail without retry and include troubleshooting context.
- **SC-005**: 100% of tested candle responses preserve the provider completion status in the internal representation.
- **SC-006**: 100% of tested signal evaluations exclude provider-incomplete candles from indicator windows.
- **SC-007**: 100% of repeated OANDA candle fetch failures produce indeterminate API/data diagnostics rather than normal no-signal or strategy-rejected outcomes.
- **SC-008**: 100% of existing strategy thresholds and entry-rule expectations remain unchanged.
- **SC-009**: Automated regression tests cover every acceptance criterion above.

## Assumptions

- The feature targets the existing OANDA v20 integration used by TradeGumi for candle, pricing, account, position, trade, and order operations.
- OANDA documentation referenced in the feature request is the authoritative source for endpoint paths and response shapes.
- Retry behavior should be bounded so the bot does not hang indefinitely during provider outages.
- Diagnostics may add fields but must not expose API keys, authorization headers, account secrets, or raw sensitive payloads.
- Metrics and signal journal consumers can accept additive diagnostic fields as long as existing fields remain backward-compatible.

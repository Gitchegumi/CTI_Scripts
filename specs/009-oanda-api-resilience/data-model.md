# Data Model: OANDA API Resilience

## OANDA Endpoint Contract

Represents one documented provider operation used by TradeGumi.

**Fields**:

- `operation`: stable local operation name, such as candle fetch or trade dependent-order modification.
- `method`: request method.
- `path_template`: documented provider path.
- `required_context`: identifiers required to build the path, such as account, instrument, or trade specifier.

**Validation Rules**:

- Every local OANDA client operation must map to a documented method/path pair.
- Built URLs must use a normalized base URL and a path beginning with one slash.

## OANDA Request Attempt

Represents one outbound request try.

**Fields**:

- `method`
- `path`
- `status_code`
- `attempt`
- `max_attempts`
- `instrument`
- `granularity`
- `operation`

**Validation Rules**:

- Attempt metadata must not include authorization headers, API tokens, or raw secrets.
- Transient status codes are retryable; non-retryable client errors are not.

## OANDA Failure Diagnostic

Represents an exhausted, non-retryable, timeout, network, or malformed provider failure.

**Fields**:

- `stage`: provider or signal stage where failure was observed.
- `provider`: `oanda`.
- `error_type`: stable category such as `oanda_gateway_timeout`, `oanda_rate_limited`, `oanda_candle_fetch_failed`, or `oanda_response_malformed`.
- `method`, `path`, `status_code`, `instrument`, `granularity`, `attempts`.
- `message`: concise troubleshooting description.

**Validation Rules**:

- Must classify repeated candle failures as indeterminate API/data failure.
- Must not classify repeated candle failures as strategy rejection or no-signal.
- Must remain additive and backward-compatible for metrics consumers.

## Provider Candle

Represents one candle returned by OANDA.

**Fields**:

- `time`
- `open`, `high`, `low`, `close`
- `volume`
- `complete`

**Validation Rules**:

- Midpoint prices must be present when midpoint candles are requested.
- Completion status must be preserved when available.

## Complete Candle Window

Represents candles eligible for indicator calculation and signal evaluation.

**Fields**:

- `raw_count`
- `complete_count`
- `selected_last_complete_time`
- `granularity`

**Validation Rules**:

- Incomplete provider candles are excluded from signal indicator windows.
- If too few complete candles remain, the signal path reports data/API readiness failure rather than strategy rejection.

## Order Transaction Response

Represents OANDA order creation output.

**Fields**:

- `order_create_transaction_id`
- `order_fill_transaction_id`
- `order_cancel_transaction_id`
- `order_reject_transaction_id`
- `related_transaction_ids`
- `last_transaction_id`
- `accepted`
- `rejected`

**Validation Rules**:

- The parser must not require a top-level `order` object.
- Reject or cancel transaction responses must be represented safely and not parsed as successful fills.

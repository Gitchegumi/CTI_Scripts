# Contract: OANDA Failure Diagnostics

## Retryable Failure Categories

| Status | Diagnostic Category |
| --- | --- |
| 429 | `oanda_rate_limited` |
| 500 | `oanda_candle_fetch_failed` or operation-specific provider failure |
| 502 | `oanda_candle_fetch_failed` or operation-specific provider failure |
| 503 | `oanda_candle_fetch_failed` or operation-specific provider failure |
| 504 | `oanda_gateway_timeout` |

Network timeouts and connection errors should use operation-specific provider failure categories and include attempt metadata.

## Required Context

OANDA failure diagnostics must include:

- `provider`: `oanda`
- `method`
- `path`
- `status_code` when available
- `instrument` when applicable
- `granularity` when applicable
- `attempts`
- `max_attempts`
- `retryable`
- `message`

Diagnostics must not include:

- API tokens
- Authorization headers
- Raw secret-bearing request headers
- Full account credentials beyond already configured non-secret identifiers needed for troubleshooting

## Signal Outcome Mapping

When candle retrieval fails repeatedly:

- `final_decision`: existing indeterminate decision state
- `decision_reason`: provider/API/data failure, such as `oanda_candle_fetch_failed`, `oanda_gateway_timeout`, or `oanda_rate_limited`
- `blocking_layer`: `data_quality` or existing API/engine layer mapping
- `first_blocker` and `all_blockers`: include the provider failure category
- Signal rules are not considered evaluated
- Strategy rejection and no-trend classifications must not be used for provider failures

When OANDA returns complete candle data:

- OANDA failure diagnostics must not be attached.
- Complete candles may proceed into existing readiness checks and signal rules.
- Existing strategy rejection semantics remain unchanged.

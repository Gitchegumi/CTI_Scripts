# Contract: Oanda Pricing Stream Provider

## Endpoint

Use the configured Oanda streaming base URL:

- Practice: `https://stream-fxpractice.oanda.com/`
- Live: `https://stream-fxtrade.oanda.com/`

Pricing stream path:

```text
GET /v3/accounts/{accountID}/pricing/stream?instruments={OANDA_INSTRUMENTS}
```

## Authentication

The provider must send the Oanda personal access token as a bearer token:

```text
Authorization: Bearer <TOKEN>
```

Logs must never include token values.

## Request Parameters

- `accountID`: configured Oanda account id.
- `instruments`: comma-separated Oanda instrument names converted from CTI symbols.
- `snapshot`: default provider behavior is acceptable unless implementation chooses to disable initial snapshots for a documented reason.

## Response Handling

Oanda returns a chunked `application/octet-stream` response. Each JSON object is serialized on a single line. Supported event types:

### Price Event

Expected fields:

- `instrument`
- `time`
- `bids`
- `asks`
- optional `status`

Mapping:

- Convert `instrument` to CTI symbol with `config.from_oanda_symbol`.
- Use first bid and ask price when present.
- Publish `PriceObservation(source=OANDA_PRICING_STREAM)`.
- Ignore or log unsupported/unmapped instruments safely.

### Heartbeat Event

Expected fields:

- `type`: `HEARTBEAT`
- `time`

Mapping:

- Update stream liveness and heartbeat age.
- Do not publish a `PriceObservation`.

## Limits and Reliability

- Respect 20 active streams per requesting IP.
- Respect no more than 2 new connections per second.
- Use one persistent pricing stream for the current watchlist when streaming is healthy.
- Reconnect with bounded backoff after disconnects or stale heartbeat timeout.
- Fall back to polling after repeated failures.
- Stop retrying or enter polling fallback after the configured reconnect tolerance is exceeded.

## Error Handling

- 401/authentication errors: log clear safe error and activate fallback.
- 429/rate or connection-limit responses: back off and avoid reconnect loops.
- Malformed lines: log DEBUG/WARNING based on frequency and continue unless repeated failures exceed threshold.
- Unknown event types: log DEBUG/WARNING based on severity and continue.
- Network disconnect: transition to reconnecting, then running or fallback.
- Practice/live stream base URL selection must use existing environment-specific configuration rather than hard-coded endpoint strings in the provider loop.

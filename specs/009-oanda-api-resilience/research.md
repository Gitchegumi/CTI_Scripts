# Research: OANDA API Resilience

## Decision: Use official OANDA v20 endpoint paths as the audit source

**Rationale**: The user supplied the authoritative OANDA v20 documentation URLs. The docs confirm REST bases for practice/live, streaming bases, candles at `/v3/instruments/{instrument}/candles`, pricing at `/v3/accounts/{accountID}/pricing`, account summary/instruments paths, open/single/close position paths, trade dependent-order modification at `/v3/accounts/{accountID}/trades/{tradeSpecifier}/orders`, and transaction-based order creation responses.

**Alternatives considered**:

- Keep existing paths where tests are absent: rejected because several current paths visibly differ from the documented API.
- Defer endpoint audit until after retry work: rejected because wrong paths can masquerade as resilience failures.

## Decision: Normalize base URLs once before path concatenation

**Rationale**: Config defaults are already correct, but user-provided env values may include trailing slashes. Normalizing `OANDA_BASE_URL` and `OANDA_STREAM_URL` prevents double slash URL defects while preserving env-driven operation.

**Alternatives considered**:

- Normalize every individual call site: rejected as duplicated and easier to miss.
- Require users to configure slash-free URLs: rejected as brittle operational behavior.

## Decision: Add bounded request timeout and retry/backoff in the OANDA request wrapper

**Rationale**: A single authenticated request wrapper is the narrowest place to cover all OANDA REST calls. Transient statuses 429, 500, 502, 503, and 504 should retry with bounded backoff before surfacing failure. Non-retryable 4xx should fail immediately.

**Alternatives considered**:

- Retry only candle calls: rejected because pricing/account/order calls also need provider diagnostics and timeout safety.
- Retry indefinitely: rejected because it can stall the signal loop.

## Decision: Raise structured OANDA request errors for exhausted or malformed responses

**Rationale**: The signal engine needs to distinguish upstream provider failure from normal no-signal, trend failure, data-not-ready, and strategy rejection. A structured exception carrying method, path, status, instrument, granularity, and attempts gives diagnostics without leaking secrets.

**Alternatives considered**:

- Return empty lists from failed OANDA calls: rejected because empty data looks like normal no-candle/no-signal input.
- Log only and suppress exceptions: rejected because metrics cannot classify provider failures accurately.

## Decision: Preserve provider `complete` on `Candle` and filter by completion before signal indicators

**Rationale**: OANDA candle data includes a `complete` flag. Time-based closure inference is useful, but provider completion should be preserved and honored so active incomplete candles do not enter indicator windows.

**Alternatives considered**:

- Infer closure only from timestamps: rejected because the provider explicitly marks completeness and the user requested preservation.
- Drop incomplete candles inside only the OANDA client: rejected because the signal engine and tests should be able to observe and enforce completion consistently across providers.

## Decision: Parse order creation as transaction-based response

**Rationale**: OANDA order creation responses include fields such as `orderCreateTransaction`, `orderFillTransaction`, `orderCancelTransaction`, `orderRejectTransaction`, `relatedTransactionIDs`, and `lastTransactionID`. The current top-level `order` assumption is incompatible.

**Alternatives considered**:

- Return only `lastTransactionID`: rejected because callers need a stable useful identifier and reject/cancel responses must be distinguished.
- Keep top-level `order` fallback only: rejected because documented responses are transaction-based.

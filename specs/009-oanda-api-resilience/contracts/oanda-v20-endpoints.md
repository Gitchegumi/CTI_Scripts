# Contract: OANDA v20 Endpoints Used By TradeGumi

Sources:

- OANDA Development Guide: `https://developer.oanda.com/rest-live-v20/development-guide/`
- OANDA Instrument Endpoints: `https://developer.oanda.com/rest-live-v20/instrument-ep/`
- OANDA Pricing Endpoints: `https://developer.oanda.com/rest-live-v20/pricing-ep/`
- OANDA Account Endpoints: `https://developer.oanda.com/rest-live-v20/account-ep/`
- OANDA Position Endpoints: `https://developer.oanda.com/rest-live-v20/position-ep/`
- OANDA Trade Endpoints: `https://developer.oanda.com/rest-live-v20/trade-ep/`
- OANDA Order Endpoints: `https://developer.oanda.com/rest-live-v20/order-ep/`

## Base URLs

| Environment | REST Base | Stream Base |
| --- | --- | --- |
| Practice | `https://api-fxpractice.oanda.com` | `https://stream-fxpractice.oanda.com` |
| Live | `https://api-fxtrade.oanda.com` | `https://stream-fxtrade.oanda.com` |

Base URLs must be normalized by removing trailing slashes before request paths are appended.

## REST Paths

| Operation | Method | Path |
| --- | --- | --- |
| Candle fetch | GET | `/v3/instruments/{instrument}/candles` |
| Pricing | GET | `/v3/accounts/{accountID}/pricing` |
| Account summary | GET | `/v3/accounts/{accountID}/summary` |
| Account instruments | GET | `/v3/accounts/{accountID}/instruments` |
| Open positions | GET | `/v3/accounts/{accountID}/openPositions` |
| Single position | GET | `/v3/accounts/{accountID}/positions/{instrument}` |
| Close position | PUT | `/v3/accounts/{accountID}/positions/{instrument}/close` |
| Trade dependent orders | PUT | `/v3/accounts/{accountID}/trades/{tradeSpecifier}/orders` |
| Order creation | POST | `/v3/accounts/{accountID}/orders` |

## Candle Request Requirements

- Candle requests must include `price=M`.
- Candle responses must preserve the provider `complete` field.
- If midpoint prices are missing from a candle response, the response is malformed.

## Order Creation Response Requirements

Order creation parsing must handle transaction-based fields, including:

- `orderCreateTransaction`
- `orderFillTransaction`
- `orderCancelTransaction`
- `orderRejectTransaction`
- `relatedTransactionIDs`
- `lastTransactionID`

The parser must not assume a top-level `order` object exists.

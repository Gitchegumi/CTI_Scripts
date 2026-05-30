# Rollback and Observability Notes: Pullback Signal Bridge and Shock Suppression

## Rollback Strategy

- Keep all new thresholds configuration-driven so operators can disable or neutralize the new pullback path without removing continuation behavior.
- Recommended rollback switch: add a pullback enable flag during implementation, default enabled only after approval; setting it false should leave continuation `CTI-v1.1-continuation-test` behavior active.
- Keep volatility shock enablement under `VOLATILITY_SHOCK_ENABLED`; if a production issue appears, operators can disable shock suppression while retaining existing LR/trend behavior.
- Do not migrate or rewrite existing journal rows. Historical `CTI-v1.1-continuation-test` rows remain as-is; new pullback rows use `CTI-v1.2-pullback`.
- Any database schema additions in strategy metrics should be additive nullable columns with safe defaults so rollback does not require destructive migration.

## Observability Requirements

Strategy metrics must make pullback funnel health visible through:

- candidates skipped by 1h anchor
- candidates where 15m bridge allowed flat/weak current 15m
- candidates rejected by strong opposite 15m
- candidates rejected by 5m structure
- candidates rejected by KC pullback sequence
- candidates rejected by trigger candle
- candidates rejected by Stoch RSI
- candidates where MACD affected soft score only
- candidates blocked by volatility shock suppression

Signal Journal exports must preserve:

- `strategy`
- `signal_type`
- pullback bridge status
- pullback trigger pattern
- pullback rejection reason where applicable
- shock detected true/false
- shock timeframe
- shock candle time
- shock true range
- shock ATR
- shock ATR multiple
- shock suppression until
- shock suppression candles remaining
- whether a signal was blocked by shock suppression

## Alerting and Logs

- Shock detection logs should include symbol, timeframe, rule, candle time, true range, ATR, ATR multiple, suppression until, and candles remaining.
- Pullback bridge logs should be DEBUG-level unless a signal is emitted or blocked by market invalidity.
- No logs should include credentials, account IDs beyond existing safe behavior, or broker auth headers.

## Forward-Test Guardrail

After implementation, run in `alert_only` for at least one market week before any demo/live promotion. Review pullback signals separately from continuation signals using the required strategy labels and metrics filters.

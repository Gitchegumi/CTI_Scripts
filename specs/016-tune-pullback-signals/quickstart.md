# Quickstart: Tune Pullback Signal Alerts

## Prerequisites

- Work from branch `016-tune-pullback-signals`.
- Keep the feature pointer at `specs/016-tune-pullback-signals`.
- Use alert/demo validation only; funded/live promotion is out of scope for this feature.
- Use these baseline files when checking before/after behavior:
  - `C:/Users/User/Downloads/tradegumi 20260605/signal-journal-all-2026-06-05.csv`
  - `C:/Users/User/Downloads/tradegumi 20260605/strategy-metrics-2026-06-01-to-2026-06-05.json`

## Targeted Validation Commands

```powershell
pytest src/tradegumi/tests/test_signal_engine.py -q
pytest src/tradegumi/tests/test_strategy_metrics.py -q
pytest src/tradegumi/tests/test_journal.py -q
```

Run dashboard checks only if dashboard types or UI are changed:

```powershell
corepack pnpm --dir dashboard lint
npm run build
```

## Required Scenarios

1. Valid BUY pullback
   - Larger uptrend remains valid.
   - Price pulled back into the configured value area after prior trend-side outer move.
   - Trigger candle has small body and long lower wick near or through the value area.
   - Recent Stoch RSI exhaustion or recovery evidence exists.
   - Expected result: `CTI-v1.2-pullback`, `signal_type=pullback`, BUY alert and journal row.

2. Valid SELL pullback
   - Larger downtrend remains valid.
   - Price pulled back into the configured value area after prior trend-side outer move.
   - Trigger candle has small body and long upper wick near or through the value area.
   - Recent Stoch RSI exhaustion or roll-down evidence exists.
   - Expected result: `CTI-v1.2-pullback`, `signal_type=pullback`, SELL alert and journal row.

3. Invalid trigger candle
   - Trend and value-area context pass.
   - Candle has a large body, wrong wick direction, or no meaningful rejection.
   - Expected result: no pullback alert; blocker is `pullback_trigger_candle_failed`.

4. Invalid value-area sequence
   - Trigger candle and exhaustion evidence are acceptable.
   - Prior trend-side outer move is missing or price is outside the configured value-area zone.
   - Expected result: no pullback alert; blocker is `pullback_kc_sequence_failed`.

5. Invalid exhaustion
   - Trend, value-area, and trigger candle context pass.
   - Stoch RSI exhaustion is absent or stale.
   - Expected result: no pullback alert; blocker is `pullback_stoch_rsi_failed`.

6. MACD soft default
   - All pullback gates pass.
   - MACD disagrees.
   - Expected result: pullback may still emit; MACD is recorded as diagnostic/confidence context.

7. MACD explicit hard block
   - Same setup as MACD soft default.
   - Explicit pullback MACD hard-block setting is enabled.
   - Expected result: MACD can block and is counted as a pullback blocker.

8. Reporting/export validation
   - Run a mixed period with pass, fail, near-miss, emitted, journaled, and prime-suppressed pullbacks.
   - Expected result: strategy metrics show evaluated/rejected/emitted/journaled/suppressed pullback counts and Signal Journal exports include pullback rows.

## Operator Review

- Compare metrics against the attached June 1-5 baseline: 92 journal rows, all continuation, zero pullback journal rows, 1,542 pullback-type opportunities, 2 `CTI-v1.2-pullback` strategy counts, and 92.83% pullback-trigger failure.
- Confirm the tuned run improves the three measured choke points without weakening structure: trigger candle 7.17% pass baseline, Keltner pullback sequence 18.20% pass baseline, Stoch RSI 35.25% pass baseline, and pullback structure 94.64% pass baseline.
- Confirm improvements come from valid pullback fixtures and representative replay data, not from accepting weak or structure-broken setups.
- Confirm continuation rows remain labeled and reportable separately from pullback rows.

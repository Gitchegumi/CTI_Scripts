# Test Plan: Pullback Signal Bridge and Shock Suppression

## Targeted Suites

- `python -m pytest src/tradegumi/tests/test_signal_engine.py -q`
- `python -m pytest src/tradegumi/tests/test_volatility_shock.py -q`
- `python -m pytest src/tradegumi/tests/test_strategy_metrics.py -q`
- `python -m pytest src/tradegumi/tests/test_journal.py -q`

## Pullback Allowed Cases

- Long pullback with prior M15 uptrend memory, current M15 flat, H1 uptrend intact, M5 HH/HL, prior upper KC break, midline retracement, hammer trigger, Stoch RSI oversold: emits BUY `CTI-v1.2-pullback`.
- Long pullback with the same setup and bullish engulfing trigger: emits BUY `CTI-v1.2-pullback`.
- Short pullback with prior M15 downtrend memory, current M15 flat, H1 downtrend intact, M5 LH/LL, prior lower KC break, midline retracement, shooting star trigger, Stoch RSI overbought: emits SELL `CTI-v1.2-pullback`.
- Short pullback with the same setup and bearish engulfing trigger: emits SELL `CTI-v1.2-pullback`.

## Continuation Regression

- Existing continuation signal fixtures still emit when current continuation gates pass.
- Continuation signals always carry strategy `CTI-v1.1-continuation-test` and signal type `continuation`.
- Continuation metrics and journal rows preserve those values.

## Pullback Reject Cases

- Current M15 strongly opposite rejects pullback with a strong-opposite bridge blocker.
- Pullback violates recent higher low/lower high and rejects with structure blocker.
- Prior KC band break is missing and rejects with Keltner sequence blocker.
- Trigger candle is generic, absent, or directionally wrong and rejects with trigger blocker.
- Long trigger is not hammer or bullish engulfing and rejects.
- Short trigger is not shooting star or bearish engulfing and rejects.
- Stoch RSI is not exhausted or recovering/rolling from exhaustion and rejects.
- MACD failure alone does not reject an otherwise valid pullback.

## Shock Tests

- M5 true range >= 4.0x prior ATR suppresses both continuation and pullback candidates.
- M15 true range >= 3.5x prior ATR suppresses both continuation and pullback candidates for the translated window.
- Body >= 3.0x ATR and range >= 3.5x ATR suppresses entries.
- Below-threshold shock fixtures do not suppress.
- Active suppression blocks regardless of candidate direction and regardless of whether filtered LR changed trend.
- Shock filtering that removes too many LR candles produces no-trade/indeterminate diagnostics, not raw-LR fallback.

## Metrics and Journal Tests

- `SignalDiagnostic.to_opportunity()` or equivalent persistence maps emitted continuation rows to `CTI-v1.1-continuation-test`/`continuation`.
- Emitted pullback rows map to `CTI-v1.2-pullback`/`pullback`.
- Strategy metrics summary/export distinguish strategy and signal type counts.
- Signal Journal export includes strategy, signal type, pullback trigger, pullback bridge status, and shock suppression diagnostics.
- Threshold hash changes when pullback memory/KC/Stoch/shock thresholds change.

## Manual Review Checklist

- Review one emitted continuation diagnostic and one emitted pullback diagnostic side by side.
- Confirm pullback blockers are legible in metrics without inspecting raw code.
- Confirm shock suppression logs include timeframe, candle time, true range, ATR, ATR multiple, suppression until, and candles remaining.
- Confirm no risk, execution, or provider behavior changed.

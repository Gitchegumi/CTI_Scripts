# Contract: Signal pipeline progression

## Contract Goals

- Preserve strategy thresholds and layer order.
- Ensure trend-valid candidates can reach signal rule evaluation when signal data is complete and the M5 candle is closed.
- Record accurate diagnostics for missing data and gate waiting without breaking evaluation.

## Canonical Pipeline

```text
trend detection
  -> signal data preparation
  -> candle close gate
  -> signal rules evaluation
  -> signal emitted | signal rejected
```

## Required Behaviors

| Scenario | Expected behavior | Required diagnostic |
| --- | --- | --- |
| Insufficient candles | Candidate does not index past available candles; evaluation records missing data. | `signal_engine_data` with missing input and available/required context. |
| Exactly enough candles | Signal data preparation succeeds when the complete required window exists. | `signal_engine_data` complete. |
| Current candle still open | Candle-close gate waits or defers; candidate remains eligible for later evaluation. | `candle_close_gate` waiting with seconds until close. |
| Exact M5 close boundary | Candle-close gate passes deterministically. | `candle_close_gate` passed. |
| After M5 close boundary | Gate passes for the correct last closed candle. | `candle_close_gate` passed. |
| Complete trend-valid candidate | Signal rules are evaluated and result is emitted or rejected by rule logic. | `signal_rules_evaluated` increments; final reason reflects rule outcome. |

## Diagnostic Naming

- `signal_engine_data` is canonical.
- `singal_engine_data` is treated as a legacy misspelling only for compatibility or migration.

## Prohibited Behaviors

- Do not loosen thresholds as a pipeline repair.
- Do not force candle gates to pass before close.
- Do not mask expected missing data with broad exception handlers.
- Do not allow diagnostic recording failures to abort the trading/signal path.

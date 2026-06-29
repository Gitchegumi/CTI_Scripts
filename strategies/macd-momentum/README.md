# MACD Zero-Line Momentum — second reference strategy

A small, self-contained strategy that exists mainly to **prove the plugin
contract**: TradeGumi discovers and loads it alongside `example-strategy` with no
change to core runtime code, and it ships with only the two required files.

| File            | Required | Present here |
|-----------------|----------|--------------|
| `strategy.json` | Yes      | ✅ metadata |
| `strategy.py`   | Yes      | ✅ `get_strategy()` + `evaluate()` |
| `indicators.py` | Optional | ❌ (reuses `tradegumi.indicators`) |
| `management.py` | Optional | ❌ (uses the default no-op `manage_open_trade`) |
| `config.py`     | Optional | ❌ (risk knobs are constants in `strategy.py`) |

## Logic

In an `Uptrend`/`Downtrend` (supplied by the framework trend filter), enter when
the MACD histogram crosses the zero line in the trend direction. Stops and targets
are ATR multiples (`SL_ATR_MULTIPLIER` / `TP_ATR_MULTIPLIER` in `strategy.py`).

It does **not** manage open trades — `BaseStrategy.manage_open_trade` declines by
default, demonstrating that continuation/management is an opt-in hook.

See [`docs/strategy-plugins.md`](../../docs/strategy-plugins.md) for the full
folder contract and interface.

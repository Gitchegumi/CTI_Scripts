# Example Strategy — CTI Pullback with Continuation Management

This is the **reference TradeGumi strategy plugin**. It is a real, executable
strategy (not just metadata): TradeGumi discovers it, loads it, and runs its
decision logic without any change to core runtime code.

## Folder contract

| File            | Required | Purpose |
|-----------------|----------|---------|
| `strategy.json` | Yes      | Metadata (`id`, `label`, `description`, `signal_type`, `entrypoint`). Surfaces in the dashboard strategy dropdown. |
| `strategy.py`   | Yes      | Exposes `get_strategy() -> BaseStrategy`. Owns the signal *decision* logic. |
| `indicators.py` | Optional | Strategy-specific indicators / structure helpers. |
| `management.py` | Optional | Trade-management helpers (risk/exit placement, confidence scoring). |
| `README.md`     | Optional | Notes for this strategy. |
| `tests/`        | Optional | Strategy-specific tests. |

## How the runtime loads a strategy

`tradegumi.strategy_loader.load_strategy()` resolves a folder under the configured
strategies directory (`STRATEGIES_DIR`, default `./strategies`), imports its
`strategy.py` as a synthetic package (so relative imports like
`from .indicators import …` work even though the folder name contains a hyphen),
and calls the module-level `get_strategy()` factory. The returned object must be a
`tradegumi.strategy_loader.BaseStrategy`.

`SignalEngine` loads its strategy once at construction (default:
`example-strategy`, overridable with the `TRADEGUMI_STRATEGY` env var) and calls:

- `strategy.evaluate(engine, ctx)` — the 4-layer signal stack + continuation/
  pullback dual path. Returns a `StrategyDecision(signal, criteria, reason,
  confidence)`.
- `strategy.bridge_trend(engine, lr_1h, lr_15m, candles_15m)` — optional hook to
  salvage a directional bias from recent M15 memory when the trend filter is flat.

The framework provides everything else: market data access, the linear-regression
trend filter, volatility-shock and chop/regime filters, the candle-close gate,
cooldown, diagnostics persistence, and position sizing.

## Creating a new strategy

```bash
cp -r strategies/example-strategy strategies/my-strategy
```

1. Edit `strategies/my-strategy/strategy.json` (`id` must be unique).
2. Edit `strategy.py` (and `indicators.py` / `management.py`) with your rules.
3. Point the runtime at it with `TRADEGUMI_STRATEGY=my-strategy` (or its `id`).

Sibling folders other than `example-strategy/` are gitignored, so your private
strategies stay local. Backtesting and strategy research live in **QuantPipe** —
TradeGumi only runs validated strategies for live/forward execution.

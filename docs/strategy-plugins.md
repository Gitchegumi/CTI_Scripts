# Strategy Plugins

TradeGumi strategies are **plugin folders**, not core code. The runtime provides
the framework — market data, the linear-regression trend filter, volatility-shock
and chop/regime filters, the candle-close gate, cooldown, diagnostics
persistence, position sizing, dashboard/API integration, and strategy discovery —
and each strategy folder provides the *behavior*: what qualifies as a setup, how
entries are evaluated, how stops/targets are placed, how open trades are managed,
and any strategy-specific indicators.

You can add a new strategy by **copying a folder** and editing the files inside
it. No TradeGumi core module needs to change.

## Folder template

```text
strategies/
└── my-strategy/
    ├── strategy.json     # required — metadata (id, label, description, …)
    ├── strategy.py       # required — exposes get_strategy() -> BaseStrategy
    ├── indicators.py     # optional — strategy-specific indicators
    ├── management.py     # optional — trade-management / risk helpers
    ├── config.py         # optional — strategy-specific config / knobs
    ├── README.md         # optional — notes for this strategy
    └── tests/            # optional — strategy-specific tests / fixtures
```

Only `strategy.json` and `strategy.py` are required. The two bundled references
show both ends of the spectrum:

- **`strategies/example-strategy/`** — a full strategy (CTI pullback + continuation
  management) using `indicators.py` and `management.py`.
- **`strategies/macd-momentum/`** — a minimal strategy (just the two required
  files) that reuses framework indicators and the default management hook.

> Sibling folders other than the bundled references are gitignored, so your own
> strategies stay local. Backtesting/research lives in **QuantPipe** — TradeGumi
> runs validated strategies for live/forward execution.

## `strategy.json`

```json
{
  "id": "my-strategy",
  "label": "My Strategy",
  "description": "What it does.",
  "signal_type": "pullback",
  "entrypoint": "strategy.py"
}
```

`id` must be unique. It is how the runtime and dashboard refer to the strategy
(`TRADEGUMI_STRATEGY=<id-or-folder-name>`), and it surfaces in the dashboard
strategy dropdown via `tradegumi.strategy_registry`.

## The interface

`strategy.py` must expose a module-level `get_strategy()` factory returning a
`tradegumi.strategy_loader.BaseStrategy`:

```python
from tradegumi.strategy_loader import BaseStrategy, StrategyDecision

class MyStrategy(BaseStrategy):
    id = "my-strategy"

    def evaluate(self, engine, ctx) -> StrategyDecision:
        ...

def get_strategy() -> MyStrategy:
    return MyStrategy()
```

### `evaluate(engine, ctx) -> StrategyDecision` (required)

The signal decision. `ctx` is a `StrategyContext` carrying everything needed to
decide without re-fetching market data (symbol, trend, candles, the closed
indicator window, pre-seeded criteria, trend/shock diagnostics, …). Return a
`StrategyDecision(signal, criteria, reason, confidence)` — `signal` is a
`tradegumi.signal_engine.Signal` or `None`.

### `bridge_trend(engine, lr_1h, lr_15m, candles_15m)` (optional)

Salvage a directional bias when the trend filter is flat. Default: no bridging.

### `manage_open_trade(ctx) -> TradeManagementDecision` (optional)

Owns **continuation / open-trade management**. When a same-direction continuation
fires against an active trade, core builds a journal-free `ManagedTradeContext`
(direction, entry, current SL/TP, risk, price-at-event, extension count, dedup
flag) and asks the strategy what to do. The strategy returns a
`TradeManagementDecision` (accept/reject, new SL/TP, flags). **Core owns
detection and persistence; the strategy owns the decision.** The default declines
(`management_not_implemented`), so a strategy that only emits entries works
unchanged. `example-strategy` implements break-even → profit-protect → TP
extension in its `management.py`.

## Discovery & validation

- **Metadata** for the dashboard dropdown: `strategy_registry.get_strategies()`
  scans folders and reads `strategy.json` (tolerant of missing/malformed files —
  they surface as warnings, not crashes).
- **Interface validation:** `strategy_loader.discover_strategies()` actually
  loads every folder and confirms it exposes a `get_strategy()` returning a
  `BaseStrategy`, reporting each as `ok` or with a useful `error`. The worker runs
  this at startup (`tradegumi.main.run`) and logs a line per strategy, so a broken
  folder is obvious immediately instead of failing lazily mid-scan.
- **Loading:** `strategy_loader.load_strategy(<id-or-folder>)` imports the folder
  as a synthetic package (so relative imports like `from .indicators import …`
  work even with a hyphenated folder name) and returns the instance. `SignalEngine`
  loads the default (`example-strategy`, override with `TRADEGUMI_STRATEGY`) once
  at construction.

## Add a new strategy

```bash
cp -r strategies/example-strategy strategies/my-strategy   # or macd-momentum for a minimal start
```

1. Edit `strategies/my-strategy/strategy.json` (`id` must be unique).
2. Edit `strategy.py` (and `indicators.py` / `management.py` if you use them).
3. Point the runtime at it: `TRADEGUMI_STRATEGY=my-strategy`.
4. Confirm it validates:
   `python -c "from tradegumi.strategy_loader import discover_strategies; print(discover_strategies())"`.

# Archived: legacy `trading_scripts` strategies

These are frozen MT5-era research/automation scripts (`supertrend_strat.py`,
`trailing_sl_atr.py`, `weekday_entries.py`). They predate TradeGumi and are **not
part of the runtime** — they import the sibling `trading_scripts.api` package and
will not run as-is from this archive location.

They are kept here for historical reference only. Current, living strategy logic
lives under `strategies/` (see `strategies/example-strategy/`). New strategies
follow that plugin-folder contract, not this layout.

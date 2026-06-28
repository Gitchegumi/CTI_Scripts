# Archived: backtesting / strategy research

Backtesting, historical simulation, and strategy research are **owned by
QuantPipe**, not TradeGumi. TradeGumi consumes validated strategy logic for
live/forward execution only.

The contents here (historical CSV data under `back_test_data/`, `get_data.py`,
`testing.ipynb`, and the `plotly/` exports) are frozen for history. The
`backtrader` dependency and the `back_testing` Poetry group were removed from
`src/pyproject.toml` as part of this move. Do not add backtesting/research
machinery back into TradeGumi — put it in QuantPipe.

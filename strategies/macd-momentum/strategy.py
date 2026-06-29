"""MACD zero-line momentum — second reference TradeGumi strategy plugin.

A deliberately small, self-contained strategy that proves the plugin contract:
TradeGumi discovers and runs it with **no change to core runtime code**, and it
needs none of the optional folder files (``indicators.py`` / ``management.py`` /
``config.py``). It enters when the MACD histogram crosses the zero line in the
direction of the framework-supplied trend, places ATR-based stops, and relies on
the default (no-op) ``manage_open_trade`` from ``BaseStrategy``.

Copy this folder (or ``example-strategy``) to start a new strategy — see
``README.md`` and ``docs/strategy-plugins.md``.
"""
from __future__ import annotations

import json
from pathlib import Path

from tradegumi import config
from tradegumi.indicators import calculate_atr, calculate_macd, candles_to_df
from tradegumi.signal_engine import (
    Signal,
    _criterion,
    _first_matching_column,
    _price_decimals,
)
from tradegumi.strategy_loader import BaseStrategy, StrategyContext, StrategyDecision

_METADATA_PATH = Path(__file__).resolve().parent / "strategy.json"

# Strategy-owned risk knobs. Edit these in your copy without touching core.
SL_ATR_MULTIPLIER = 1.5
TP_ATR_MULTIPLIER = 3.0
MIN_WINDOW = 35


def _load_metadata() -> dict:
    try:
        return json.loads(_METADATA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


class MacdMomentumStrategy(BaseStrategy):
    """Enter on a MACD histogram zero-line cross aligned with the trend."""

    def __init__(self) -> None:
        self.metadata = _load_metadata()
        self.id = self.metadata.get("id", "macd-momentum")

    def evaluate(self, engine, ctx: StrategyContext) -> StrategyDecision:
        trend = ctx.trend
        criteria = ctx.criteria
        closed_window = ctx.closed_window

        if trend not in ("Uptrend", "Downtrend"):
            return StrategyDecision(None, criteria, "no_trend", None)
        if len(closed_window) < MIN_WINDOW:
            return StrategyDecision(None, criteria, "signal_stack_data_not_ready", None)

        df = candles_to_df(closed_window)
        macd_df = calculate_macd(df, fast=12, slow=26, signal=9)
        hist_col = _first_matching_column(macd_df, lambda name: "h" in name, "macd_histogram")
        hist = macd_df[hist_col].dropna()
        if len(hist) < 2:
            return StrategyDecision(None, criteria, "signal_stack_data_not_ready", None)

        current = float(hist.iloc[-1])
        prev = float(hist.iloc[-2])
        if trend == "Uptrend":
            crossed = prev <= 0 < current
        else:
            crossed = prev >= 0 > current

        criteria.append(_criterion(
            "macd_zero_cross", "signal_stack",
            {"prev": prev, "current": current},
            "histogram crosses zero in trend direction",
            bool(crossed), abs(current),
        ))
        if not crossed:
            return StrategyDecision(None, criteria, "criteria_failed", None)

        atr = float(calculate_atr(df).iloc[-1])
        last_close = float(df["c"].iloc[-1])
        decimals = _price_decimals(last_close)
        if trend == "Uptrend":
            sl = round(last_close - atr * SL_ATR_MULTIPLIER, decimals)
            tp = round(last_close + atr * TP_ATR_MULTIPLIER, decimals)
        else:
            sl = round(last_close + atr * SL_ATR_MULTIPLIER, decimals)
            tp = round(last_close - atr * TP_ATR_MULTIPLIER, decimals)

        # Confidence scales with how decisively the histogram cleared zero.
        confidence = round(min(0.99, 0.5 + min(abs(current) / (atr or 1e-9), 0.49)), 3)
        breakdown = {"macd": confidence}

        return StrategyDecision(Signal(
            symbol=ctx.symbol,
            direction=trend,
            entry_price=round(last_close, decimals),
            stop_loss=sl,
            take_profit=tp,
            atr=round(atr, 6),
            lot_size=0.0,
            risk_pct=config.RISK_PER_TRADE * 100,
            confidence=confidence,
            breakdown=breakdown,
            trend_direction=trend,
            patterns_found=[],
            strategy="macd-momentum-v1",
            signal_type="momentum",
            macd_histogram=current,
            signal_price=round(last_close, decimals),
            suggested_entry=round(last_close, decimals),
        ), criteria, "emitted", confidence)


def get_strategy() -> MacdMomentumStrategy:
    """Factory used by the TradeGumi strategy loader."""
    return MacdMomentumStrategy()

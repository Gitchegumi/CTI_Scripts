"""Trade-management helpers for the example pullback strategy.

Pure helpers used by ``strategy.py`` for risk/exit placement and confidence
scoring. Kept separate so the strategy's trade-management knobs are easy to find
and override when copying this folder into a new strategy.
"""
from __future__ import annotations

from tradegumi import config
from tradegumi.signal_engine import _price_decimals

# Signals below this weighted confidence are too weak to act on. Applies to both
# the continuation and pullback paths.
MIN_CONFIDENCE = 0.55


def compute_sl_tp(entry_price: float, atr: float, trend: str) -> tuple[float, float]:
    """ATR-based stop-loss / take-profit, rounded to the instrument's precision."""
    if trend == "Uptrend":
        sl = entry_price - (atr * config.SL_ATR_MULTIPLIER)
        tp = entry_price + (atr * config.TP_ATR_MULTIPLIER)
    else:
        sl = entry_price + (atr * config.SL_ATR_MULTIPLIER)
        tp = entry_price - (atr * config.TP_ATR_MULTIPLIER)
    decimals = _price_decimals(entry_price)
    return round(sl, decimals), round(tp, decimals)


def continuation_confidence(breakdown: dict) -> float:
    """Weighted confidence for the continuation path (no stoch/candle requirement)."""
    return (
        breakdown["macd"] * 0.35
        + breakdown["keltner"] * 0.25
        + breakdown["trend"] * 0.20
        + breakdown["structure"] * 0.20
    )


def pullback_confidence(breakdown: dict) -> float:
    """Weighted confidence for the pullback path (candle optional — lower weight)."""
    return (
        breakdown["stoch_rsi"] * 0.30
        + breakdown["macd"] * 0.25
        + breakdown["keltner"] * 0.20
        + breakdown["trend"] * 0.15
        + breakdown["candlestick"] * 0.10
    )

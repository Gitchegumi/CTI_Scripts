"""Pullback strategy indicators / structure helpers.

Strategy-specific decision helpers for the example pullback strategy. These were
previously embedded in ``tradegumi.signal_engine``; they live here now so the
strategy owns its own rules. Shared, generic indicator math (Stoch RSI, MACD,
Keltner, ATR, linear regression, scoring) remains in ``tradegumi.indicators``
and is consumed by ``strategy.py``.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

import pandas as pd

from tradegumi import config
from tradegumi.signal_engine import _lr_direction


def classify_pullback_trend_bridge(
    lr_1h: object,
    current_lr_15m: object,
    recent_lr_15m: Sequence[object],
    trend: str,
    threshold_1h: float,
    threshold_15m: float,
    *,
    memory_candles: int,
    strong_opposite_multiplier: float,
) -> dict:
    """Evaluate whether recent M15 memory bridges a current pullback flattening.

    Pullback entries need the H1 anchor to remain aligned while allowing the
    current M15 LR to flatten. A current M15 reading that is strongly opposite
    the desired direction rejects the bridge even if older memory was aligned.

    Note: trend=None is intentionally not handled here — callers that pass a flat/
    unknown trend should not be building pullback bridges at all.
    """
    desired = "up" if trend == "Uptrend" else "down"
    opposite = "down" if desired == "up" else "up"
    try:
        h1 = float(lr_1h)
        m15 = float(current_lr_15m)
    except (TypeError, ValueError):
        return {"passed": False, "status": "pullback_1h_anchor_failed", "reason": "invalid_lr"}

    h1_aligned = _lr_direction(h1) == desired and abs(h1) >= threshold_1h
    if config.PULLBACK_REQUIRE_1H_ALIGNMENT and not h1_aligned:
        return {
            "passed": False,
            "status": "pullback_1h_anchor_failed",
            "lr_1h": h1,
            "threshold_1h": threshold_1h,
        }

    strong_opposite_threshold = threshold_15m * strong_opposite_multiplier
    current_direction = _lr_direction(m15)
    if current_direction == opposite and abs(m15) >= strong_opposite_threshold:
        return {
            "passed": False,
            "status": "pullback_15m_bridge_strong_opposite",
            "lr_15m": m15,
            "strong_opposite_threshold": strong_opposite_threshold,
        }

    memory_window = list(recent_lr_15m)[-memory_candles:]
    aligned_memory = []
    for value in memory_window:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if _lr_direction(numeric) == desired and abs(numeric) >= threshold_15m:
            aligned_memory.append(numeric)

    if not aligned_memory:
        return {
            "passed": False,
            "status": "pullback_15m_bridge_no_memory",
            "recent_lr_15m": memory_window,
            "threshold_15m": threshold_15m,
        }

    return {
        "passed": True,
        "status": "pullback_15m_bridge_allowed",
        "lr_1h": h1,
        "lr_15m": m15,
        "recent_aligned_count": len(aligned_memory),
        "recent_lr_15m": memory_window,
    }


def pullback_structure(df: pd.DataFrame, trend: str) -> dict:
    """Validate recent M5 structure and protected swing for a pullback."""
    lookback = max(4, min(config.PULLBACK_STRUCTURE_LOOKBACK_BARS, len(df)))
    window = df.iloc[-lookback:]
    highs = [float(v) for v in window["h"].tolist()]
    lows = [float(v) for v in window["l"].tolist()]
    last_low = lows[-1]
    last_high = highs[-1]

    if trend == "Uptrend":
        prior_lows = lows[:-1]
        protected_low = min(prior_lows) if prior_lows else last_low
        has_higher_high = highs[-1] > min(highs[:-1]) if len(highs) > 1 else False
        has_higher_low = last_low >= protected_low
        passed = has_higher_high and has_higher_low
        reason = "pullback_structure_ok" if passed else "pullback_structure_failed"
        return {
            "passed": passed,
            "reason": reason,
            "protected_level": protected_low,
            "recent_highs": highs,
            "recent_lows": lows,
        }

    prior_highs = highs[:-1]
    protected_high = max(prior_highs) if prior_highs else last_high
    has_lower_low = lows[-1] < max(lows[:-1]) if len(lows) > 1 else False
    has_lower_high = last_high <= protected_high
    passed = has_lower_low and has_lower_high
    reason = "pullback_structure_ok" if passed else "pullback_structure_failed"
    return {
        "passed": passed,
        "reason": reason,
        "protected_level": protected_high,
        "recent_highs": highs,
        "recent_lows": lows,
    }


def pullback_keltner_sequence(
    df: pd.DataFrame,
    kc: pd.DataFrame,
    trend: str,
    atr: float,
    kc_upper_col: str,
    kc_lower_col: str,
    kc_mid_col: str,
    macd_current: Optional[float] = None,
) -> dict:
    """Validate prior outer-band break followed by a midline pullback or high-value pullback."""
    lookback = max(2, min(config.PULLBACK_KC_BREAK_LOOKBACK_BARS, len(df)))
    price_window = df.iloc[-lookback:]
    kc_window = kc.iloc[-lookback:]
    midline = float(kc[kc_mid_col].iloc[-1])
    upper = float(kc[kc_upper_col].iloc[-1])
    lower = float(kc[kc_lower_col].iloc[-1])
    channel_width = abs(upper - lower)
    tolerance_atr_component = float(atr) * config.PULLBACK_KC_MIDLINE_TOLERANCE_ATR
    tolerance_channel_component = channel_width * config.PULLBACK_KC_MIDLINE_TOLERANCE_CHANNEL_WIDTH
    tolerance = max(tolerance_atr_component, tolerance_channel_component)
    trigger_close = float(df["c"].iloc[-1])
    distance_to_midline = abs(trigger_close - midline)
    near_midline = distance_to_midline <= tolerance

    if trend == "Uptrend":
        highs = price_window["h"].iloc[:-1].to_numpy()
        upper_band = kc_window[kc_upper_col].iloc[:-1].to_numpy()
        prior_break = bool((highs >= upper_band).any())
    else:
        lows = price_window["l"].iloc[:-1].to_numpy()
        lower_band = kc_window[kc_lower_col].iloc[:-1].to_numpy()
        prior_break = bool((lows <= lower_band).any())

    is_high_value = False
    if macd_current is not None:
        if trend == "Uptrend":
            is_high_value = bool(prior_break and trigger_close > midline and macd_current > 0)
        else:
            is_high_value = bool(prior_break and trigger_close < midline and macd_current < 0)

    passed = prior_break and (near_midline or is_high_value)
    return {
        "passed": passed,
        "reason": "pullback_kc_sequence_ok" if passed else "pullback_kc_sequence_failed",
        "prior_break": prior_break,
        "near_midline": near_midline,
        "is_high_value": bool(is_high_value and not near_midline),
        "trigger_close": trigger_close,
        "midline": midline,
        "distance_to_midline": distance_to_midline,
        "tolerance": tolerance,
        "tolerance_atr_component": tolerance_atr_component,
        "tolerance_channel_component": tolerance_channel_component,
    }


def pullback_trigger(
    patterns: pd.DataFrame,
    trend: str,
    candles: Optional[pd.DataFrame] = None,
    value_area_midline: Optional[float] = None,
    value_area_tolerance: Optional[float] = None,
    macd_current: Optional[float] = None,
) -> dict:
    """Return approved direction-specific pullback trigger candle diagnostics.

    The primary gate requires a recognised candlestick pattern (hammer/
    engulfing for uptrend, shooting star/engulfing for downtrend) whose shape
    matches a tight body/long-rejection-wick profile. When that pattern is
    absent or its shape is marginal, a MACD-histogram momentum fallback is
    allowed: if the histogram is on the correct side of zero for the trend
    direction, the trigger is approved as ``macd_momentum`` so valid pullback
    setups are not blocked solely by a missing exact candlestick label.
    """
    base = {
        "passed": False,
        "trigger": None,
        "reason": "pullback_trigger_candle_failed",
        "pattern": None,
        "body_to_range": None,
        "upper_wick": None,
        "lower_wick": None,
        "rejection_wick_ratio": None,
        "rejection_wick_body_ratio": None,
        "close_position": None,
        "value_area_relation": None,
        "momentum_fallback": False,
    }

    def _macd_supports() -> bool:
        if macd_current is None:
            return False
        return (trend == "Uptrend" and macd_current > 0) or (trend == "Downtrend" and macd_current < 0)

    if patterns.empty:
        if _macd_supports():
            return {
                **base,
                "passed": True,
                "trigger": "macd_momentum",
                "pattern": "MACD_HISTOGRAM",
                "reason": "pullback_trigger_macd_momentum",
                "momentum_fallback": True,
            }
        return base

    last = patterns.iloc[-1]
    value = lambda name: last.get(name, 0) if hasattr(last, "get") else 0
    trigger: Optional[str] = None
    pattern: Optional[str] = None
    if trend == "Uptrend":
        if value("CDL_HAMMER") < 0:
            trigger = "hammer"
            pattern = "CDL_HAMMER"
        elif value("CDL_ENGULFING") < 0:
            trigger = "bullish_engulfing"
            pattern = "CDL_ENGULFING"
    else:
        if value("CDL_SHOOTINGSTAR") > 0:
            trigger = "shooting_star"
            pattern = "CDL_SHOOTINGSTAR"
        elif value("CDL_ENGULFING") > 0:
            trigger = "bearish_engulfing"
            pattern = "CDL_ENGULFING"

    if trigger is None:
        if _macd_supports():
            return {
                **base,
                "passed": True,
                "trigger": "macd_momentum",
                "pattern": "MACD_HISTOGRAM",
                "reason": "pullback_trigger_macd_momentum",
                "momentum_fallback": True,
            }
        return base

    context = {**base, "trigger": trigger, "pattern": pattern}
    if candles is None or candles.empty:
        context.update({"passed": True, "reason": f"pullback_trigger_{trigger}"})
        return context

    candle = candles.iloc[-1]
    open_price = float(candle["o"])
    high = float(candle["h"])
    low = float(candle["l"])
    close = float(candle["c"])
    full_range = max(0.0, high - low)
    body_size = abs(close - open_price)
    if full_range <= 0:
        return context

    upper_wick = max(0.0, high - max(open_price, close))
    lower_wick = max(0.0, min(open_price, close) - low)
    rejection_wick = lower_wick if trend == "Uptrend" else upper_wick
    body_to_range = body_size / full_range
    rejection_wick_ratio = rejection_wick / full_range
    rejection_wick_body_ratio = rejection_wick / body_size if body_size > 0 else math.inf
    close_position = (close - low) / full_range
    value_area_relation = None
    if value_area_midline is not None and value_area_tolerance is not None:
        wick_price = low if trend == "Uptrend" else high
        close_near = abs(close - float(value_area_midline)) <= float(value_area_tolerance)
        wick_near = abs(wick_price - float(value_area_midline)) <= float(value_area_tolerance)
        wick_through = wick_price <= value_area_midline if trend == "Uptrend" else wick_price >= value_area_midline
        value_area_relation = {
            "close_near": close_near,
            "wick_near": wick_near,
            "wick_through": wick_through,
        }
    shape_ok = (
        body_to_range <= config.PULLBACK_TRIGGER_MAX_BODY_RANGE_RATIO
        and rejection_wick_ratio >= config.PULLBACK_TRIGGER_MIN_REJECTION_WICK_RANGE_RATIO
        and rejection_wick_body_ratio >= config.PULLBACK_TRIGGER_MIN_REJECTION_WICK_BODY_RATIO
    )
    if not shape_ok and _macd_supports():
        # Momentum continuation rescue: the candle isn't a textbook rejection
        # shape, but MACD histogram is on the correct side of zero for the
        # pullback direction, so allow the trigger to pass.
        context.update({
            "passed": True,
            "reason": f"pullback_trigger_{trigger}_momentum_fallback",
            "momentum_fallback": True,
            "body_to_range": body_to_range,
            "upper_wick": upper_wick,
            "lower_wick": lower_wick,
            "rejection_wick_ratio": rejection_wick_ratio,
            "rejection_wick_body_ratio": rejection_wick_body_ratio,
            "close_position": close_position,
            "value_area_relation": value_area_relation,
        })
        return context
    context.update({
        "passed": bool(shape_ok),
        "reason": f"pullback_trigger_{trigger}" if shape_ok else "pullback_trigger_candle_failed",
        "body_to_range": body_to_range,
        "upper_wick": upper_wick,
        "lower_wick": lower_wick,
        "rejection_wick_ratio": rejection_wick_ratio,
        "rejection_wick_body_ratio": rejection_wick_body_ratio,
        "close_position": close_position,
        "value_area_relation": value_area_relation,
    })
    return context


def pullback_stoch_rsi(k: float, d: float, k_values: pd.Series, trend: str) -> dict:
    """Evaluate Stoch RSI exhaustion for a direction-specific pullback."""
    memory_bars = max(1, int(config.PULLBACK_STOCH_MEMORY_BARS))
    recent = k_values.iloc[-memory_bars:] if len(k_values) >= memory_bars else k_values
    if trend == "Uptrend":
        recent_low = float(recent.min())
        rising = len(recent) >= 2 and float(recent.iloc[-1]) > float(recent.iloc[-2])
        passed = (
            k <= config.PULLBACK_STOCH_OVERSOLD
            or d <= config.PULLBACK_STOCH_OVERSOLD
            or (recent_low <= config.PULLBACK_STOCH_OVERSOLD_RECENT and (k > d or rising))
        )
        return {"passed": bool(passed), "reason": "pullback_stoch_rsi_ok" if passed else "pullback_stoch_rsi_failed", "recent_low": recent_low, "k": float(k), "d": float(d), "memory_bars": memory_bars, "recovery_or_roll_down": bool(k > d or rising)}

    recent_high = float(recent.max())
    falling = len(recent) >= 2 and float(recent.iloc[-1]) < float(recent.iloc[-2])
    passed = (
        k >= config.PULLBACK_STOCH_OVERBOUGHT
        or d >= config.PULLBACK_STOCH_OVERBOUGHT
        or (recent_high >= config.PULLBACK_STOCH_OVERBOUGHT_RECENT and (k < d or falling))
    )
    return {"passed": bool(passed), "reason": "pullback_stoch_rsi_ok" if passed else "pullback_stoch_rsi_failed", "recent_high": recent_high, "k": float(k), "d": float(d), "memory_bars": memory_bars, "recovery_or_roll_down": bool(k < d or falling)}

"""Trade-management helpers for the example pullback strategy.

Pure helpers used by ``strategy.py`` for risk/exit placement and confidence
scoring. Kept separate so the strategy's trade-management knobs are easy to find
and override when copying this folder into a new strategy.
"""
from __future__ import annotations

from tradegumi import config
from tradegumi.signal_engine import _price_decimals
from tradegumi.strategy_loader import (
    MANAGEMENT_ACCEPTED,
    MANAGEMENT_REJECTED_DISABLED,
    MANAGEMENT_REJECTED_DUPLICATE_EVENT,
    MANAGEMENT_REJECTED_EXTENSION_CAP,
    MANAGEMENT_REJECTED_INSUFFICIENT_PROGRESS,
    MANAGEMENT_REJECTED_MISSING_CONTEXT,
    MANAGEMENT_REJECTED_RISK_INCREASE,
    ManagedTradeContext,
    TradeManagementDecision,
)

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


# ── Open-trade / continuation management ───────────────────────────────────────
# How this strategy manages an already-open trade when a same-direction
# continuation fires: move to break-even, then profit-protect, and extend the
# target — never increasing risk. Thresholds default to the framework's
# ``CONTINUATION_MANAGEMENT_*`` config so existing env tuning keeps working; copy
# this folder and edit the numbers (or read your own ``config.py``) to change them.


def _directional_movement(direction: str, entry_price: float, price: float) -> float | None:
    """Favorable movement in price units for a normalized BUY/SELL direction."""
    if entry_price is None or price is None:
        return None
    if direction == "BUY":
        return price - entry_price
    if direction == "SELL":
        return entry_price - price
    return None


def _price_from_r(direction: str, entry_price: float, risk: float, r_value: float) -> float:
    """Direction-aware price offset from entry by an R multiple."""
    return entry_price + (risk * r_value) if direction == "BUY" else entry_price - (risk * r_value)


def _would_increase_risk(direction: str, entry_price: float, current_sl: float, proposed_sl: float) -> bool:
    """Whether a proposed SL sits farther from entry (i.e. loosens) the current SL."""
    if abs(entry_price - proposed_sl) > abs(entry_price - current_sl):
        return True
    if direction == "BUY":
        return proposed_sl < current_sl
    return proposed_sl > current_sl


def manage_open_trade(ctx: ManagedTradeContext) -> TradeManagementDecision:
    """Evaluate SL/TP changes for one continuation against an active trade."""
    old_sl = ctx.current_stop_loss
    old_tp = ctx.current_take_profit
    entry_price = ctx.entry_price
    risk = ctx.risk_at_entry
    price = ctx.price_at_event
    direction = ctx.direction

    if not bool(config.CONTINUATION_MANAGEMENT_ENABLED):
        return TradeManagementDecision(False, MANAGEMENT_REJECTED_DISABLED, MANAGEMENT_REJECTED_DISABLED, old_sl, old_sl, old_tp, old_tp, price)
    if ctx.already_seen:
        return TradeManagementDecision(False, MANAGEMENT_REJECTED_DUPLICATE_EVENT, MANAGEMENT_REJECTED_DUPLICATE_EVENT, old_sl, old_sl, old_tp, old_tp, price)
    if old_sl is None or old_tp is None or entry_price is None or risk in (None, 0):
        return TradeManagementDecision(False, MANAGEMENT_REJECTED_MISSING_CONTEXT, MANAGEMENT_REJECTED_MISSING_CONTEXT, old_sl, old_sl, old_tp, old_tp, price)

    movement = _directional_movement(direction, entry_price, price)
    progress_r = None if movement is None else movement / risk
    if progress_r is None or progress_r < float(config.CONTINUATION_MANAGEMENT_BE_TRIGGER_R):
        return TradeManagementDecision(False, MANAGEMENT_REJECTED_INSUFFICIENT_PROGRESS, MANAGEMENT_REJECTED_INSUFFICIENT_PROGRESS, old_sl, old_sl, old_tp, old_tp, price)

    proposed_sl = old_sl
    break_even_moved = False
    sl_tightened = False
    if progress_r >= float(config.CONTINUATION_MANAGEMENT_PROFIT_PROTECT_TRIGGER_R):
        proposed_sl = _price_from_r(direction, entry_price, risk, float(config.CONTINUATION_MANAGEMENT_PROFIT_PROTECT_OFFSET_R))
    elif progress_r >= float(config.CONTINUATION_MANAGEMENT_BE_TRIGGER_R):
        proposed_sl = entry_price
        break_even_moved = True
    if _would_increase_risk(direction, entry_price, old_sl, proposed_sl):
        return TradeManagementDecision(False, MANAGEMENT_REJECTED_RISK_INCREASE, MANAGEMENT_REJECTED_RISK_INCREASE, old_sl, old_sl, old_tp, old_tp, price)
    if proposed_sl != old_sl:
        sl_tightened = True

    max_extensions = int(config.CONTINUATION_MANAGEMENT_MAX_TP_EXTENSIONS)
    current_extensions = int(ctx.tp_extension_count or 0)
    proposed_tp = old_tp
    tp_extended = False
    if current_extensions < max_extensions:
        target_r = abs(old_tp - entry_price) / risk + float(config.CONTINUATION_MANAGEMENT_TP_EXTENSION_MULTIPLE_R)
        target_r = min(target_r, float(config.CONTINUATION_MANAGEMENT_MAX_TARGET_R))
        proposed_tp = _price_from_r(direction, entry_price, risk, target_r)
        tp_extended = proposed_tp != old_tp
    elif not sl_tightened:
        return TradeManagementDecision(False, MANAGEMENT_REJECTED_EXTENSION_CAP, MANAGEMENT_REJECTED_EXTENSION_CAP, old_sl, old_sl, old_tp, old_tp, price)

    accepted = sl_tightened or tp_extended
    reason = MANAGEMENT_ACCEPTED if accepted else MANAGEMENT_REJECTED_INSUFFICIENT_PROGRESS
    return TradeManagementDecision(
        accepted,
        reason,
        None if accepted else reason,
        old_sl,
        proposed_sl,
        old_tp,
        proposed_tp,
        price,
        tp_extended=tp_extended,
        sl_tightened=sl_tightened,
        break_even_moved=break_even_moved,
    )

"""Trailing Stop Loss manager — 4-tier ATR-based.

Adapted from CTI_Scripts trailing_sl_atr.py.
No os.execv() — raises exceptions instead.
No threading — designed to be driven by main.py's loop or a simple scheduler.
"""
import logging as log
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pytz import timezone

from tradegumi import config
from tradegumi.api.base_client import ExecutionClient, Position
from tradegumi.indicators import calculate_atr, candles_to_df

log = log.getLogger(__name__)
NY_TZ = timezone("America/New_York")


# ── Tier definitions ──────────────────────────────────────────────────────────

@dataclass
class TrailingTier:
    """A trailing SL tier.

    r_ratio: profit in R-multiples (distance from open price / initial SL distance)
    atr_mult: ATR multiplier for the trailing SL calculation
    """
    r_ratio_min: float
    r_ratio_max: float
    atr_mult: float


TIERS = [
    TrailingTier(r_ratio_min=0.0,   r_ratio_max=1.5,  atr_mult=3.0),   # Tier 1
    TrailingTier(r_ratio_min=1.5,   r_ratio_max=3.0,  atr_mult=2.0),   # Tier 2
    TrailingTier(r_ratio_min=3.0,   r_ratio_max=5.0,  atr_mult=1.5),   # Tier 3
    TrailingTier(r_ratio_min=5.0,   r_ratio_max=999, atr_mult=1.0),   # Tier 4
]


# ── State ────────────────────────────────────────────────────────────────────

@dataclass
class TradeState:
    """Per-position trailing SL state."""
    position_id: str
    symbol: str
    side: str
    open_price: float
    initial_r: float          # initial R-value (SL distance in price units)
    current_sl: float
    tier_index: int = 0
    opened_at: datetime = field(default_factory=lambda: datetime.now(NY_TZ))


class TrailingSLManager:
    """Manages trailing SL for open positions.

    Call run_once() on each iteration of the main loop.
    """

    def __init__(self, client: ExecutionClient):
        self.client = client
        self._states: dict[str, TradeState] = {}

    # ── Startup ───────────────────────────────────────────────────────────────

    def init_position(self, position: Position) -> None:
        """Initialise trailing state for a newly opened position."""
        symbol = position.symbol
        side   = position.side
        open_price = position.open_price

        # Calculate initial R distance
        candles = self.client.get_candles(symbol, "M5", count=20)
        df = candles_to_df(candles)
        atr = calculate_atr(df).iloc[-1]
        sl_distance = atr * config.SL_ATR_MULTIPLIER

        initial_r = round(abs(open_price - (open_price - (sl_distance if side == "BUY" else -sl_distance))), 6)
        initial_sl = self._calc_sl_price(symbol, side, open_price, atr, mult=config.SL_ATR_MULTIPLIER)

        self._states[position.id] = TradeState(
            position_id=position.id,
            symbol=symbol,
            side=side,
            open_price=open_price,
            initial_r=initial_r,
            current_sl=initial_sl,
            tier_index=0,
        )
        log.info("TrailingSL: initialised %s id=%s initial_sl=%s tier=1",
                 symbol, position.id, initial_sl)

    # ── Main update ────────────────────────────────────────────────────────────

    def run_once(self) -> None:
        """Update trailing SL for all tracked positions.

        Called on each loop iteration.
        """
        positions = self.client.get_open_positions()

        # Register new positions
        for pos in positions:
            if pos.id not in self._states:
                self.init_position(pos)

        # Prune closed positions
        open_ids = {p.id for p in positions}
        for pos_id in list(self._states.keys()):
            if pos_id not in open_ids:
                log.info("TrailingSL: removing closed position %s", pos_id)
                del self._states[pos_id]

        # Update each tracked position
        for pos in positions:
            if pos.id not in self._states:
                continue
            self._update_one(pos)

    # ── Per-position update ───────────────────────────────────────────────────

    def _update_one(self, position: Position) -> None:
        """Compute and apply new trailing SL for one position."""
        state = self._states[position.id]
        symbol = state.symbol
        side   = state.side

        # Get ATR
        candles = self.client.get_candles(symbol, "M5", count=20)
        df = candles_to_df(candles)
        atr = calculate_atr(df).iloc[-1]

        # Get current swing high/low (for simplicity: use recent 20-candle high/low)
        swing_high = df["h"].iloc[-20:].max()
        swing_low  = df["l"].iloc[-20:].min()

        # Calculate R-ratio
        if side == "BUY":
            r_distance = position.current_price - state.open_price
        else:
            r_distance = state.open_price - position.current_price

        if state.initial_r == 0:
            rr = 0.0
        else:
            rr = round(r_distance / state.initial_r, 2)

        # Determine current tier
        tier_index = self._tier_for_rr(rr)
        state.tier_index = tier_index
        tier = TIERS[tier_index]

        # Calculate new SL
        new_sl = self._calc_sl_from_swing(
            symbol, side, swing_high, swing_low, atr, tier.atr_mult
        )

        if new_sl is None:
            return

        new_sl_rounded = round(new_sl, _price_decimals(position.current_price))

        # Only tighten (SL moves in direction of profit only)
        should_update = False
        if side == "BUY" and new_sl_rounded > state.current_sl:
            should_update = True
        elif side == "SELL" and new_sl_rounded < state.current_sl:
            should_update = True

        if should_update:
            old_sl = state.current_sl
            state.current_sl = new_sl_rounded
            log.info(
                "TrailingSL: %s id=%s RR=%.2f tier=%d SL %s → %s",
                symbol, position.id, rr, tier_index + 1,
                _fmt_price(old_sl), _fmt_price(new_sl_rounded)
            )
            try:
                self.client.modify_sl_tp(
                    position.id,
                    stop_loss=new_sl_rounded,
                    take_profit=None,   # TP managed separately or by Oanda
                )
            except Exception as e:
                log.error("TrailingSL: failed to update SL for %s: %s", symbol, e)
        else:
            log.debug(
                "TrailingSL: %s no change RR=%.2f tier=%d current_sl=%s",
                symbol, rr, tier_index + 1, _fmt_price(state.current_sl)
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _calc_sl_price(
        self, symbol: str, side: str, reference_price: float,
        atr: float, mult: float
    ) -> float:
        """Calculate SL price from ATR multiplier."""
        if side == "BUY":
            sl = reference_price - (atr * mult)
        else:
            sl = reference_price + (atr * mult)
        return round(sl, _price_decimals(reference_price))

    def _calc_sl_from_swing(
        self, symbol: str, side: str,
        swing_high: float, swing_low: float,
        atr: float, atr_mult: float
    ) -> Optional[float]:
        """Calculate trailing SL from swing values."""
        if side == "BUY":
            raw = swing_high - (atr * atr_mult)
        else:
            raw = swing_low + (atr * atr_mult)
        return raw

    def _tier_for_rr(self, rr: float) -> int:
        """Return tier index for a given R-ratio."""
        for i, tier in enumerate(TIERS):
            if tier.r_ratio_min <= rr < tier.r_ratio_max:
                return i
        return len(TIERS) - 1


def _price_decimals(price: float) -> int:
    if price >= 1000:
        return 2
    elif price >= 100:
        return 3
    elif price >= 10:
        return 4
    elif price >= 1:
        return 5
    return 6


def _fmt_price(price: float) -> str:
    return f"{price:.{_price_decimals(price)}f}"
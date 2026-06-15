"""Session rules: forex trading week, swap blackout, day-of-week scoring.

Forex instruments trade as one weekly session that opens Sunday 17:00 US
Eastern / 16:00 US Central and closes Friday 17:00 US Eastern / 16:00 US
Central. Every session decision is made in a canonical US Eastern reference so
US Central and Eastern displays — and daylight saving transitions — agree on a
single open/closed truth.
"""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional

from pytz import timezone

NY_TZ = timezone("America/New_York")

# ── Forex weekly session boundaries (US Eastern reference) ────────────────────
# Forex opens Sunday 17:00 ET (16:00 CT) and closes Friday 17:00 ET (16:00 CT).
# Python weekday(): Monday=0 … Friday=4, Saturday=5, Sunday=6.
FOREX_OPEN_WEEKDAY = 6          # Sunday
FOREX_CLOSE_WEEKDAY = 4         # Friday
FOREX_SATURDAY = 5
FOREX_WEEKLY_BOUNDARY_ET = time(17, 0)   # 17:00 ET == 16:00 CT

# ── Stable session reason codes ──────────────────────────────────────────────
REASON_OPEN = "open"
REASON_BEFORE_WEEKLY_OPEN = "before_weekly_open"
REASON_AFTER_WEEKLY_CLOSE = "after_weekly_close"
REASON_WEEKEND_BREAK = "weekend_break"

# ── Operator-facing boundary labels ──────────────────────────────────────────
FOREX_NEXT_OPEN_BOUNDARY = "Next forex weekly open Sunday 16:00 CT / 17:00 ET"
FOREX_WEEKLY_CLOSE_BOUNDARY = "Forex weekly close Friday 16:00 CT / 17:00 ET"

# ── Index market hours (weekday windows, unchanged) ──────────────────────────
# Indices keep their own weekday calendar; they do not follow the forex week.
INDEX_HOURS = {
    0: [(time(0, 0), time(23, 59, 59))],
    1: [(time(0, 0), time(23, 59, 59))],
    2: [(time(0, 0), time(23, 59, 59))],
    3: [(time(0, 0), time(23, 59, 59))],
    4: [(time(0, 0), time(16, 30))],  # Friday
}

# ── Swap Blackout Windows ────────────────────────────────────────────────────
# Oanda swaps at ~17:00 ET; blackout 16:55–17:30 for safety
FOREX_SWAP_BLACKOUT = (time(16, 55), time(17, 30))
INDEX_SWAP_BLACKOUT = (time(16, 55), time(18, 29))
CRYPTO_SWAP_BLACKOUT = (time(16, 55), time(17, 30))

# ── Symbol category lookup ────────────────────────────────────────────────────
from tradegumi import config


@dataclass
class MarketSessionStatus:
    """Structured market-session decision for a symbol at a moment in time.

    Boolean callers use ``is_open``; diagnostics use ``reason`` and
    ``session_boundary`` so machine-readable state never disagrees with the
    boolean open/closed answer.
    """

    symbol: str
    category: str
    evaluated_at: datetime
    is_open: bool
    reason: str
    session_boundary: Optional[str] = None


def _to_ny(when: Optional[datetime]) -> datetime:
    """Return ``when`` as a US Eastern reference time (defaults to now)."""
    if when is None:
        return datetime.now(NY_TZ)
    if when.tzinfo is None:
        return NY_TZ.localize(when)
    return when.astimezone(NY_TZ)


def _symbol_category(symbol: str) -> str:
    if symbol in config.FOREX_MAJORS or symbol in config.FOREX_MINORS:
        return "forex"
    if symbol in config.INDICES:
        return "index"
    if symbol in config.CRYPTO:
        return "crypto"
    if symbol in config.COMMODITIES:
        # Commodities intentionally follow the forex weekly session.
        return "forex"
    return "forex"


def _forex_decision(when_et: datetime) -> tuple[bool, str]:
    """Return (is_open, reason) for the weekly forex session at a NY-local time.

    Open Sunday 17:00 ET → Friday 17:00 ET. The Sunday open boundary is
    inclusive and the Friday close boundary is exclusive of the open side, so
    16:59:59 ET Friday is still open while 17:00:00 ET Friday is closed.
    """
    weekday = when_et.weekday()
    now_t = when_et.time()
    if weekday == FOREX_OPEN_WEEKDAY:  # Sunday — opens at 17:00 ET
        if now_t >= FOREX_WEEKLY_BOUNDARY_ET:
            return True, REASON_OPEN
        return False, REASON_BEFORE_WEEKLY_OPEN
    if weekday == FOREX_CLOSE_WEEKDAY:  # Friday — closes at 17:00 ET
        if now_t < FOREX_WEEKLY_BOUNDARY_ET:
            return True, REASON_OPEN
        return False, REASON_AFTER_WEEKLY_CLOSE
    if weekday == FOREX_SATURDAY:  # Saturday — weekend break
        return False, REASON_WEEKEND_BREAK
    return True, REASON_OPEN  # Monday–Thursday — continuous trading


def _index_decision(when_et: datetime) -> tuple[bool, str]:
    """Return (is_open, reason) for index symbols using weekday windows."""
    weekday = when_et.weekday()
    if weekday > FOREX_CLOSE_WEEKDAY:  # Saturday / Sunday — index markets shut
        return False, REASON_WEEKEND_BREAK
    now_t = when_et.time()
    for start, end in INDEX_HOURS.get(weekday, []):
        if start <= end:
            if start <= now_t <= end:
                return True, REASON_OPEN
        elif now_t >= start or now_t <= end:
            return True, REASON_OPEN
    return False, REASON_AFTER_WEEKLY_CLOSE


def market_session_status(symbol: str, when: Optional[datetime] = None) -> MarketSessionStatus:
    """Return the structured market-session decision for ``symbol``.

    Forex (and commodities that follow forex hours) use the weekly
    Sunday-17:00-ET → Friday-17:00-ET window. Crypto is always open. Index
    symbols keep their existing weekday session windows.
    """
    when_et = _to_ny(when)
    category = _symbol_category(symbol)

    if category == "crypto":
        return MarketSessionStatus(symbol, category, when_et, True, REASON_OPEN, None)

    if category == "index":
        is_open, reason = _index_decision(when_et)
        return MarketSessionStatus(symbol, category, when_et, is_open, reason, None)

    is_open, reason = _forex_decision(when_et)
    boundary = None if is_open else FOREX_NEXT_OPEN_BOUNDARY
    return MarketSessionStatus(symbol, category, when_et, is_open, reason, boundary)


def is_trading_open(symbol: str, when: Optional[datetime] = None) -> bool:
    """Check if symbol is within its market session hours.

    Args:
        symbol: Trading symbol e.g. "EURUSD"
        when: datetime (any timezone, or naive=ET). Defaults to now.

    Returns:
        True if market is open, False otherwise.
    """
    return market_session_status(symbol, when).is_open


def is_swap_blackout(symbol: str, when: Optional[datetime] = None) -> bool:
    """Check if symbol is in its daily swap blackout window.

    On Fridays, skip blackout — the market closes for the week, so
    there's no swap rollover to worry about.
    """
    when = _to_ny(when)

    # Friday close: no swap blackout (market closes for the week)
    if when.weekday() == FOREX_CLOSE_WEEKDAY:
        return False

    cat = _symbol_category(symbol)
    if cat == "forex":
        blackout = FOREX_SWAP_BLACKOUT
    elif cat == "index":
        blackout = INDEX_SWAP_BLACKOUT
    else:
        blackout = CRYPTO_SWAP_BLACKOUT

    now_t = when.time()
    return blackout[0] <= now_t <= blackout[1]


def is_market_open(symbol: str, when: Optional[datetime] = None) -> bool:
    """Combined check: within session AND not in swap blackout.

    Swap blackout is ignored for early development — markets stay open
    during rollover. Will add swap-aware scheduling later.
    """
    return is_trading_open(symbol, when)


def is_trading_day(symbol: str, when: Optional[datetime] = None) -> bool:
    """Check if the market is in session for this symbol at ``when``.

    Backed by the same structured session decision as ``is_trading_open`` so a
    forex symbol is "trading" across the full weekly window, including the
    Sunday evening open, rather than a simplified Monday–Friday calendar.
    """
    return market_session_status(symbol, when).is_open


# ── Day-of-week scoring ───────────────────────────────────────────────────────


def day_of_week_bias(symbol: str, when: Optional[datetime] = None) -> float:
    """Return a day-of-week bias multiplier for ADR-based scoring.

    Based on CTI observations:
    - Monday: compressed ranges, lower breakout probability → 0.7
    - Tuesday–Thursday: strongest trend days → 1.0
    - Friday: PM square-off pressure → 0.6
    """
    when = _to_ny(when)

    bias_map = {0: 0.7, 1: 1.0, 2: 1.0, 3: 1.0, 4: 0.6, 5: 0.0, 6: 0.0}
    return bias_map.get(when.weekday(), 1.0)

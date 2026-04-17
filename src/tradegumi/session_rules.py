"""Session rules: trading hours, swap blackout, day-of-week filtering."""
from datetime import datetime, time
from typing import Optional

from pytz import timezone

NY_TZ = timezone("America/New_York")

# ── Market Hours ─────────────────────────────────────────────────────────────
# Oanda forex: Open Sun 17:05 ET, close Fri 16:59 ET
# Mon–Thu: two windows (pre-break and post-break with swap gap)
# Friday: closes at 16:59, no evening session
# Indexed by weekday (0=Mon … 4=Fri), each entry is a list of (start, end) tuples

FOREX_HOURS = {
    0: [(time(0, 0), time(16, 59)), (time(17, 5), time(23, 59))],   # Monday
    1: [(time(0, 0), time(16, 59)), (time(17, 5), time(23, 59))],   # Tuesday
    2: [(time(0, 0), time(16, 59)), (time(17, 5), time(23, 59))],   # Wednesday
    3: [(time(0, 0), time(16, 59)), (time(17, 5), time(23, 59))],   # Thursday
    4: [(time(0, 0), time(16, 59))],                                # Friday (closes for week)
}

INDEX_HOURS = {
    0: [(time(0, 0), time(16, 30)), (time(18, 30), time(23, 59))],
    1: [(time(0, 0), time(16, 30)), (time(18, 30), time(23, 59))],
    2: [(time(0, 0), time(16, 30)), (time(18, 30), time(23, 59))],
    3: [(time(0, 0), time(16, 30)), (time(18, 30), time(23, 59))],
    4: [(time(0, 0), time(16, 30))],                                # Friday
}

INDEX_HOURS = [
    (time(0, 0),  time(16, 30)),
    (time(18, 30), time(23, 59)),
]

# ── Swap Blackout Windows ───────────────────────────────────────────────────
# Oanda swaps at ~17:00 ET; blackout 16:55–17:30 for safety
FOREX_SWAP_BLACKOUT = (time(16, 55), time(17, 30))
INDEX_SWAP_BLACKOUT = (time(16, 55), time(18, 29))
CRYPTO_SWAP_BLACKOUT = (time(16, 55), time(17, 30))

# ── Symbol category lookup ────────────────────────────────────────────────────
from tradegumi import config


def _symbol_category(symbol: str) -> str:
    if symbol in config.FOREX_MAJORS or symbol in config.FOREX_MINORS:
        return "forex"
    if symbol in config.INDICES:
        return "index"
    if symbol in config.CRYPTO:
        return "crypto"
    if symbol in config.COMMODITIES:
        # Commodities follow forex rules
        return "forex"
    return "forex"


def is_trading_open(symbol: str, when: Optional[datetime] = None) -> bool:
    """Check if symbol is within its market session hours (NY time).

    Args:
        symbol: Trading symbol e.g. "EURUSD"
        when: datetime in NY timezone. Defaults to now.

    Returns:
        True if market is open, False otherwise.
    """
    if when is None:
        when = datetime.now(NY_TZ)
    else:
        # Ensure we work in NY timezone
        if when.tzinfo is None:
            when = NY_TZ.localize(when)
        else:
            when = when.astimezone(NY_TZ)

    weekday = when.weekday()
    if weekday > 4:  # Saturday / Sunday
        return False

    cat = _symbol_category(symbol)
    if cat == "forex":
        hours = FOREX_HOURS
    elif cat == "index":
        hours = INDEX_HOURS
    else:
        return True  # Crypto — always open

    now_t = when.time()
    day_windows = hours.get(weekday, [])

    for start, end in day_windows:
        if start <= end:
            if start <= now_t <= end:
                return True
        else:
            if now_t >= start or now_t <= end:
                return True
    return False


def is_swap_blackout(symbol: str, when: Optional[datetime] = None) -> bool:
    """Check if symbol is in its daily swap blackout window.

    On Fridays, skip blackout — the market closes for the week, so
    there's no swap rollover to worry about.
    """
    if when is None:
        when = datetime.now(NY_TZ)
    else:
        if when.tzinfo is None:
            when = NY_TZ.localize(when)
        else:
            when = when.astimezone(NY_TZ)

    # Friday close: no swap blackout (market closes for the week)
    if when.weekday() == 4:
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
    """Combined check: within session AND not in swap blackout."""
    return is_trading_open(symbol, when) and not is_swap_blackout(symbol, when)


def is_trading_day(symbol: str, when: Optional[datetime] = None) -> bool:
    """Check if today is a trading day for this symbol category."""
    if when is None:
        when = datetime.now(NY_TZ)
    else:
        if when.tzinfo is None:
            when = NY_TZ.localize(when)
        else:
            when = when.astimezone(NY_TZ)

    weekday = when.weekday()
    # No trading Sat/Sun regardless of asset class
    return weekday <= 4


# ── Day-of-week scoring ───────────────────────────────────────────────────────

def day_of_week_bias(symbol: str, when: Optional[datetime] = None) -> float:
    """Return a day-of-week bias multiplier for ADR-based scoring.

    Based on CTI observations:
    - Monday: compressed ranges, lower breakout probability → 0.7
    - Tuesday–Thursday: strongest trend days → 1.0
    - Friday: PM square-off pressure → 0.6
    """
    if when is None:
        when = datetime.now(NY_TZ)
    else:
        if when.tzinfo is None:
            when = NY_TZ.localize(when)
        else:
            when = when.astimezone(NY_TZ)

    bias_map = {0: 0.7, 1: 1.0, 2: 1.0, 3: 1.0, 4: 0.6, 5: 0.0, 6: 0.0}
    return bias_map.get(when.weekday(), 1.0)
"""Forex weekly session boundary tests (specs/021-market-hours-rescan US1).

Covers the Sunday open, weekday continuous trading, Friday close, weekend
closure, and daylight-saving equivalence between US Central and US Eastern
reference times. The canonical decision is made in US Eastern, so a Central
wall-clock time and the equivalent Eastern wall-clock time must agree.
"""
from datetime import datetime

from pytz import timezone

from tradegumi.session_rules import (
    REASON_AFTER_WEEKLY_CLOSE,
    REASON_BEFORE_WEEKLY_OPEN,
    REASON_OPEN,
    REASON_WEEKEND_BREAK,
    is_market_open,
    is_trading_day,
    is_trading_open,
    market_session_status,
)

CT_TZ = timezone("America/Chicago")
NY_TZ = timezone("America/New_York")


def ct(year, month, day, hour, minute, second=0):
    """A timezone-aware US Central timestamp (DST handled by pytz)."""
    return CT_TZ.localize(datetime(year, month, day, hour, minute, second))


def et(year, month, day, hour, minute, second=0):
    """A timezone-aware US Eastern timestamp (DST handled by pytz)."""
    return NY_TZ.localize(datetime(year, month, day, hour, minute, second))


# ── Sunday weekly open boundary (US1: T008) ──────────────────────────────────


def test_sunday_before_open_is_closed():
    status = market_session_status("EURUSD", ct(2026, 6, 14, 15, 59, 59))
    assert status.is_open is False
    assert status.reason == REASON_BEFORE_WEEKLY_OPEN
    assert status.session_boundary  # operator gets next-open context


def test_sunday_open_boundary_is_inclusive():
    status = market_session_status("EURUSD", ct(2026, 6, 14, 16, 0, 0))
    assert status.is_open is True
    assert status.reason == REASON_OPEN


def test_sunday_2140_central_is_open():
    # The exact operator-reported case: Sunday 21:40 Central must be open.
    assert is_trading_open("EURUSD", ct(2026, 6, 14, 21, 40)) is True
    assert is_market_open("EURUSD", ct(2026, 6, 14, 21, 40)) is True


# ── Weekday / Friday / weekend boundaries (US1: T009) ────────────────────────


def test_weekday_midweek_is_open():
    assert is_trading_open("EURUSD", ct(2026, 6, 10, 3, 0)) is True
    assert is_trading_open("EURUSD", ct(2026, 6, 10, 23, 30)) is True


def test_friday_before_close_is_open():
    status = market_session_status("EURUSD", ct(2026, 6, 12, 15, 59, 59))
    assert status.is_open is True
    assert status.reason == REASON_OPEN


def test_friday_close_boundary_is_closed():
    status = market_session_status("EURUSD", ct(2026, 6, 12, 16, 0, 0))
    assert status.is_open is False
    assert status.reason == REASON_AFTER_WEEKLY_CLOSE


def test_saturday_is_weekend_break():
    status = market_session_status("EURUSD", ct(2026, 6, 13, 12, 0))
    assert status.is_open is False
    assert status.reason == REASON_WEEKEND_BREAK


# ── Daylight-saving equivalence: Central vs Eastern (US1: T010) ──────────────


def test_sunday_open_equivalence_summer_dst():
    # Sunday 16:00 CDT and 17:00 EDT are the same instant — both open.
    assert is_trading_open("EURUSD", ct(2026, 6, 14, 16, 0)) is True
    assert is_trading_open("EURUSD", et(2026, 6, 14, 17, 0)) is True
    # And one second earlier (15:59 CT / 16:59 ET) both closed.
    assert is_trading_open("EURUSD", ct(2026, 6, 14, 15, 59, 59)) is False
    assert is_trading_open("EURUSD", et(2026, 6, 14, 16, 59, 59)) is False


def test_sunday_open_equivalence_winter_standard():
    # Sunday 16:00 CST and 17:00 EST are the same instant in standard time.
    assert is_trading_open("EURUSD", ct(2026, 1, 4, 16, 0)) is True
    assert is_trading_open("EURUSD", et(2026, 1, 4, 17, 0)) is True
    assert is_trading_open("EURUSD", ct(2026, 1, 4, 15, 59, 59)) is False


def test_friday_close_equivalence_winter_standard():
    # Friday 16:00 CST / 17:00 EST close for the weekend break.
    assert is_trading_open("EURUSD", ct(2026, 1, 2, 16, 0)) is False
    assert is_trading_open("EURUSD", et(2026, 1, 2, 17, 0)) is False
    assert is_trading_open("EURUSD", ct(2026, 1, 2, 15, 59, 59)) is True


# ── Category behavior: commodities follow forex, crypto always open (T012/T013)


def test_commodities_follow_forex_week():
    assert is_trading_open("XAUUSD", ct(2026, 6, 13, 12, 0)) is False  # Saturday
    assert is_trading_open("XAUUSD", ct(2026, 6, 10, 12, 0)) is True   # Wednesday


def test_crypto_is_always_open():
    assert is_trading_open("BTCUSD", ct(2026, 6, 13, 12, 0)) is True   # Saturday
    assert is_trading_open("BTCUSD", ct(2026, 6, 14, 3, 0)) is True    # Sunday a.m.


# ── is_trading_day follows the same weekly decision (T006) ───────────────────


def test_is_trading_day_recognizes_sunday_evening():
    assert is_trading_day("EURUSD", ct(2026, 6, 14, 21, 40)) is True
    assert is_trading_day("EURUSD", ct(2026, 6, 13, 12, 0)) is False  # Saturday

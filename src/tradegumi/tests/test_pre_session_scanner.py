"""Forced-rescan availability tests (specs/021-market-hours-rescan US2).

Verifies that during an open forex session a forced rescan evaluates each
symbol independently — available symbols stay available and symbol-specific
unavailability is isolated — rather than collapsing the whole watchlist into a
global closed-market result.
"""
from datetime import datetime

import pytest
from pytz import timezone

from tradegumi.api.base_client import Candle, ExecutionClient
from tradegumi.pre_session_scanner import (
    AVAIL_ACCOUNT_INSTRUMENT_UNAVAILABLE,
    AVAIL_AVAILABLE,
    AVAIL_CONFIGURED_UNAVAILABLE,
    AVAIL_MARKET_CLOSED,
    evaluate_symbol_availability,
    summarize_availability,
)

CT_TZ = timezone("America/Chicago")

# An open forex instant: Sunday 21:40 Central — the operator-reported case.
OPEN_SUNDAY = CT_TZ.localize(datetime(2026, 6, 14, 21, 40))
# A closed forex instant: Saturday midday — weekend break.
CLOSED_SATURDAY = CT_TZ.localize(datetime(2026, 6, 13, 12, 0))

FOREX_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]


class FakeExecutionClient(ExecutionClient):
    """Minimal in-memory execution client for scanner/rescan tests (T007).

    Returns flat synthetic daily candles and a configurable available-symbol
    set so tests never reach a broker.
    """

    def __init__(self, available: set[str] | None = None):
        self.available = set(available) if available is not None else set(FOREX_SYMBOLS)

    def get_candles(self, instrument, granularity, count):
        return [
            Candle(t=f"2026-06-{(i % 27) + 1:02d}T00:00:00Z", o=1.0, h=1.01, l=0.99, c=1.0)
            for i in range(count)
        ]

    def get_pricing(self, instruments):
        return []

    def get_account_balance(self):
        return 10000.0

    def get_open_positions(self):
        return []

    def place_order(self, order):
        return "fake-order"

    def close_position(self, position_id, units=None):
        return None

    def get_trade_history(self, count=50):
        return []

    def modify_sl_tp(self, position_id, stop_loss, take_profit):
        return None

    def get_position(self, position_id):
        raise NotImplementedError


@pytest.fixture
def fake_client():
    return FakeExecutionClient()


# ── T016: open hours preserve available symbols ──────────────────────────────


def test_open_session_preserves_available_symbols(fake_client):
    summary = summarize_availability(
        FOREX_SYMBOLS,
        available_symbols=fake_client.available,
        unavailable_instruments=set(),
        when=OPEN_SUNDAY,
    )
    assert summary["market_open"] is True
    assert summary["symbols_checked"] == len(FOREX_SYMBOLS)
    assert summary["symbols_available"] == len(FOREX_SYMBOLS)
    assert summary["symbols_unavailable"] == 0
    assert all(
        a["available"] and a["reason"] == AVAIL_AVAILABLE
        for a in summary["availability"]
    )


# ── T017: symbol-specific unavailability is isolated ─────────────────────────


def test_symbol_specific_unavailable_does_not_hide_available(fake_client):
    # USDJPY off the account, GBPUSD configured-unavailable; the rest stay open.
    available = set(FOREX_SYMBOLS) - {"USDJPY"}
    summary = summarize_availability(
        FOREX_SYMBOLS,
        available_symbols=available,
        unavailable_instruments={"GBPUSD"},
        when=OPEN_SUNDAY,
    )
    by_symbol = {a["symbol"]: a for a in summary["availability"]}

    assert summary["market_open"] is True
    assert by_symbol["EURUSD"]["available"] is True
    assert by_symbol["AUDUSD"]["available"] is True
    assert by_symbol["GBPUSD"]["reason"] == AVAIL_CONFIGURED_UNAVAILABLE
    assert by_symbol["USDJPY"]["reason"] == AVAIL_ACCOUNT_INSTRUMENT_UNAVAILABLE
    # Available symbols are preserved — not collapsed into a global result.
    assert summary["symbols_available"] == 2
    assert summary["symbols_unavailable"] == 2


def test_closed_session_reports_market_closed_with_boundary_context():
    summary = summarize_availability(
        FOREX_SYMBOLS,
        available_symbols=set(FOREX_SYMBOLS),
        unavailable_instruments=set(),
        when=CLOSED_SATURDAY,
    )
    assert summary["market_open"] is False
    assert summary["symbols_available"] == 0
    assert all(a["reason"] == AVAIL_MARKET_CLOSED for a in summary["availability"])
    # The reason distinguishes market closure and carries boundary context.
    assert all(a["detail"] for a in summary["availability"])


def test_market_closed_reason_only_when_session_closed():
    # Open market + symbol not on the account → an account reason, never
    # market_closed (validation rule: market_closed implies a closed session).
    avail = evaluate_symbol_availability("EURUSD", set(), set(), when=OPEN_SUNDAY)
    assert avail.market_open is True
    assert avail.reason == AVAIL_ACCOUNT_INSTRUMENT_UNAVAILABLE

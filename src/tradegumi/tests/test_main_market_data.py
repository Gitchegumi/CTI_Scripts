"""Focused tests for main-loop market data helper behavior."""

from datetime import datetime

from pytz import timezone

from tradegumi.main import _latest_prices, _loop_state_diagnostics, _should_poll_market_data
from tradegumi.price_observations import DEFAULT_PRICE_HISTORY, PriceObservation

CT_TZ = timezone("America/Chicago")
# Sunday 21:40 Central is inside the open forex week; Saturday is the weekend break.
OPEN_SUNDAY = CT_TZ.localize(datetime(2026, 6, 14, 21, 40))
CLOSED_SATURDAY = CT_TZ.localize(datetime(2026, 6, 13, 12, 0))


class FakeStreamProvider:
    """Provider shape for main-loop polling decision tests."""

    mode = "streaming"
    fallback_active = False

    def __init__(self, status="running") -> None:
        self.status = status

    def snapshot_health(self):
        return {"status": self.status}


def test_latest_prices_reads_shared_observations_without_provider_calls():
    observation = PriceObservation(symbol="ZZZUSD", timestamp="2026-05-30T12:00:00Z", bid=1.1, ask=1.1002)
    DEFAULT_PRICE_HISTORY.publish(observation)

    prices = _latest_prices(["ZZZUSD"])

    assert prices == {"ZZZUSD": {"bid": 1.1, "ask": 1.1002, "spread": 0.0002}}


def test_healthy_streaming_mode_does_not_request_polling(monkeypatch):
    monkeypatch.setattr("tradegumi.config.TRADEGUMI_MARKET_DATA_MODE", "streaming")

    assert _should_poll_market_data(FakeStreamProvider()) is False


def test_streaming_fallback_requests_polling(monkeypatch):
    monkeypatch.setattr("tradegumi.config.TRADEGUMI_MARKET_DATA_MODE", "streaming")
    provider = FakeStreamProvider()
    provider.fallback_active = True

    assert _should_poll_market_data(provider) is True


def test_streaming_reconnect_requests_polling(monkeypatch):
    monkeypatch.setattr("tradegumi.config.TRADEGUMI_MARKET_DATA_MODE", "streaming")

    assert _should_poll_market_data(FakeStreamProvider(status="reconnecting")) is True


# ── Loop-state availability diagnostics (specs/021-market-hours-rescan US3) ───


def test_loop_diagnostics_available_during_open_forex():
    diag = _loop_state_diagnostics("EURUSD", {"EURUSD"}, set(), OPEN_SUNDAY)

    assert diag["market_open"] is True
    assert diag["availability_state"] == "available"
    assert diag["availability_reason"] == "available"
    assert diag["session_boundary"] is None


def test_loop_diagnostics_market_closed_on_weekend():
    diag = _loop_state_diagnostics("EURUSD", {"EURUSD"}, set(), CLOSED_SATURDAY)

    assert diag["market_open"] is False
    assert diag["availability_state"] == "market_closed"
    assert diag["availability_reason"] == "weekend_break"
    assert diag["session_boundary"]  # next-open boundary context present


def test_loop_diagnostics_symbol_unavailable_during_open_forex():
    # Open forex session, but the symbol is not available on the account: the
    # diagnostic must say symbol_unavailable, not market_closed.
    diag = _loop_state_diagnostics("EURUSD", set(), set(), OPEN_SUNDAY)

    assert diag["market_open"] is True
    assert diag["availability_state"] == "symbol_unavailable"
    assert diag["availability_reason"] == "account_instrument_unavailable"

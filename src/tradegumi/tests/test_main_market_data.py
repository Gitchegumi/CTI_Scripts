"""Focused tests for main-loop market data helper behavior."""

from tradegumi.main import _latest_prices, _should_poll_market_data
from tradegumi.price_observations import DEFAULT_PRICE_HISTORY, PriceObservation


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

"""Tests for provider-neutral market data dispatch and polling fallback."""

from dataclasses import dataclass

from tradegumi.market_data import (
    MODE_POLLING,
    MarketDataHealth,
    MarketDataSubscription,
    ObservationDispatcher,
    PollingMarketDataProvider,
)
from tradegumi.price_observations import DASHBOARD_POLL, PriceObservation, RollingPriceHistory


@dataclass
class FakeTick:
    """Minimal pricing tick used by polling-provider tests."""

    symbol: str = "EURUSD"
    bid: float = 1.1
    ask: float = 1.1002
    spread: float = 0.0002
    timestamp: str = "2026-05-30T12:00:00Z"


class FakePricingClient:
    """Execution-client test double that records get_pricing calls."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def get_pricing(self, symbols: list[str]) -> list[FakeTick]:
        self.calls.append(list(symbols))
        return [FakeTick(symbol=symbol) for symbol in symbols]


def test_subscription_normalizes_and_sorts_symbols():
    subscription = MarketDataSubscription.from_symbols([" eurusd ", "GBPUSD", "eurusd"])

    assert subscription.symbols == ("EURUSD", "GBPUSD")
    assert subscription.reason == "startup"


def test_dispatcher_publishes_to_history_and_evaluator_once():
    history = RollingPriceHistory()
    seen: list[str] = []
    dispatcher = ObservationDispatcher(history=history, evaluator=lambda observation: seen.append(observation.symbol))

    observation = PriceObservation(symbol="eurusd", timestamp="2026-05-30T12:00:00Z", bid=1.1)
    dispatcher.publish(observation)

    assert history.latest("EURUSD") == observation
    assert seen == ["EURUSD"]


def test_polling_provider_dispatches_existing_get_pricing_ticks():
    history = RollingPriceHistory()
    seen: list[str] = []
    dispatcher = ObservationDispatcher(history=history, evaluator=lambda observation: seen.append(observation.symbol))
    client = FakePricingClient()
    provider = PollingMarketDataProvider(client, dispatcher, configured_mode=MODE_POLLING)

    provider.start(["EURUSD", "GBPUSD"])
    observations = provider.poll_once()

    assert client.calls == [["EURUSD", "GBPUSD"]]
    assert [observation.source for observation in observations] == [DASHBOARD_POLL, DASHBOARD_POLL]
    assert seen == ["EURUSD", "GBPUSD"]
    assert history.latest("GBPUSD").symbol == "GBPUSD"


def test_polling_provider_resubscribe_replaces_next_symbol_set():
    dispatcher = ObservationDispatcher(history=RollingPriceHistory(), evaluator=lambda observation: None)
    client = FakePricingClient()
    provider = PollingMarketDataProvider(client, dispatcher)

    provider.start(["EURUSD"])
    provider.resubscribe(["USDJPY"], reason="api_rescan")
    provider.poll_once()

    assert client.calls == [["USDJPY"]]
    assert provider.snapshot_health()["active_symbol_count"] == 1


def test_market_data_health_serializes_provider_neutral_fields():
    health = MarketDataHealth(configured_mode="streaming", active_mode="polling", provider="fake")

    payload = health.to_dict()

    assert payload["configured_mode"] == "streaming"
    assert payload["active_mode"] == "polling"
    assert payload["provider"] == "fake"
    assert "last_heartbeat_age_seconds" in payload

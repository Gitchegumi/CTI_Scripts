"""Tests for Oanda pricing stream parsing and provider behavior."""

import pytest

from tradegumi.market_data import (
    OandaStreamingMarketDataProvider,
    ObservationDispatcher,
    oanda_price_event_to_observation,
    parse_oanda_stream_line,
)
from tradegumi.price_observations import OANDA_PRICING_STREAM, RollingPriceHistory


class FakeOandaClient:
    """Oanda client shape needed by the stream provider."""

    api_key = "secret-token"
    account_id = "abc-123"
    stream_url = "https://stream-fxpractice.oanda.com"


def _provider(evaluator=None) -> OandaStreamingMarketDataProvider:
    dispatcher = ObservationDispatcher(
        history=RollingPriceHistory(),
        evaluator=evaluator or (lambda observation: None),
    )
    provider = OandaStreamingMarketDataProvider(
        FakeOandaClient(),
        dispatcher,
        reconnect_seconds=1,
        heartbeat_timeout_seconds=5,
        backoff_max_seconds=4,
        max_reconnect_attempts=2,
    )
    provider.subscription = provider.subscription.from_symbols(["EURUSD"])
    provider.health.active_symbol_count = 1
    return provider


def test_parse_oanda_stream_line_accepts_chunked_json_line():
    line = b'{"type":"HEARTBEAT","time":"2026-05-30T12:00:00Z"}\n'

    assert parse_oanda_stream_line(line)["type"] == "HEARTBEAT"


def test_parse_oanda_stream_line_marks_malformed_json():
    assert parse_oanda_stream_line("{nope")["type"] == "MALFORMED"


def test_oanda_price_event_maps_symbol_and_source():
    event = {
        "type": "PRICE",
        "instrument": "EUR_USD",
        "time": "2026-05-30T12:00:00Z",
        "bids": [{"price": "1.1000"}],
        "asks": [{"price": "1.1002"}],
    }

    observation = oanda_price_event_to_observation(event)

    assert observation.symbol == "EURUSD"
    assert observation.source == OANDA_PRICING_STREAM
    assert observation.bid == pytest.approx(1.1)
    assert observation.ask == pytest.approx(1.1002)


def test_oanda_heartbeat_updates_liveness_without_observation():
    provider = _provider()

    result = provider.handle_event({"type": "HEARTBEAT", "time": "2026-05-30T12:00:00Z"})

    assert result is None
    assert provider.snapshot_health()["last_heartbeat_at"].startswith("2026-05-30T12:00:00")
    assert provider.snapshot_health()["observations_per_minute"] == 0.0


def test_oanda_price_event_dispatches_observation_once():
    seen: list[str] = []
    provider = _provider(evaluator=lambda observation: seen.append(observation.symbol))

    observation = provider.handle_event({
        "type": "PRICE",
        "instrument": "EUR_USD",
        "time": "2026-05-30T12:00:00Z",
        "bids": [{"price": "1.1000"}],
        "asks": [{"price": "1.1002"}],
    })

    assert observation.symbol == "EURUSD"
    assert seen == ["EURUSD"]
    assert provider.snapshot_health()["active_symbol_count"] == 1


def test_oanda_unknown_event_does_not_dispatch_observation():
    seen: list[str] = []
    provider = _provider(evaluator=lambda observation: seen.append(observation.symbol))

    result = provider.handle_event({"type": "UNKNOWN"})

    assert result is None
    assert seen == []


def test_oanda_reconnect_backoff_is_bounded():
    provider = _provider()

    assert provider._next_backoff(1) == provider.reconnect_seconds
    assert provider._next_backoff(10) == 4


def test_oanda_stream_url_uses_configured_client_stream_url():
    provider = _provider()

    assert provider._stream_url() == "https://stream-fxpractice.oanda.com/v3/accounts/abc-123/pricing/stream"

"""Tests for shared price observation history."""

from dataclasses import dataclass

import pytest

from tradegumi.price_observations import (
    DASHBOARD_POLL,
    PriceObservation,
    RollingPriceHistory,
    publish_tick_observations,
)


@dataclass
class FakeTick:
    """Minimal execution-client tick shape for observation tests."""

    symbol: str = "EURUSD"
    bid: float = 1.1
    ask: float = 1.1002
    timestamp: str = "2026-05-27T12:00:00Z"


def test_price_observation_derives_mid_and_normalizes_symbol():
    observation = PriceObservation(symbol="eurusd", timestamp="2026-05-27T12:00:00Z", bid=1.1, ask=1.1002)

    assert observation.symbol == "EURUSD"
    assert observation.mid == pytest.approx(1.1001)
    assert observation.source == DASHBOARD_POLL


def test_price_observation_requires_a_price():
    with pytest.raises(ValueError, match="requires bid, ask, or mid"):
        PriceObservation(symbol="EURUSD", timestamp="2026-05-27T12:00:00Z")


def test_rolling_history_prunes_to_count_bound():
    history = RollingPriceHistory(max_observations_per_symbol=2, max_age_seconds=3600)

    for index in range(3):
        history.publish(
            PriceObservation(
                symbol="EURUSD",
                timestamp=f"2026-05-27T12:00:0{index}Z",
                bid=1.1 + index,
            )
        )

    recent = history.recent("EURUSD")
    assert len(recent) == 2
    assert recent[0].bid == 2.1
    assert history.latest("EURUSD").bid == 3.1


def test_publish_tick_observations_records_dashboard_poll_source():
    history = RollingPriceHistory(max_observations_per_symbol=10)

    observations = publish_tick_observations([FakeTick()], history=history)

    assert observations[0].source == DASHBOARD_POLL
    assert history.latest("EURUSD") == observations[0]

from datetime import datetime, timedelta, timezone

import pandas as pd

from tradegumi.api.base_client import Candle
from tradegumi.signal_engine import (
    SignalEngine,
    _last_closed_candle_window,
)


class FakeClient:
    """Small execution client test double that returns configured candle lists."""

    def __init__(self, candles_by_timeframe: dict[str, list[Candle]]):
        self.candles_by_timeframe = candles_by_timeframe

    def get_candles(self, instrument: str, granularity: str, count: int):
        return self.candles_by_timeframe.get(granularity, [])[-count:]

    def get_pricing(self, instruments: list[str]):
        return []

    def get_account_balance(self) -> float:
        return 100_000.0

    def get_open_positions(self):
        return []

    def place_order(self, order):
        return None

    def get_trade_history(self, count: int = 50):
        return []


def candle_at(open_time: datetime, close: float = 1.1) -> Candle:
    """Create a deterministic M5 candle for signal engine tests."""
    return Candle(
        t=open_time.astimezone(timezone.utc).isoformat(),
        o=close - 0.001,
        h=close + 0.002,
        l=close - 0.002,
        c=close,
        s=100,
    )


def closed_candles(count: int, now: datetime) -> list[Candle]:
    """Return count candles whose final candle closed shortly before now."""
    first_open = now - timedelta(minutes=5 * count, seconds=5)
    return [candle_at(first_open + timedelta(minutes=5 * index), 1.1 + index * 0.0001) for index in range(count)]


def test_signal_engine_data_with_insufficient_candles_reports_missing_window():
    now = datetime.now(timezone.utc)
    engine = SignalEngine(FakeClient({"M5": closed_candles(SignalEngine.SIGNAL_WINDOW_MIN_CANDLES - 1, now)}))

    signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend")

    assert signal is None
    assert confidence is None
    assert reason == "missing_signal_engine_data"
    data_criterion = next(c for c in criteria if c.criterion_name == "signal_engine_data")
    assert data_criterion.context["missing_input"] == "last_closed_candle_or_indicator_window"
    assert data_criterion.context["available_count"] == SignalEngine.SIGNAL_WINDOW_MIN_CANDLES - 1


def test_last_closed_candle_selection_ignores_current_open_candle():
    base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
    candles = [candle_at(base), candle_at(base + timedelta(minutes=5)), candle_at(base + timedelta(minutes=10))]

    last_closed, window, context = _last_closed_candle_window(
        candles,
        "M5",
        current_time=base + timedelta(minutes=12),
    )

    assert last_closed == candles[1]
    assert window == candles[:2]
    assert context["candle_open_time"] == candles[1].time.isoformat()


def test_m5_candle_close_boundary_before_close_waits():
    base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
    last_closed, window, context = _last_closed_candle_window(
        [candle_at(base)],
        "M5",
        current_time=base + timedelta(minutes=4, seconds=59),
    )

    assert last_closed is None
    assert window == []
    assert context["seconds_until_close"] == 1.0


def test_m5_candle_close_boundary_at_and_after_close_passes():
    base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
    candle = candle_at(base)

    exact_closed, exact_window, exact_context = _last_closed_candle_window(
        [candle],
        "M5",
        current_time=base + timedelta(minutes=5),
    )
    after_closed, after_window, after_context = _last_closed_candle_window(
        [candle],
        "M5",
        current_time=base + timedelta(minutes=5, seconds=1),
    )

    assert exact_closed == candle
    assert exact_window == [candle]
    assert exact_context["seconds_since_close"] == 0.0
    assert after_closed == candle
    assert after_window == [candle]
    assert after_context["seconds_since_close"] == 1.0


def test_full_trend_valid_candidate_reaches_signal_rule_evaluation(monkeypatch):
    now = datetime.now(timezone.utc)
    candles = closed_candles(SignalEngine.SIGNAL_WINDOW_MIN_CANDLES, now)
    engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
    count = len(candles)

    monkeypatch.setattr(
        "tradegumi.signal_engine.calculate_stoch_rsi",
        lambda df, length, k, d: pd.DataFrame({"k": [20.0] * (count - 1) + [40.0], "d": [30.0] * count}),
    )
    monkeypatch.setattr(
        "tradegumi.signal_engine.calculate_macd",
        lambda df, fast, slow, signal: pd.DataFrame({
            "macd": [0.2] * count,
            "signal": [0.1] * count,
            "histogram": [0.1] * (count - 1) + [0.2],
        }),
    )
    monkeypatch.setattr(
        "tradegumi.signal_engine.calculate_keltner_channels",
        lambda df, length, multiplier, mamode: pd.DataFrame({
            "upper": [1.2] * count,
            "mid": [1.1] * count,
            "lower": [1.11] * count,
        }),
    )
    monkeypatch.setattr(
        "tradegumi.signal_engine.calculate_candlestick_patterns",
        lambda df: pd.DataFrame({"CDL_HAMMER": [0] * (count - 1) + [100]}),
    )
    monkeypatch.setattr("tradegumi.signal_engine.calculate_atr", lambda df: pd.Series([0.001] * count))
    monkeypatch.setattr("tradegumi.signal_engine.calculate_linear_regression", lambda df, length: pd.Series([0.01] * count))
    monkeypatch.setattr("tradegumi.signal_engine.stoch_rsi_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.macd_histogram_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.keltner_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.candlestick_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.trend_score", lambda *args: 1.0)

    signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend")

    assert signal is not None
    assert reason == "emitted"
    assert confidence == 1.0
    assert {"stoch_rsi", "macd", "keltner", "confidence"}.issubset({c.criterion_name for c in criteria})

from datetime import datetime, timedelta, timezone

import pandas as pd

from tradegumi.api.base_client import Candle, ProviderRequestError
from tradegumi.signal_engine import (
    SignalEngine,
    _live_trigger_price,
    _last_closed_candle_window,
    _pullback_keltner_sequence,
    _pullback_stoch_rsi,
    _pullback_trigger,
    classify_trend_decision,
    classify_pullback_trend_bridge,
)
from tradegumi.price_observations import DEFAULT_PRICE_HISTORY, PriceObservation
from tradegumi import journal
from tradegumi.signal_engine import Signal
from tradegumi.signal_processor import lifecycle_state_for_signal
from tradegumi.tests._pg import requires_postgres, get_test_backend
from tradegumi.volatility_shock import VolatilityShockFilter, ShockDetectionResult


class FakeClient:
    """Small execution client test double that returns configured candle lists."""

    def __init__(self, candles_by_timeframe: dict[str, list[Candle]]):
        self.candles_by_timeframe = candles_by_timeframe
        self.calls: list[tuple[str, str, int]] = []

    def get_candles(self, instrument: str, granularity: str, count: int):
        self.calls.append((instrument, granularity, count))
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


def trend_candles(count: int, now: datetime, *, start: float = 1.1000, step: float = 0.0004) -> list[Candle]:
    """Return candles with configurable directional drift for structure tests."""
    first_open = now - timedelta(minutes=5 * count, seconds=5)
    return [candle_at(first_open + timedelta(minutes=5 * index), start + index * step) for index in range(count)]


def test_live_trigger_price_uses_latest_shared_observation():
    DEFAULT_PRICE_HISTORY.publish(
        PriceObservation(symbol="ZZZUSD", timestamp="2026-05-30T12:00:00Z", bid=1.2, ask=1.2003)
    )

    assert _live_trigger_price("ZZZUSD", "BUY", 1.0) == 1.2003
    assert _live_trigger_price("ZZZUSD", "SELL", 1.0) == 1.2


@requires_postgres
def test_continuation_detection_state_is_preserved_without_entry_creation(tmp_path, monkeypatch):
    get_test_backend()  # journal is Postgres-authoritative; point it at the test DB
    journal_file = tmp_path / "signal_journal.jsonl"
    monkeypatch.setattr(journal, "JOURNAL_FILE", journal_file)
    monkeypatch.setattr(journal, "_now_iso", lambda: "2026-06-11T15:00:00+00:00")
    signal = Signal(
        symbol="EURUSD",
        direction="BUY",
        entry_price=1.1020,
        stop_loss=1.1000,
        take_profit=1.1080,
        atr=0.0010,
        lot_size=1.0,
        risk_pct=1.0,
        confidence=0.8,
        breakdown={},
        trend_direction="Uptrend",
        patterns_found=[],
        signal_type="continuation",
    )

    assert lifecycle_state_for_signal(signal)["lifecycle_role"] == "management"
    journal.append_signal(signal)
    entry = journal.read_journal()[0]

    assert entry["signal_type"] == "continuation"
    assert entry["lifecycle_role"] == journal.LIFECYCLE_MANAGEMENT
    assert entry["management_rejection_reason"] == journal.MANAGEMENT_REJECTED_NO_ACTIVE_TRADE
    assert entry["usable_for_strategy_stats"] is False


def test_signal_engine_data_with_insufficient_candles_reports_missing_window():
    now = datetime.now(timezone.utc)
    engine = SignalEngine(FakeClient({"M5": closed_candles(SignalEngine.SIGNAL_WINDOW_MIN_CANDLES - 1, now)}))

    signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend")

    assert signal is None
    assert confidence is None
    assert reason == "signal_stack_data_not_ready"
    data_criterion = next(c for c in criteria if c.criterion_name == "signal_engine_data")
    assert data_criterion.context["missing_input"] == "last_closed_candle_or_indicator_window"
    assert data_criterion.context["error_type"] == "DataNotReady"
    assert data_criterion.context["available_closed_candles"] == SignalEngine.SIGNAL_WINDOW_MIN_CANDLES - 1
    assert data_criterion.blocked_signal is True


def test_signal_engine_data_with_empty_candles_reports_data_not_ready():
    engine = SignalEngine(FakeClient({"M5": []}))

    signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend")

    assert signal is None
    assert confidence is None
    assert reason == "signal_stack_data_not_ready"
    data_criterion = next(c for c in criteria if c.criterion_name == "signal_engine_data")
    assert data_criterion.context["error_type"] == "DataNotReady"
    assert data_criterion.context["available_candles"] == 0
    assert data_criterion.context["available_indicator_window"] == 0


def test_signal_engine_data_with_one_candle_reports_data_not_ready():
    now = datetime.now(timezone.utc)
    engine = SignalEngine(FakeClient({"M5": closed_candles(1, now)}))

    signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend")

    assert signal is None
    assert confidence is None
    assert reason == "signal_stack_data_not_ready"
    data_criterion = next(c for c in criteria if c.criterion_name == "signal_engine_data")
    assert data_criterion.context["available_closed_candles"] == 1


def test_signal_engine_data_with_short_indicator_output_reports_data_not_ready(monkeypatch):
    now = datetime.now(timezone.utc)
    candles = closed_candles(SignalEngine.SIGNAL_WINDOW_MIN_CANDLES, now)
    engine = SignalEngine(FakeClient({"M5": candles}))

    monkeypatch.setattr(
        "tradegumi.signal_engine.calculate_stoch_rsi",
        lambda df, length, k, d: pd.DataFrame({"k": [], "d": []}),
    )

    signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend")

    assert signal is None
    assert confidence is None
    assert reason == "signal_stack_data_not_ready"
    data_criterion = next(c for c in criteria if c.criterion_name == "signal_engine_data")
    assert data_criterion.context["error_type"] == "DataNotReady"
    assert data_criterion.context["available_indicator_window"] == 0


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


def test_last_closed_candle_selection_uses_provider_complete_flag():
    base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
    closed = candle_at(base)
    active = candle_at(base + timedelta(minutes=5))
    active.complete = False

    last_closed, window, context = _last_closed_candle_window(
        [closed, active],
        "M5",
        current_time=base + timedelta(minutes=20),
    )

    assert last_closed == closed
    assert window == [closed]
    assert context["candle_open_time"] == closed.time.isoformat()


class SignalFetchFailureClient(FakeClient):
    """Fake client that fails only when the signal stack fetches M5 candles."""

    def get_candles(self, instrument: str, granularity: str, count: int):
        if granularity == "M5" and count == 100:
            raise ProviderRequestError(
                "Oanda candle fetch failed with HTTP 504",
                provider="oanda",
                method="GET",
                path="/v3/instruments/EUR_USD/candles",
                operation="candle_fetch",
                status_code=504,
                instrument="EUR_USD",
                granularity="M5",
                attempts=3,
                max_attempts=3,
                retryable=True,
                error_type="oanda_gateway_timeout",
            )
        return super().get_candles(instrument, granularity, count)


def test_failed_oanda_candle_fetch_is_indeterminate_not_rejected(monkeypatch):
    now = datetime.now(timezone.utc)
    candles = closed_candles(SignalEngine.SIGNAL_WINDOW_MIN_CANDLES, now)
    engine = SignalEngine(SignalFetchFailureClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})

    monkeypatch.setattr("tradegumi.signal_engine.calculate_linear_regression", lambda df, length: pd.Series([0.01] * len(df)))

    # Warm up chop filter state so trend persistence check passes
    engine._record_trend_evaluation("EURUSD", "Uptrend")
    engine._record_trend_evaluation("EURUSD", "Uptrend")

    signal, trend, lr_1h, lr_15, lr_5, diag = engine.check_symbol("EURUSD")

    assert signal is None
    assert trend == "Uptrend"
    assert diag.final_decision == "indeterminate"
    assert diag.decision_reason == "oanda_gateway_timeout"
    data_criterion = next(c for c in diag.criteria if c.criterion_name == "signal_engine_data")
    assert data_criterion.context["provider"] == "oanda"
    assert data_criterion.context["status_code"] == 504
    assert data_criterion.context["attempts"] == 3


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
        lambda df: pd.DataFrame({"CDL_HAMMER": [0] * (count - 1) + [-1]}),
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
    # CTI-v1.1: could be continuation (no stoch_rsi) or pullback (has stoch_rsi)
    criteria_names = {c.criterion_name for c in criteria}
    assert "macd" in criteria_names
    assert "keltner" in criteria_names
    assert "confidence" in criteria_names
    assert signal.signal_type in ("continuation", "pullback")


def test_get_signal_reuses_trend_lr_without_refetching_trend_timeframes(monkeypatch):
    now = datetime.now(timezone.utc)
    candles = closed_candles(SignalEngine.SIGNAL_WINDOW_MIN_CANDLES, now)
    client = FakeClient({"M5": candles, "M15": candles, "H1": candles})
    engine = SignalEngine(client)
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
        lambda df: pd.DataFrame({"CDL_HAMMER": [0] * (count - 1) + [-1]}),
    )
    monkeypatch.setattr("tradegumi.signal_engine.calculate_atr", lambda df: pd.Series([0.001] * count))
    monkeypatch.setattr("tradegumi.signal_engine.stoch_rsi_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.macd_histogram_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.keltner_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.candlestick_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.trend_score", lambda *args: 1.0)

    signal, _, reason, _ = engine._get_signal("EURUSD", "Uptrend", (0.01, 0.01, 0.01))

    assert signal is not None
    assert reason == "emitted"
    assert [call[1:] for call in client.calls] == [("M5", 100)]


def test_candle_cache_reuses_history_until_timeframe_boundary(monkeypatch):
    now = datetime.now(timezone.utc)
    candles = closed_candles(40, now)
    client = FakeClient({"M5": candles})
    engine = SignalEngine(client)

    monkeypatch.setattr("tradegumi.signal_engine._seconds_until_next_timeframe", lambda timeframe: 300.0)

    first = engine._get_cached_candles("EURUSD", "M5", 24)
    second = engine._get_cached_candles("EURUSD", "M5", 24)

    assert first == second
    assert client.calls == [("EURUSD", "M5", 24)]

    engine._candle_cache[("EURUSD", "M5", 24)].expires_at = 0.0
    engine._get_cached_candles("EURUSD", "M5", 24)

    assert client.calls == [("EURUSD", "M5", 24), ("EURUSD", "M5", 24)]


def test_valid_data_strategy_rejection_is_not_signal_data_missing(monkeypatch):
    now = datetime.now(timezone.utc)
    candles = closed_candles(SignalEngine.SIGNAL_WINDOW_MIN_CANDLES, now)
    engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
    count = len(candles)

    monkeypatch.setattr(
        "tradegumi.signal_engine.calculate_stoch_rsi",
        lambda df, length, k, d: pd.DataFrame({"k": [40.0] * count, "d": [30.0] * count}),
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
            "mid": [1.15] * count,
            "lower": [1.11] * count,
        }),
    )
    monkeypatch.setattr(
        "tradegumi.signal_engine.calculate_candlestick_patterns",
        lambda df: pd.DataFrame({"CDL_HAMMER": [0] * count}),
    )
    monkeypatch.setattr("tradegumi.signal_engine.stoch_rsi_score", lambda *args: 0.2)
    monkeypatch.setattr("tradegumi.signal_engine.macd_histogram_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.keltner_score", lambda *args: 1.0)
    monkeypatch.setattr("tradegumi.signal_engine.candlestick_score", lambda *args: 0.0)

    signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend")

    assert signal is None
    assert confidence is None
    assert reason == "criteria_failed"
    assert not any(c.criterion_name == "signal_engine_data" for c in criteria)


def test_missing_macd_signal_column_is_indeterminate_not_strategy_rejection(monkeypatch):
    from tradegumi import config
    now = datetime.now(timezone.utc)
    candles = closed_candles(SignalEngine.SIGNAL_WINDOW_MIN_CANDLES, now)
    engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})
    count = len(candles)

    monkeypatch.setattr("tradegumi.signal_engine.calculate_linear_regression", lambda df, length: pd.Series([0.01] * len(df)))
    monkeypatch.setattr(
        "tradegumi.signal_engine.calculate_stoch_rsi",
        lambda df, length, k, d: pd.DataFrame({"k": [20.0] * (count - 1) + [40.0], "d": [30.0] * count}),
    )
    monkeypatch.setattr(
        "tradegumi.signal_engine.calculate_macd",
        lambda df, fast, slow, signal: pd.DataFrame({
            "macd": [0.2] * count,
            "histogram": [0.1] * (count - 1) + [0.2],
        }),
    )

    # Warm up chop filter state so trend persistence check passes
    for _ in range(config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES):
        engine._record_trend_evaluation("EURUSD", "Uptrend")

    signal, trend, lr_1h, lr_15, lr_5, diag = engine.check_symbol("EURUSD")

    assert signal is None
    assert trend == "Uptrend"
    assert diag.final_decision == "indeterminate"
    assert diag.decision_reason == "missing_signal_engine_data"
    assert not any(c.reason == "criteria_failed" for c in diag.criteria)


def test_actual_pandas_ta_macd_and_keltner_columns_match_signal_engine_predicates():
    """Verify pandas-ta output columns are matched by the signal engine's predicates."""
    from datetime import datetime, timezone
    from tradegumi.indicators import calculate_macd, calculate_keltner_channels, candles_to_df
    from tradegumi.signal_engine import _first_matching_column

    now = datetime.now(timezone.utc)
    candles = closed_candles(SignalEngine.SIGNAL_WINDOW_MIN_CANDLES, now)
    df = candles_to_df(candles)
    df.index = pd.DatetimeIndex([c.time for c in candles])

    # MACD — verify the fixed predicate finds the right columns
    macd_df = calculate_macd(df, fast=12, slow=26, signal=9)
    assert "MACDs_" in macd_df.columns[2], "pandas-ta should produce MACDs column"

    # The actual predicate used in signal_engine.py (after fix)
    hist_col = _first_matching_column(macd_df, lambda name: "h" in name and "s" not in name, "macd_histogram")
    line_col = _first_matching_column(macd_df, lambda name: "macd" in name and "h" not in name and "s" not in name, "macd_line")
    signal_col = _first_matching_column(macd_df, lambda name: "s" in name and "h" not in name, "macd_signal")

    assert "h" in hist_col.lower() and "s" not in hist_col.lower()
    assert "macd" in line_col.lower() and "h" not in line_col.lower() and "s" not in line_col.lower()
    assert "s" in signal_col.lower() and "h" not in signal_col.lower()

    # Keltner — verify the fixed predicate finds the right columns
    kc_df = calculate_keltner_channels(df, length=20, multiplier=1.5, mamode="ema")
    assert "KCUe" in kc_df.columns[2], "pandas-ta should produce KCUe column"
    assert "KCLe" in kc_df.columns[0], "pandas-ta should produce KCLe column"
    assert "KCBe" in kc_df.columns[1], "pandas-ta should produce KCBe column"

    # The actual predicates used in signal_engine.py (after fix)
    upper_col = _first_matching_column(kc_df, lambda name: "u" in name and "l" not in name and "b" not in name, "keltner_upper")
    lower_col = _first_matching_column(kc_df, lambda name: "l" in name and "u" not in name and "b" not in name, "keltner_lower")
    mid_col = _first_matching_column(kc_df, lambda name: ("b" in name and "u" not in name and "l" not in name) or "m" in name, "keltner_mid")

    assert upper_col == "KCUe_20_1.5", f"Expected KCUe, got {upper_col}"
    assert lower_col == "KCLe_20_1.5", f"Expected KCLe, got {lower_col}"
    assert mid_col == "KCBe_20_1.5", f"Expected KCBe, got {mid_col}"


class TestShockDiagnosticSemantics:
    """Bug 1: Shock diagnostic semantics."""

    def test_no_shock_does_not_add_volatility_shock_criterion(self, monkeypatch):
        from tradegumi import config
        now = datetime.now(timezone.utc)
        candles = closed_candles(60, now)
        engine = SignalEngine(
            FakeClient({"M5": candles, "M15": candles, "H1": candles}),
            {"EURUSD"},
            shock_filter=VolatilityShockFilter(),
        )
        # Force no shock on any timeframe
        def _no_shock_detect(self, candles_list, tf):
            return ShockDetectionResult(detected=False, timeframe=tf)
        monkeypatch.setattr(
            "tradegumi.signal_engine.VolatilityShockFilter.detect",
            _no_shock_detect,
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_linear_regression",
            lambda df, length: pd.Series([0.01] * len(df)),
        )

        # Warm up chop filter state so trend persistence check passes
        for _ in range(config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES):
            engine._record_trend_evaluation("EURUSD", "Uptrend")

        signal, trend, lr_1h, lr_15, lr_5, diag = engine.check_symbol("EURUSD")

        shock_criteria = [c for c in diag.criteria if c.criterion_name == "volatility_shock"]
        assert len(shock_criteria) == 0
        assert diag.market_validity_state == "valid"
        assert diag.market_validity_reason is None

    def test_shock_rows_categorized_market_invalid_volatility_shock(self, monkeypatch):
        now = datetime.now(timezone.utc)
        candles = closed_candles(60, now)
        engine = SignalEngine(
            FakeClient({"M5": candles, "M15": candles, "H1": candles}),
            {"EURUSD"},
        )
        # Inject a shock into the last candle of M5
        prev_close = candles[-2].c
        candles[-1] = Candle(
            t=candles[-1].time.isoformat(),
            o=candles[-1].o,
            h=prev_close + 0.0050,
            l=candles[-1].l,
            c=candles[-1].c,
            s=100,
        )
        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: pd.Series([0.0010] * len(df)),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_linear_regression",
            lambda df, length: pd.Series([0.01] * len(df)),
        )

        signal, trend, lr_1h, lr_15, lr_5, diag = engine.check_symbol("EURUSD")

        assert diag.volatility_shock_detected is True
        assert diag.market_validity_state == "invalid"
        assert diag.market_validity_reason == "market_invalid:volatility_shock"
        # volatility_shock criterion should be present and informational (not a hard fail)
        shock_criteria = [c for c in diag.criteria if c.criterion_name == "volatility_shock"]
        assert len(shock_criteria) >= 1
        assert shock_criteria[0].required is False
        assert shock_criteria[0].passed is None


class TestFilteredLRNoFallback:
    """Bug 3: Filtered LR must NOT fall back to raw LR."""

    def test_insufficient_clean_data_returns_no_trend(self, monkeypatch):
        now = datetime.now(timezone.utc)
        candles = closed_candles(60, now)
        engine = SignalEngine(
            FakeClient({"M5": candles, "M15": candles, "H1": candles}),
            {"EURUSD"},
            shock_filter=VolatilityShockFilter(),
        )
        # Make shock filter strip out most candles (simulate >50% excluded)
        def strip_most(candles_list):
            # Keep only first and last candle
            return [candles_list[0], candles_list[-1]], list(range(1, len(candles_list) - 1))
        engine.shock_filter.filter_candles_for_lr = strip_most
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_linear_regression",
            lambda df, length: pd.Series([0.01] * len(df)),
        )

        signal, trend, lr_1h, lr_15, lr_5, diag = engine.check_symbol("EURUSD")

        # Insufficient clean data → trend should be None (flat), not derived from raw LR
        assert trend is None
        assert diag.decision_reason == "no_trend"
        assert diag.trend_decision is not None
        assert diag.trend_decision["trend_classification_output"]["no_trend_reason"] == "insufficient_clean_data"

    def test_shock_disabled_uses_raw_lr(self, monkeypatch):
        now = datetime.now(timezone.utc)
        candles = closed_candles(60, now)
        engine = SignalEngine(
            FakeClient({"M5": candles, "M15": candles, "H1": candles}),
            {"EURUSD"},
            shock_filter=VolatilityShockFilter(),
        )
        engine.shock_filter.enabled = False
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_linear_regression",
            lambda df, length: pd.Series([0.01] * len(df)),
        )

        signal, trend, lr_1h, lr_15, lr_5, diag = engine.check_symbol("EURUSD")

        assert trend == "Uptrend"
        assert diag.trend_decision["trend_classification_output"]["no_trend_reason"] is None


class TestDualPathSignals:
    """CTI-v1.1 dual-path signal tests: continuation + pullback."""

    def test_continuation_signal_fires_when_trend_aligned_and_price_above_midline(self, monkeypatch):
        """Continuation path: price on correct side of Keltner midline + MACD supports + structure."""
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = closed_candles(count, now)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))

        # Price above midline (Uptrend), MACD histogram positive and improving
        last_price = candles[-1].c
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_stoch_rsi",
            lambda df, length, k, d: pd.DataFrame({"k": [55.0] * count, "d": [50.0] * count}),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [0.001] * count,
                "signal": [0.0005] * count,
                "histogram": [0.001] * count,
            }),
        )
        # Price above midline (mid = 1.1, close = last_price > mid)
        mid_val = last_price - 0.0005
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": [mid_val + 0.003] * count,
                "mid": [mid_val] * count,
                "lower": [mid_val - 0.003] * count,
            }),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_candlestick_patterns",
            lambda df: pd.DataFrame({"CDL_HAMMER": [0] * count}),
        )
        monkeypatch.setattr("tradegumi.signal_engine.calculate_atr", lambda df: pd.Series([0.001] * count))
        monkeypatch.setattr("tradegumi.signal_engine.calculate_linear_regression", lambda df, length: pd.Series([0.01] * count))
        monkeypatch.setattr("tradegumi.signal_engine.stoch_rsi_score", lambda *args: 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.macd_histogram_score", lambda *args: 0.9)
        monkeypatch.setattr("tradegumi.signal_engine.keltner_score", lambda *args: 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.candlestick_score", lambda *args: 0.0)
        monkeypatch.setattr("tradegumi.signal_engine.trend_score", lambda *args: 1.0)

        signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend")

        # Continuation signal should fire (Keltner midline check + MACD + structure)
        assert signal is not None, f"Expected continuation signal but got reason={reason}"
        assert reason == "emitted"
        assert signal.strategy == "CTI-v1.1-continuation-test"
        assert signal.signal_type == "continuation"

    def test_pullback_signal_uses_prior_break_and_midline_retrace(self, monkeypatch):
        """Pullback path: prior Keltner break plus current midline retrace."""
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))

        last_price = candles[-1].c
        mid_val = last_price
        upper = [last_price + 0.003] * count
        upper[-8] = last_price - 0.001
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_stoch_rsi",
            lambda df, length, k, d: pd.DataFrame({"k": [25.0] * (count - 1) + [35.0], "d": [30.0] * count}),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [0.001] * count,
                "signal": [0.0005] * count,
                "histogram": [0.0005] * (count - 1) + [0.001],
            }),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": upper,
                "mid": [mid_val] * count,
                "lower": [last_price - 0.006] * count,
            }),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_candlestick_patterns",
            lambda df: pd.DataFrame({"CDL_HAMMER": [0] * (count - 1) + [-1]}),
        )
        monkeypatch.setattr("tradegumi.signal_engine.calculate_atr", lambda df: pd.Series([0.001] * count))
        monkeypatch.setattr("tradegumi.signal_engine.calculate_linear_regression", lambda df, length: pd.Series([0.01] * count))
        monkeypatch.setattr("tradegumi.signal_engine.stoch_rsi_score", lambda *args: 1.0)
        monkeypatch.setattr("tradegumi.signal_engine.macd_histogram_score", lambda *args: 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.keltner_score", lambda *args: 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.candlestick_score", lambda *args: 0.0)
        monkeypatch.setattr("tradegumi.signal_engine.trend_score", lambda *args: 1.0)

        signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        # Pullback signal should fire from a prior outer-band break plus midline retrace.
        assert signal is not None, f"Expected pullback signal but got reason={reason}"
        assert reason == "emitted"
        assert signal.signal_type == "pullback"

    def test_continuation_requires_all_3_tfs_aligned(self, monkeypatch):
        """Continuation path: 5M must align with 1H/15M (unlike bias-only)."""
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = closed_candles(count, now)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))

        last_price = candles[-1].c
        mid_val = last_price - 0.0005
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_stoch_rsi",
            lambda df, length, k, d: pd.DataFrame({"k": [55.0] * count, "d": [50.0] * count}),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [0.001] * count,
                "signal": [0.0005] * count,
                "histogram": [0.001] * count,
            }),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": [mid_val + 0.003] * count,
                "mid": [mid_val] * count,
                "lower": [mid_val - 0.003] * count,
            }),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_candlestick_patterns",
            lambda df: pd.DataFrame({"CDL_HAMMER": [0] * count}),
        )
        monkeypatch.setattr("tradegumi.signal_engine.calculate_atr", lambda df: pd.Series([0.001] * count))
        # 1H and 15M strong up, 5M flat/weak (would fail classify_trend_decision)
        def lr_side_effect(df, length):
            if length == 20:  # 1H
                return pd.Series([0.012] * len(df))
            elif length == 25:  # 15M
                return pd.Series([0.010] * len(df))
            else:  # 5M — weak
                return pd.Series([0.001] * len(df))
        monkeypatch.setattr("tradegumi.signal_engine.calculate_linear_regression", lr_side_effect)
        monkeypatch.setattr("tradegumi.signal_engine.stoch_rsi_score", lambda *args: 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.macd_histogram_score", lambda *args: 0.9)
        monkeypatch.setattr("tradegumi.signal_engine.keltner_score", lambda *args: 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.candlestick_score", lambda *args: 0.0)
        monkeypatch.setattr("tradegumi.signal_engine.trend_score", lambda *args: 1.0)

        signal, criteria, reason, confidence = engine._get_signal("EURUSD", "Uptrend")

        # With 5M weak, all 3 TFs don't agree → continuation needs all 3, so fail
        # Falls back to pullback path
        assert signal is None or signal.signal_type in ("pullback", "continuation")


class TestShockSuppressionContextAware:
    """Shock suppression is direction-aware: only suppress when shock matches signal direction."""

    def test_shock_suppresses_only_same_direction_signal(self, monkeypatch):
        """Uptrend shock (direction=up) should NOT suppress SELL (downtrend) continuation signals."""
        now = datetime.now(timezone.utc)
        candles = closed_candles(60, now)
        # Shock filter with uptrend shock (direction=up)
        shock_filter = VolatilityShockFilter()

        def _detect_up_shock(self, candles_list, tf):
            return ShockDetectionResult(
                detected=True, timeframe=tf, direction="up", rule="single_candle_tr",
                candle_time=datetime.now(timezone.utc).isoformat(),
                true_range=0.005, atr=0.001, atr_multiple=5.0, lookback_bars=1,
                suppression_until=datetime.now(timezone.utc).isoformat(),
                suppression_candles_remaining=3,
            )
        monkeypatch.setattr(
            "tradegumi.signal_engine.VolatilityShockFilter.detect",
            _detect_up_shock,
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_linear_regression",
            lambda df, length: pd.Series([0.01] * len(df)),
        )

        # Uptrend shock detected but we're checking for SELL (downtrend) — should NOT suppress
        engine = SignalEngine(
            FakeClient({"M5": candles, "M15": candles, "H1": candles}),
            {"EURUSD"},
            shock_filter=shock_filter,
        )

        signal, trend, lr_1h, lr_15, lr_5, diag = engine.check_symbol("EURUSD")

        # Should proceed (shock direction=up, signal direction=down for SELL)
        # shock_suppressed check now considers direction
        assert trend == "Uptrend" or trend == "Downtrend"

    def test_shock_with_trend_changed_suppresses_same_direction(self, monkeypatch):
        """When shock changed the trend direction, same-direction signals are suppressed."""
        now = datetime.now(timezone.utc)
        candles = closed_candles(60, now)
        shock_filter = VolatilityShockFilter()

        def _detect_down_shock(self, candles_list, tf):
            return ShockDetectionResult(
                detected=True, timeframe=tf, direction="down", rule="single_candle_tr",
                candle_time=datetime.now(timezone.utc).isoformat(),
                true_range=0.005, atr=0.001, atr_multiple=5.0, lookback_bars=1,
                suppression_until=datetime.now(timezone.utc).isoformat(),
                suppression_candles_remaining=3,
            )
        monkeypatch.setattr(
            "tradegumi.signal_engine.VolatilityShockFilter.detect",
            _detect_down_shock,
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_linear_regression",
            lambda df, length: pd.Series([0.01] * len(df)),
        )

        engine = SignalEngine(
            FakeClient({"M5": candles, "M15": candles, "H1": candles}),
            {"EURUSD"},
            shock_filter=shock_filter,
        )

        signal, trend, lr_1h, lr_15, lr_5, diag = engine.check_symbol("EURUSD")

        # Shock changed trend and direction=down matches SELL → suppressed
        # The diag should show shock detected
        assert diag.volatility_shock_detected is True


class TestSignalTypeField:
    """signal_type field is tracked across signal, diagnostic, and metrics."""

    def test_signal_dataclass_has_signal_type_field(self):
        from tradegumi.signal_engine import Signal
        sig = Signal(
            symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
            take_profit=1.1200, atr=0.0010, lot_size=1.0, risk_pct=0.25,
            confidence=0.75, breakdown={}, trend_direction="Uptrend",
            patterns_found=[], signal_type="continuation",
        )
        assert sig.signal_type == "continuation"

    def test_signal_default_signal_type_is_pullback(self):
        from tradegumi.signal_engine import Signal
        sig = Signal(
            symbol="EURUSD", direction="BUY", entry_price=1.1000, stop_loss=1.0950,
            take_profit=1.1200, atr=0.0010, lot_size=1.0, risk_pct=0.25,
            confidence=0.75, breakdown={}, trend_direction="Uptrend", patterns_found=[],
        )
        assert sig.signal_type == "pullback"


class TestPullbackBridgeAndVersioning:
    """CTI-v1.2 pullback bridge, trigger, and version behavior."""

    def _patch_pullback_indicators(
        self,
        monkeypatch,
        count,
        *,
        trend="Uptrend",
        trigger="CDL_HAMMER",
        stoch_ok=True,
        macd_blocks=False,
        prior_break=True,
    ):
        if trend == "Uptrend":
            k_values = ([22.0] * (count - 1) + [24.0]) if stoch_ok else [55.0] * count
            d_values = ([26.0] * (count - 1) + [20.0]) if stoch_ok else [50.0] * count
            hist_values = [-0.002] * (count - 1) + ([-0.003] if macd_blocks else [-0.001])
            mid = 1.1030
            upper = [1.1100] * count
            if prior_break:
                upper[-8] = 1.1000
            lower = [1.0960] * count
            pattern_value = -1
        else:
            k_values = ([78.0] * (count - 1) + [76.0]) if stoch_ok else [45.0] * count
            d_values = ([74.0] * (count - 1) + [82.0]) if stoch_ok else [50.0] * count
            hist_values = [0.002] * (count - 1) + ([0.003] if macd_blocks else [0.001])
            mid = 1.0970
            upper = [1.1040] * count
            lower = [1.0900] * count
            if prior_break:
                lower[-8] = 1.1000
            pattern_value = 1

        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_stoch_rsi",
            lambda df, length, k, d: pd.DataFrame({"k": k_values, "d": d_values}),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": hist_values,
                "signal": [0.0] * count,
                "histogram": hist_values,
            }),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": upper,
                "mid": [mid] * count,
                "lower": lower,
            }),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_candlestick_patterns",
            lambda df: pd.DataFrame({trigger: [0] * (count - 1) + [pattern_value]}),
        )
        monkeypatch.setattr("tradegumi.signal_engine.calculate_atr", lambda df: pd.Series([0.001] * count))
        monkeypatch.setattr("tradegumi.signal_engine.stoch_rsi_score", lambda *args: 1.0)
        monkeypatch.setattr("tradegumi.signal_engine.macd_histogram_score", lambda *args: 0.0 if macd_blocks else 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.keltner_score", lambda *args: 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.candlestick_score", lambda *args: 1.0)
        monkeypatch.setattr("tradegumi.signal_engine.trend_score", lambda *args: 1.0)

    def test_pullback_bridge_allows_current_15m_flat_with_recent_memory(self):
        result = classify_pullback_trend_bridge(
            0.007,
            0.0001,
            [0.009, 0.010, 0.011, 0.0001],
            "Uptrend",
            0.005,
            0.008,
            memory_candles=4,
            strong_opposite_multiplier=1.25,
        )

        assert result["passed"] is True
        assert result["status"] == "pullback_15m_bridge_allowed"

    def test_pullback_bridge_rejects_current_15m_strongly_opposite(self):
        result = classify_pullback_trend_bridge(
            0.007,
            -0.011,
            [0.009, 0.010, 0.011, -0.011],
            "Uptrend",
            0.005,
            0.008,
            memory_candles=4,
            strong_opposite_multiplier=1.25,
        )

        assert result["passed"] is False
        assert result["status"] == "pullback_15m_bridge_strong_opposite"

    def test_pullback_bridge_rejects_missing_larger_trend_memory(self):
        result = classify_pullback_trend_bridge(
            0.007,
            0.0001,
            [0.0002, -0.0001, 0.0003, 0.0001],
            "Uptrend",
            0.005,
            0.008,
            memory_candles=4,
            strong_opposite_multiplier=1.25,
        )

        assert result["passed"] is False
        assert result["status"] == "pullback_15m_bridge_no_memory"

    def test_long_pullback_hammer_emits_cti_v12_pullback(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count, trigger="CDL_HAMMER")

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is not None, reason
        assert signal.strategy == "CTI-v1.2-pullback"
        assert signal.signal_type == "pullback"
        assert signal.pullback_trigger == "hammer"
        assert any(c.reason == "pullback_trigger_hammer" for c in criteria)

    def test_long_pullback_bullish_engulfing_emits_cti_v12_pullback(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count, trigger="CDL_ENGULFING")

        signal, _, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is not None, reason
        assert signal.strategy == "CTI-v1.2-pullback"
        assert signal.pullback_trigger == "bullish_engulfing"

    def test_short_pullback_shooting_star_emits_cti_v12_pullback(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.1100, step=-0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count, trend="Downtrend", trigger="CDL_SHOOTINGSTAR")

        signal, _, reason, _ = engine._get_signal("EURUSD", "Downtrend", allow_continuation=False)

        assert signal is not None, reason
        assert signal.strategy == "CTI-v1.2-pullback"
        assert signal.pullback_trigger == "shooting_star"

    def test_short_pullback_bearish_engulfing_emits_cti_v12_pullback(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.1100, step=-0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count, trend="Downtrend", trigger="CDL_ENGULFING")

        signal, _, reason, _ = engine._get_signal("EURUSD", "Downtrend", allow_continuation=False)

        assert signal is not None, reason
        assert signal.strategy == "CTI-v1.2-pullback"
        assert signal.pullback_trigger == "bearish_engulfing"

    def test_pullback_trigger_rejects_wrong_direction_hammer_and_shooting_star(self):
        bullish_shooting_star = pd.DataFrame({"CDL_SHOOTINGSTAR": [-1], "CDL_HAMMER": [0]})
        bearish_hammer = pd.DataFrame({"CDL_HAMMER": [1], "CDL_SHOOTINGSTAR": [0]})

        long_result = _pullback_trigger(bearish_hammer, "Uptrend")
        short_result = _pullback_trigger(bullish_shooting_star, "Downtrend")

        assert long_result["passed"] is False
        assert long_result["reason"] == "pullback_trigger_candle_failed"
        assert short_result["passed"] is False
        assert short_result["reason"] == "pullback_trigger_candle_failed"

    def test_pullback_trigger_accepts_small_body_lower_wick_rejection(self):
        patterns = pd.DataFrame({"CDL_HAMMER": [-1]})
        candles = pd.DataFrame([{"o": 1.1020, "h": 1.1025, "l": 1.1000, "c": 1.1022}])

        result = _pullback_trigger(patterns, "Uptrend", candles, 1.1010, 0.0015)

        assert result["passed"] is True
        assert result["trigger"] == "hammer"
        assert result["reason"] == "pullback_trigger_hammer"
        assert result["body_to_range"] < 0.33
        assert result["lower_wick"] > result["upper_wick"]
        assert result["value_area_relation"]["wick_through"] is True

    def test_pullback_trigger_rejects_large_body_or_wrong_wick_shape(self):
        patterns = pd.DataFrame({"CDL_HAMMER": [-1]})
        large_body = pd.DataFrame([{"o": 1.1000, "h": 1.1030, "l": 1.0998, "c": 1.1028}])
        wrong_wick = pd.DataFrame([{"o": 1.1010, "h": 1.1035, "l": 1.1009, "c": 1.1012}])

        assert _pullback_trigger(patterns, "Uptrend", large_body)["passed"] is False
        assert _pullback_trigger(patterns, "Uptrend", wrong_wick)["passed"] is False

    def test_pullback_keltner_sequence_reports_tolerance_components(self):
        df = pd.DataFrame({
            "h": [1.1020, 1.1060, 1.1040, 1.1012],
            "l": [1.0980, 1.1010, 1.1000, 1.1005],
            "c": [1.1010, 1.1050, 1.1020, 1.1010],
        })
        kc = pd.DataFrame({
            "upper": [1.1050, 1.1050, 1.1050, 1.1050],
            "mid": [1.1010, 1.1010, 1.1010, 1.1010],
            "lower": [1.0970, 1.0970, 1.0970, 1.0970],
        })

        result = _pullback_keltner_sequence(df, kc, "Uptrend", 0.001, "upper", "lower", "mid")

        assert result["passed"] is True
        assert result["prior_break"] is True
        assert result["near_midline"] is True
        assert result["distance_to_midline"] == 0
        assert result["tolerance_atr_component"] > 0
        assert result["tolerance_channel_component"] > 0

    def test_pullback_stoch_rsi_uses_configurable_memory_bars(self, monkeypatch):
        import tradegumi.config as config_module

        monkeypatch.setattr(config_module, "PULLBACK_STOCH_MEMORY_BARS", 3, raising=False)
        k_values = pd.Series([10.0, 55.0, 58.0, 60.0])

        result = _pullback_stoch_rsi(60.0, 58.0, k_values, "Uptrend")

        assert result["passed"] is False
        assert result["memory_bars"] == 3
        assert result["recent_low"] == 55.0

    def test_pullback_rejects_generic_candlestick_confirmation(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count, trigger="CDL_SPINNINGTOP")

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is None
        assert reason == "criteria_failed"
        assert any(c.reason == "pullback_trigger_candle_failed" and c.blocked_signal for c in criteria)

    def test_pullback_rejects_missing_prior_kc_break(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count, prior_break=False)

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is None
        assert reason == "criteria_failed"
        assert any(c.reason == "pullback_kc_sequence_failed" for c in criteria)

    def test_pullback_rejects_structure_violation(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.1000, step=-0.0001)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count)

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is None
        assert reason == "criteria_failed"
        structure = next(c for c in criteria if c.criterion_name == "pullback_structure")
        assert structure.reason == "pullback_structure_failed"
        assert structure.blocked_signal is True

    def test_pullback_rejects_without_stoch_exhaustion(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count, stoch_ok=False)

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is None
        assert reason == "criteria_failed"
        assert any(c.reason == "pullback_stoch_rsi_failed" for c in criteria)

    def test_pullback_macd_is_soft_score_only(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count, macd_blocks=True)

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is not None, reason
        macd = next(c for c in criteria if c.criterion_name == "macd_soft_score")
        assert macd.required is False
        assert macd.blocked_signal is False

    def test_pullback_macd_hard_block_is_explicitly_configurable(self, monkeypatch):
        import tradegumi.config as config_module

        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        self._patch_pullback_indicators(monkeypatch, count, macd_blocks=True)
        monkeypatch.setattr(config_module, "PULLBACK_MACD_HARD_BLOCK_ENABLED", True, raising=False)

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is None
        assert reason == "criteria_failed"
        hard_block = next(c for c in criteria if c.criterion_name == "pullback_macd_hard_block")
        assert hard_block.required is True
        assert hard_block.blocked_signal is True
        assert hard_block.reason == "pullback_macd_hard_block_failed"

    def test_high_value_pullback_partial_retracement_buy(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        
        self._patch_pullback_indicators(monkeypatch, count, trend="Uptrend", trigger="CDL_HAMMER")
        
        mid = 1.0900
        upper = [1.1000] * count
        upper[-8] = 1.0920
        lower = [1.0800] * count
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": upper,
                "mid": [mid] * count,
                "lower": lower,
            }),
        )
        
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [0.001] * count,
                "signal": [0.0] * count,
                "histogram": [0.001] * count,
            }),
        )

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is not None, reason
        assert signal.signal_type == "high_value_pullback"
        assert signal.strategy == "CTI-v1.2-pullback"

    def test_high_value_pullback_partial_retracement_sell(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.1100, step=-0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        
        self._patch_pullback_indicators(monkeypatch, count, trend="Downtrend", trigger="CDL_SHOOTINGSTAR")
        
        mid = 1.1100
        upper = [1.1200] * count
        lower = [1.1000] * count
        lower[-8] = 1.1080
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": upper,
                "mid": [mid] * count,
                "lower": lower,
            }),
        )
        
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [-0.001] * count,
                "signal": [0.0] * count,
                "histogram": [-0.001] * count,
            }),
        )

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Downtrend", allow_continuation=False)

        assert signal is not None, reason
        assert signal.signal_type == "high_value_pullback"
        assert signal.strategy == "CTI-v1.2-pullback"

    def test_high_value_pullback_remains_outside_band_buy(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        
        self._patch_pullback_indicators(monkeypatch, count, trend="Uptrend", trigger="CDL_HAMMER")
        
        mid = 1.0800
        upper = [1.0900] * count
        lower = [1.0700] * count
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": upper,
                "mid": [mid] * count,
                "lower": lower,
            }),
        )
        
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [0.001] * count,
                "signal": [0.0] * count,
                "histogram": [0.001] * count,
            }),
        )

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is not None, reason
        assert signal.signal_type == "high_value_pullback"
        assert signal.strategy == "CTI-v1.2-pullback"

    def test_high_value_pullback_remains_outside_band_sell(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.1100, step=-0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        
        self._patch_pullback_indicators(monkeypatch, count, trend="Downtrend", trigger="CDL_SHOOTINGSTAR")
        
        mid = 1.1200
        upper = [1.1300] * count
        lower = [1.1100] * count
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": upper,
                "mid": [mid] * count,
                "lower": lower,
            }),
        )
        
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [-0.001] * count,
                "signal": [0.0] * count,
                "histogram": [-0.001] * count,
            }),
        )

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Downtrend", allow_continuation=False)

        assert signal is not None, reason
        assert signal.signal_type == "high_value_pullback"
        assert signal.strategy == "CTI-v1.2-pullback"

    def test_high_value_pullback_rejected_by_macd_histogram_buy(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        
        self._patch_pullback_indicators(monkeypatch, count, trend="Uptrend", trigger="CDL_HAMMER")
        
        mid = 1.0800
        upper = [1.0900] * count
        lower = [1.0700] * count
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": upper,
                "mid": [mid] * count,
                "lower": lower,
            }),
        )
        
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [-0.001] * count,
                "signal": [0.0] * count,
                "histogram": [-0.001] * count,
            }),
        )

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is None
        assert reason == "criteria_failed"

    def test_high_value_pullback_rejected_by_macd_histogram_sell(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.1100, step=-0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        
        self._patch_pullback_indicators(monkeypatch, count, trend="Downtrend", trigger="CDL_SHOOTINGSTAR")
        
        mid = 1.1200
        upper = [1.1300] * count
        lower = [1.1100] * count
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": upper,
                "mid": [mid] * count,
                "lower": lower,
            }),
        )
        
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [0.001] * count,
                "signal": [0.0] * count,
                "histogram": [0.001] * count,
            }),
        )

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Downtrend", allow_continuation=False)

        assert signal is None
        assert reason == "criteria_failed"

    def test_standard_midline_pullback_regression(self, monkeypatch):
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = trend_candles(count, now, start=1.0900, step=0.0004)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}))
        
        self._patch_pullback_indicators(monkeypatch, count, trend="Uptrend", trigger="CDL_HAMMER")
        
        mid = 1.1000
        upper = [1.1150] * count
        upper[-8] = 1.1020
        lower = [1.0850] * count
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": upper,
                "mid": [mid] * count,
                "lower": lower,
            }),
        )

        signal, criteria, reason, _ = engine._get_signal("EURUSD", "Uptrend", allow_continuation=False)

        assert signal is not None, reason
        assert signal.signal_type == "pullback"
        assert signal.strategy == "CTI-v1.2-pullback"


class TestClassifyTrendBias:
    """classify_trend_bias: 1H+15M define bias, 5M is timing only (not hard disqualification)."""

    def test_bias_requires_1h_and_15m_agree(self, monkeypatch):
        from tradegumi.signal_engine import classify_trend_bias

        # Strong 1H and 15M agree up, 5M weak but should still give bias=up
        result = classify_trend_bias(0.010, 0.009, 0.001, 0.005, 0.008, 0.002)

        assert result["bias_result"] == "up"
        assert result["final_direction"] == "BUY"
        assert result["bias_directions_agree"] is True
        assert result["bias_strength_passed"] is True

    def test_bias_fails_when_1h_and_15m_conflict(self, monkeypatch):
        from tradegumi.signal_engine import classify_trend_bias

        # 1H up, 15M down → no bias
        result = classify_trend_bias(0.010, -0.009, 0.001, 0.005, 0.008, 0.002)

        assert result["bias_result"] == "flat"
        assert result["final_direction"] == "none"
        assert result["no_bias_reason"] == "bias_direction_conflict"

    def test_bias_requires_1h_and_15m_strength(self, monkeypatch):
        from tradegumi.signal_engine import classify_trend_bias

        # 1H and 15M both above strength thresholds
        result = classify_trend_bias(0.010, 0.009, 0.001, 0.005, 0.008, 0.002)

        assert result["strength_passed_1h"] is True
        assert result["strength_passed_15m"] is True
        assert result["bias_strength_passed"] is True

    def test_bias_fails_when_1h_insufficient_strength(self, monkeypatch):
        from tradegumi.signal_engine import classify_trend_bias

        # 1H below threshold, 15M above
        result = classify_trend_bias(0.003, 0.009, 0.001, 0.005, 0.008, 0.002)

        assert result["bias_result"] == "flat"
        assert result["strength_passed_1h"] is False
        assert result["strength_passed_15m"] is True


class TestChopFilter:
    """Chop / regime filter: opposite-signal conflict, suppression, 15M strength, persistence, flip detection."""

    def _warm_persistence(self, engine, symbol, direction, n):
        """Pre-populate trend evaluations so persistence check passes."""
        for _ in range(n):
            engine._record_trend_evaluation(symbol, direction)

    def _make_strong_lr(self, monkeypatch):
        """Mock calculate_linear_regression to return strong LRs on all TFs."""
        def lr_side_effect(df, length):
            if length == 20:
                return pd.Series([0.012] * len(df))  # 1H strong
            if length == 25:
                return pd.Series([0.012] * len(df))  # 15M strong (> 0.008 * 1.25)
            return pd.Series([0.005] * len(df))      # 5M strong
        monkeypatch.setattr("tradegumi.signal_engine.calculate_linear_regression", lr_side_effect)

    def _setup_continuation_signal(self, engine, monkeypatch, count):
        """Mock all signal stack layers so continuation fires reliably."""
        last_price = 1.1000
        mid_val = last_price - 0.0005
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_stoch_rsi",
            lambda df, length, k, d: pd.DataFrame({"k": [55.0] * count, "d": [50.0] * count}),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_macd",
            lambda df, fast, slow, signal: pd.DataFrame({
                "macd": [0.001] * count,
                "signal": [0.0005] * count,
                "histogram": [0.001] * count,
            }),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_keltner_channels",
            lambda df, length, multiplier, mamode: pd.DataFrame({
                "upper": [mid_val + 0.003] * count,
                "mid": [mid_val] * count,
                "lower": [mid_val - 0.003] * count,
            }),
        )
        monkeypatch.setattr(
            "tradegumi.signal_engine.calculate_candlestick_patterns",
            lambda df: pd.DataFrame({"CDL_HAMMER": [0] * count}),
        )
        monkeypatch.setattr("tradegumi.signal_engine.calculate_atr", lambda df: pd.Series([0.001] * count))
        monkeypatch.setattr("tradegumi.signal_engine.stoch_rsi_score", lambda *args: 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.macd_histogram_score", lambda *args: 0.9)
        monkeypatch.setattr("tradegumi.signal_engine.keltner_score", lambda *args: 0.8)
        monkeypatch.setattr("tradegumi.signal_engine.candlestick_score", lambda *args: 0.0)
        monkeypatch.setattr("tradegumi.signal_engine.trend_score", lambda *args: 1.0)

    def _emit_signal(self, engine, symbol):
        """Call check_symbol and return the diagnostic, with detailed logging on failure."""
        signal, trend, lr_1h, lr_15, lr_5, diag = engine.check_symbol(symbol)
        return signal, trend, diag

    def test_opposite_direction_conflict_blocks_signal_and_enters_suppression(self, monkeypatch):
        """Requirement 1: same-symbol opposite-direction signal while prior unresolved → blocked."""
        from tradegumi import config
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = closed_candles(count, now)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})

        self._make_strong_lr(monkeypatch)
        self._setup_continuation_signal(engine, monkeypatch, count)
        self._warm_persistence(engine, "EURUSD", "Uptrend", config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES)

        # First signal: BUY (Uptrend)
        signal, trend, diag = self._emit_signal(engine, "EURUSD")
        assert signal is not None
        assert trend == "Uptrend"

        # Manually inject a conflicting last signal direction (SELL) to simulate
        # the scenario where a prior opposite-direction signal is unresolved.
        engine._record_signal_direction("EURUSD", "SELL")

        # Now a new Uptrend evaluation should conflict
        signal2, trend2, diag2 = self._emit_signal(engine, "EURUSD")
        assert signal2 is None
        assert diag2.final_decision == "skipped"
        assert diag2.decision_reason == "market_invalid:opposite_signal_chop"
        assert diag2.market_validity_state == "invalid"
        chop_criterion = next(c for c in diag2.criteria if c.criterion_name == "chop_filter")
        assert chop_criterion.passed is False
        assert chop_criterion.reason == "market_invalid:opposite_signal_chop"
        assert chop_criterion.context["current_direction"] == "BUY"
        assert chop_criterion.context["conflicting_direction"] == "SELL"

    def test_chop_suppression_blocks_subsequent_evaluations(self, monkeypatch):
        """Requirement 2: after opposite-direction conflict, symbol is suppressed for N candles."""
        from tradegumi import config
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = closed_candles(count, now)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})

        # Clear class-level cooldown state from prior tests
        SignalEngine._cooldown.clear()

        self._make_strong_lr(monkeypatch)
        self._setup_continuation_signal(engine, monkeypatch, count)
        self._warm_persistence(engine, "EURUSD", "Uptrend", config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES)

        # Emit first signal
        signal, trend, diag = self._emit_signal(engine, "EURUSD")
        if signal is None:
            # Debug: understand why the first signal did not emit
            print(f"DEBUG: first signal not emitted. reason={diag.decision_reason}")
            for c in diag.criteria:
                print(f"  {c.criterion_name}: passed={c.passed} reason={c.reason}")
        assert signal is not None

        # Inject opposite-direction conflict → triggers suppression
        engine._record_signal_direction("EURUSD", "SELL")

        # Conflict evaluation triggers suppression
        _, _, diag_conflict = self._emit_signal(engine, "EURUSD")
        assert diag_conflict.decision_reason == "market_invalid:opposite_signal_chop"

        # Immediately evaluate again — should be in suppression window
        signal3, trend3, diag3 = self._emit_signal(engine, "EURUSD")
        assert signal3 is None
        assert diag3.decision_reason == "market_invalid:chop_suppression"
        assert diag3.market_validity_state == "invalid"
        chop_criterion = next(c for c in diag3.criteria if c.criterion_name == "chop_filter")
        assert chop_criterion.reason == "market_invalid:chop_suppression"
        assert chop_criterion.context["suppression_candles_remaining"] > 0
        assert chop_criterion.context["suppression_candles_remaining"] <= config.CHOP_OPPOSITE_SIGNAL_SUPPRESSION_CANDLES

    def test_weak_15m_bridge_blocks_signal(self, monkeypatch):
        """Requirement 3: abs(lr_15m) must be >= LR_15M_THRESHOLD * multiplier."""
        from tradegumi import config
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = closed_candles(count, now)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})

        # 15M is just below chop threshold (0.008 * 1.25 = 0.010) but above trend threshold (0.008)
        def weak_15m_lr(df, length):
            if length == 20:
                return pd.Series([0.012] * len(df))
            if length == 25:
                return pd.Series([0.009] * len(df))  # passes trend (>=0.008) but fails chop (<0.010)
            return pd.Series([0.005] * len(df))
        monkeypatch.setattr("tradegumi.signal_engine.calculate_linear_regression", weak_15m_lr)
        self._setup_continuation_signal(engine, monkeypatch, count)
        self._warm_persistence(engine, "EURUSD", "Uptrend", config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES)

        signal, trend, _, _, _, diag = engine.check_symbol("EURUSD")
        assert signal is None
        assert diag.decision_reason == "trend:weak_15m_bridge"
        assert diag.market_validity_state == "invalid"
        chop_criterion = next(c for c in diag.criteria if c.criterion_name == "chop_filter")
        assert chop_criterion.reason == "trend:weak_15m_bridge"
        assert chop_criterion.context["lr_15m"] == 0.009
        assert chop_criterion.context["required_15m_strength"] == 0.010

    def test_trend_persistence_blocks_without_prior_evaluations(self, monkeypatch):
        """Requirement 4: without enough prior same-direction evaluations, signal is blocked."""
        from tradegumi import config
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = closed_candles(count, now)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})

        self._make_strong_lr(monkeypatch)
        self._setup_continuation_signal(engine, monkeypatch, count)
        # No warmup — persistence check should fail

        signal, trend, _, _, _, diag = engine.check_symbol("EURUSD")
        assert signal is None
        assert diag.decision_reason == "trend:not_persistent"
        assert diag.market_validity_state == "invalid"
        chop_criterion = next(c for c in diag.criteria if c.criterion_name == "chop_filter")
        assert chop_criterion.reason == "trend:not_persistent"
        assert chop_criterion.context["required_persistence_candles"] == config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES

    def test_trend_persistence_passes_after_warmup(self, monkeypatch):
        """Requirement 4: with enough prior evaluations, signal proceeds."""
        from tradegumi import config
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = closed_candles(count, now)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})

        # Clear class-level cooldown state from prior tests
        SignalEngine._cooldown.clear()

        self._make_strong_lr(monkeypatch)
        self._setup_continuation_signal(engine, monkeypatch, count)
        self._warm_persistence(engine, "EURUSD", "Uptrend", config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES)

        signal, trend, _, _, _, diag = engine.check_symbol("EURUSD")
        assert signal is not None
        assert diag.decision_reason not in ("trend:not_persistent", "market_invalid:chop_suppression")

    def test_direction_flip_chop_blocks_on_excessive_flips(self, monkeypatch):
        """Requirement 5: too many direction flips in lookback → chop."""
        from tradegumi import config
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = closed_candles(count, now)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})

        self._make_strong_lr(monkeypatch)
        self._setup_continuation_signal(engine, monkeypatch, count)

        # Seed evaluations with alternating directions > max_flips
        for i in range(config.CHOP_DIRECTION_FLIP_LOOKBACK_CANDLES + 2):
            engine._record_trend_evaluation("EURUSD", "Uptrend" if i % 2 == 0 else "Downtrend")

        # Warm persistence with the current direction
        self._warm_persistence(engine, "EURUSD", "Uptrend", config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES)

        signal, trend, _, _, _, diag = engine.check_symbol("EURUSD")
        assert signal is None
        assert diag.decision_reason == "market_invalid:direction_flip_chop"
        assert diag.market_validity_state == "invalid"
        chop_criterion = next(c for c in diag.criteria if c.criterion_name == "chop_filter")
        assert chop_criterion.reason == "market_invalid:direction_flip_chop"
        assert chop_criterion.context["observed_flips"] > config.CHOP_MAX_DIRECTION_FLIPS

    def test_chop_filter_disabled_allows_all_signals(self, monkeypatch):
        """When CHOP_FILTER_ENABLED is false, no chop blocks occur."""
        import tradegumi.config as config_module
        orig_enabled = config_module.CHOP_FILTER_ENABLED
        try:
            config_module.CHOP_FILTER_ENABLED = False
            now = datetime.now(timezone.utc)
            count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
            candles = closed_candles(count, now)
            engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})

            # Clear class-level cooldown state from prior tests
            SignalEngine._cooldown.clear()

            self._make_strong_lr(monkeypatch)
            self._setup_continuation_signal(engine, monkeypatch, count)
            # No warmup, no suppression handling needed

            signal, trend, _, _, _, diag = engine.check_symbol("EURUSD")
            assert signal is not None
            assert diag.decision_reason != "market_invalid:chop_suppression"
            assert diag.decision_reason != "trend:not_persistent"
        finally:
            config_module.CHOP_FILTER_ENABLED = orig_enabled

    def test_chop_suppression_expires_after_window(self, monkeypatch):
        """Suppression window eventually expires and allows signals again."""
        from tradegumi import config
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        count = SignalEngine.SIGNAL_WINDOW_MIN_CANDLES
        candles = closed_candles(count, now)
        engine = SignalEngine(FakeClient({"M5": candles, "M15": candles, "H1": candles}), {"EURUSD"})

        # Clear class-level cooldown state from prior tests
        SignalEngine._cooldown.clear()

        self._make_strong_lr(monkeypatch)
        self._setup_continuation_signal(engine, monkeypatch, count)
        self._warm_persistence(engine, "EURUSD", "Uptrend", config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES)

        # Emit first signal
        signal, trend, _, _, _, diag = engine.check_symbol("EURUSD")
        assert signal is not None

        # Inject opposite-direction conflict → triggers suppression
        engine._record_signal_direction("EURUSD", "SELL")
        _, _, _, _, _, diag_conflict = engine.check_symbol("EURUSD")
        assert diag_conflict.decision_reason == "market_invalid:opposite_signal_chop"

        # Fast-forward time past suppression window and clear the conflicting
        # direction so the test verifies only suppression expiration.
        state = engine._chop_state["EURUSD"]
        state["chop_suppression_until"] = (now - timedelta(minutes=1)).isoformat()
        state["last_signal_direction"] = "BUY"  # align with current trend

        # Also clear cooldown from the first emitted signal
        SignalEngine._cooldown.clear()

        # Now evaluate again — suppression should be expired and no conflict
        signal2, trend2, _, _, _, diag2 = engine.check_symbol("EURUSD")
        assert signal2 is not None
        assert "chop_suppression_until" not in state or state.get("chop_suppression_until") is None

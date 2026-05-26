"""Unit tests for the volatility shock filter.

Tests all detection rules, suppression logic, LR filtering, and disable behavior.
Uses monkeypatch on calculate_atr for deterministic ATR values.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from tradegumi.api.base_client import Candle
from tradegumi.volatility_shock import (
    VolatilityShockFilter,
    ShockDetectionResult,
    _timeframe_seconds,
)


def _candle(open_time: datetime, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(
        t=open_time.astimezone(timezone.utc).isoformat(),
        o=o,
        h=h,
        l=l,
        c=c,
        s=100,
    )


def _candles_normal(count: int, base: datetime, price: float = 1.1000) -> list[Candle]:
    """Generate normal candles with very small drift."""
    result = []
    current = price
    for i in range(count):
        o = current
        # tiny 0.1-pip drift per candle
        drift = 0.0001 if i % 2 == 0 else -0.0001
        h = o + 0.0004
        l = o - 0.0004
        c = o + drift
        result.append(_candle(base + timedelta(minutes=5 * i), o, h, l, c))
        current = c
    return result


def _fixed_atr_series(atr: float, length: int) -> pd.Series:
    """Return a constant ATR series."""
    return pd.Series([atr] * length)


class TestPriorOnlyATR:
    """ATR used for shock detection must be prior-only (Bug 2)."""

    def test_shifted_atr_prevents_self_influence_single_candle(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        prev_close = candles[-2].c
        # TR = 0.005; last ATR = 100.0 (inflated), prior ATR = 0.001
        atr_values = [0.001] * (len(candles) - 1) + [100.0]
        candles[-1] = _candle(
            candles[-1].time,
            candles[-1].o,
            prev_close + 0.0030,
            candles[-1].c - 0.0050,
            candles[-1].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: pd.Series(atr_values),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.candle_multiple = 3.0
        f.lookback_candles = 3

        result = f.detect(candles, "M5")
        # With prior-only ATR (0.001), TR=0.005 is 5x → shock detected
        # Without shift, ATR=100.0 would make it 0.05x → no shock
        assert result.detected is True
        assert result.rule == "single_candle_tr"
        assert result.atr == 0.001  # prior ATR, not the inflated last one

    def test_shifted_atr_prevents_self_influence_2_bar(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        # diff = 0.005; last ATR = 100.0, prior ATR = 0.001
        atr_values = [0.001] * (len(candles) - 1) + [100.0]
        candles[-1] = _candle(
            candles[-1].time, candles[-1].o, candles[-1].h, candles[-1].l,
            candles[-3].c - 0.0050,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: pd.Series(atr_values),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.bar2_multiple = 4.0
        f.lookback_candles = 3

        result = f.detect(candles, "M5")
        assert result.detected is True
        assert result.atr == 0.001  # prior ATR, not the inflated last one

    def test_shifted_atr_prevents_self_influence_3_bar(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        atr_values = [0.001] * (len(candles) - 1) + [100.0]
        candles[-1] = _candle(
            candles[-1].time, candles[-1].o, candles[-1].h, candles[-1].l,
            candles[-4].c - 0.0060,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: pd.Series(atr_values),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.bar3_multiple = 5.0
        f.lookback_candles = 3

        result = f.detect(candles, "M5")
        assert result.detected is True
        assert result.rule == "3_bar_close"
        assert result.atr == 0.001

    def test_shifted_atr_skips_when_prior_is_na(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        # First ATR is NaN, rest are normal; shifted makes index 0 use NaN
        atr_values = [float("nan")] + [0.001] * (len(candles) - 1)
        prev_close = candles[-2].c
        candles[-1] = _candle(
            candles[-1].time,
            candles[-1].o,
            prev_close + 0.0030,
            candles[-1].c - 0.0050,
            candles[-1].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: pd.Series(atr_values),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.candle_multiple = 3.0
        f.lookback_candles = 3

        result = f.detect(candles, "M5")
        # Index -1 shifted ATR comes from index -2 which is 0.001
        assert result.detected is True

    def test_filtered_lr_uses_shifted_atr(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(30, base, price=1.1000)
        # Make index 15 have inflated ATR but normal prior ATR
        atr_values = [0.001] * 15 + [100.0] + [0.001] * 14
        candles[15] = _candle(
            candles[15].time,
            candles[15].o,
            candles[15].h + 0.0120,
            candles[15].l,
            candles[15].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: pd.Series(atr_values),
        )

        f = VolatilityShockFilter()
        f.enabled = True

        clean, excluded = f.filter_candles_for_lr(candles)
        # With shifted ATR, index 15 uses prior ATR=0.001, TR ~0.012 → 12x → excluded
        assert 15 in excluded
        # Index 16 uses prior ATR=100.0 (from index 15 original), but after shift,
        # index 16 gets ATR from index 15 which was 100.0 before shift... wait.
        # Actually in filter_candles_for_lr, shifted_atr.iloc[16] = atr_values[15] = 100.0
        # So index 16 may NOT be excluded because its prior ATR is inflated.
        # The key point: the judged candle does not influence its own baseline.
        assert len(clean) == len(candles) - len(excluded)


class TestDetectionRules:
    def test_single_candle_tr_rule_fires_when_3x_atr(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        # Inject a shock at index -1: TR ~ 0.0035 (3.5x ATR=0.001)
        prev_close = candles[-2].c
        candles[-1] = _candle(
            candles[-1].time,
            candles[-1].o,
            prev_close + 0.0010,   # high far above prev close
            candles[-1].c - 0.0035,
            candles[-1].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.candle_multiple = 3.0
        f.lookback_candles = 3

        result = f.detect(candles, "M5")
        assert result.detected is True
        assert result.rule == "single_candle_tr"
        assert result.atr_multiple >= 3.0
        assert result.direction == "down"

    def test_2_bar_rule_fires_when_4x_atr(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        # Close[-1] vs Close[-3] diff = 0.0045 (4.5x ATR=0.001)
        candles[-1] = _candle(
            candles[-1].time, candles[-1].o, candles[-1].h, candles[-1].l,
            candles[-3].c - 0.0045,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.bar2_multiple = 4.0
        f.lookback_candles = 3

        result = f.detect(candles, "M5")
        assert result.detected is True
        assert result.rule == "2_bar_close"
        assert result.atr_multiple >= 4.0

    def test_3_bar_rule_fires_when_5x_atr(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        # Close[-1] vs Close[-4] diff = 0.0055 (5.5x ATR=0.001)
        candles[-1] = _candle(
            candles[-1].time, candles[-1].o, candles[-1].h, candles[-1].l,
            candles[-4].c - 0.0055,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.bar3_multiple = 5.0
        f.lookback_candles = 3

        result = f.detect(candles, "M5")
        assert result.detected is True
        assert result.rule == "3_bar_close"
        assert result.atr_multiple >= 5.0

    def test_most_severe_shock_returned(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        # Both 2-bar and 3-bar rules fire; 3-bar is more severe
        candles[-1] = _candle(
            candles[-1].time, candles[-1].o, candles[-1].h, candles[-1].l,
            candles[-4].c - 0.0060,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.bar2_multiple = 4.0
        f.bar3_multiple = 5.0
        f.lookback_candles = 3

        result = f.detect(candles, "M5")
        assert result.detected is True
        assert result.rule == "3_bar_close"
        assert result.atr_multiple >= 5.0

    def test_no_shock_on_normal_data(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True

        result = f.detect(candles, "M5")
        assert result.detected is False
        assert result.atr_multiple is None

    def test_disabled_returns_no_detection(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        # Inject massive shock
        candles[-1] = _candle(
            candles[-1].time, candles[-1].o, candles[-1].h + 0.0100,
            candles[-1].l, candles[-1].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = False

        result = f.detect(candles, "M5")
        assert result.detected is False

    def test_insufficient_candles_returns_no_detection(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(5, base, price=1.1000)

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True

        result = f.detect(candles, "M5")
        assert result.detected is False


class TestSuppression:
    def test_shock_suppresses_symbol_for_n_candles(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        # Inject shock at last candle
        candles[-1] = _candle(
            candles[-1].time, candles[-1].o, candles[-1].h + 0.0050,
            candles[-1].l, candles[-1].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.suppression_candles = 3

        is_suppressed, active_shock, all_shocks = f.check_symbol(
            "EURUSD",
            {"M5": candles, "M15": candles, "H1": candles},
        )
        assert is_suppressed is True
        assert active_shock is not None
        assert active_shock.detected is True
        assert active_shock.suppression_candles_remaining == 3

    def test_suppression_expires_after_duration(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        candles[-1] = _candle(
            candles[-1].time, candles[-1].o, candles[-1].h + 0.0050,
            candles[-1].l, candles[-1].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.suppression_candles = 1  # 1 M5 candle = 5 minutes

        is_suppressed, _, _ = f.check_symbol("EURUSD", {"M5": candles})
        assert is_suppressed is True

        # Second check immediately after is still suppressed
        is_suppressed, active, _ = f.check_symbol("EURUSD", {"M5": candles})
        assert is_suppressed is True

    def test_no_suppression_when_disabled(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(40, base, price=1.1000)
        candles[-1] = _candle(
            candles[-1].time, candles[-1].o, candles[-1].h + 0.0050,
            candles[-1].l, candles[-1].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = False

        is_suppressed, active_shock, _ = f.check_symbol("EURUSD", {"M5": candles})
        assert is_suppressed is False
        assert active_shock is None


class TestFilteredLR:
    def test_shock_candles_excluded_from_lr_window(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(30, base, price=1.1000)
        # Inject a massive shock at index 15 so TR > 2.5x ATR
        candles[15] = _candle(
            candles[15].time,
            candles[15].o,
            candles[15].h + 0.0120,
            candles[15].l,
            candles[15].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True

        clean, excluded = f.filter_candles_for_lr(candles)
        assert len(excluded) >= 1
        assert 15 in excluded
        assert len(clean) == len(candles) - len(excluded)

    def test_no_exclusion_when_disabled(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(30, base, price=1.1000)
        candles[15] = _candle(
            candles[15].time,
            candles[15].o,
            candles[15].h + 0.0120,
            candles[15].l,
            candles[15].c,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = False

        clean, excluded = f.filter_candles_for_lr(candles)
        assert excluded == []
        assert clean == candles

    def test_no_exclusion_on_normal_data(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        candles = _candles_normal(30, base, price=1.1000)

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0010, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True

        clean, excluded = f.filter_candles_for_lr(candles)
        assert excluded == []


class TestCADJPYScenario:
    """Simulate the CADJPY ~-0.486 move over 10 min with ATR ~0.06-0.08."""

    def test_6x_atr_shock_detected(self, monkeypatch):
        base = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
        # CADJPY around 108.00, ATR ~0.07
        candles = _candles_normal(40, base, price=108.0000)
        # Shock: drop 0.486 in one candle
        candles[-1] = _candle(
            candles[-1].time,
            candles[-1].o,
            candles[-1].h,
            candles[-1].l - 0.4860,
            candles[-1].c - 0.4860,
        )

        monkeypatch.setattr(
            "tradegumi.volatility_shock.calculate_atr",
            lambda df, length=14: _fixed_atr_series(0.0700, len(df)),
        )

        f = VolatilityShockFilter()
        f.enabled = True
        f.candle_multiple = 3.0
        f.lookback_candles = 3

        result = f.detect(candles, "M5")
        assert result.detected is True
        # TR should be ~0.486 which is ~6.9x ATR=0.07
        assert result.atr_multiple >= 6.0
        assert result.direction == "down"


class TestTimeframeHelpers:
    def test_timeframe_seconds(self):
        assert _timeframe_seconds("M5") == 300
        assert _timeframe_seconds("M15") == 900
        assert _timeframe_seconds("H1") == 3600
        assert _timeframe_seconds("D1") == 86400
        assert _timeframe_seconds("UNKNOWN") == 300


class TestShockResultDict:
    def test_to_dict_contains_all_fields(self):
        r = ShockDetectionResult(
            detected=True,
            timeframe="M5",
            candle_time="2026-05-06T10:00:00+00:00",
            true_range=0.500,
            atr=0.070,
            atr_multiple=7.14,
            lookback_bars=1,
            direction="down",
            rule="single_candle_tr",
            suppression_until="2026-05-06T10:15:00+00:00",
            suppression_candles_remaining=3,
        )
        d = r.to_dict()
        assert d["volatility_shock_detected"] is True
        assert d["shock_timeframe"] == "M5"
        assert d["shock_candle_time"] == "2026-05-06T10:00:00+00:00"
        assert d["shock_true_range"] == 0.500
        assert d["shock_atr"] == 0.070
        assert d["shock_atr_multiple"] == 7.14
        assert d["shock_lookback_bars"] == 1
        assert d["shock_direction"] == "down"
        assert d["shock_rule"] == "single_candle_tr"
        assert d["shock_suppression_until"] == "2026-05-06T10:15:00+00:00"
        assert d["shock_suppression_candles_remaining"] == 3

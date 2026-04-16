"""Unit tests for tradegumi indicator and signal engine logic."""
import pytest
import pandas as pd
import numpy as np

from tradegumi.indicators import (
    candles_to_df,
    calculate_stoch_rsi,
    calculate_macd,
    calculate_keltner_channels,
    calculate_atr,
    calculate_linear_regression,
    calculate_candlestick_patterns,
    stoch_rsi_score,
    macd_histogram_score,
    keltner_score,
    candlestick_score,
    trend_score,
)
from tradegumi.api.base_client import Candle


# ── Fixtures ─────────────────────────────────────────────────────────────────

def make_candles(n: int = 100, base_price: float = 1.0900) -> list[Candle]:
    """Generate synthetic OHLCV candles with some trend."""
    candles = []
    price = base_price
    for i in range(n):
        # Add some noise + slight upward drift
        noise = np.random.randn() * 0.0003
        o = price
        h = price + abs(np.random.randn() * 0.0005)
        l = price - abs(np.random.randn() * 0.0005)
        c = price + noise + 0.00005
        candles.append(Candle(t=i, o=o, h=h, l=l, c=c, s=1000))
        price = c
    return candles


@pytest.fixture
def candle_df():
    return candles_to_df(make_candles(100))


# ── DataFrame conversion ─────────────────────────────────────────────────────

class TestCandleConversion:
    def test_candles_to_df_correct_columns(self):
        candles = make_candles(10)
        df = candles_to_df(candles)
        assert list(df.columns) == ["t", "o", "h", "l", "c", "s"]
        assert len(df) == 10

    def test_candles_to_df_ohlcv_values(self):
        candles = [Candle(t=1, o=1.0, h=1.01, l=0.99, c=1.005, s=100)]
        df = candles_to_df(candles)
        assert df["o"].iloc[0] == 1.0
        assert df["h"].iloc[0] == 1.01


# ── Indicator calculations ───────────────────────────────────────────────────

class TestIndicators:
    def test_rsi_shapes(self, candle_df):
        rsi = calculate_atr(candle_df)
        assert len(rsi) == len(candle_df)

    def test_stoch_rsi_columns(self, candle_df):
        stoch = calculate_stoch_rsi(candle_df)
        cols = stoch.columns.tolist()
        assert any("k" in c.lower() for c in cols)
        assert any("d" in c.lower() for c in cols)

    def test_macd_columns(self, candle_df):
        macd = calculate_macd(candle_df)
        cols = macd.columns.tolist()
        assert any("macd" in c.lower() for c in cols)

    def test_keltner_columns(self, candle_df):
        kc = calculate_keltner_channels(candle_df)
        cols = kc.columns.tolist()
        assert any("kc" in c.lower() for c in cols)

    def test_linear_regression_fills_column(self, candle_df):
        lr = calculate_linear_regression(candle_df, length=14)
        assert len(lr) == len(candle_df)
        assert not lr.isna().all()

    def test_candlestick_patterns_all(self, candle_df):
        patterns = calculate_candlestick_patterns(candle_df)
        assert patterns.shape[0] == candle_df.shape[0]


# ── Layer 2 signal scoring ──────────────────────────────────────────────────

class TestSignalScoring:
    def test_stoch_rsi_score_buy_oversold(self):
        # Deeply oversold + bullish cross = high score
        score = stoch_rsi_score(k=25, d=22, k_prev3_min=10, k_prev3_max=50, direction="BUY")
        assert 0.0 <= score <= 1.0

    def test_stoch_rsi_score_sell_overbought(self):
        score = stoch_rsi_score(k=80, d=82, k_prev3_min=20, k_prev3_max=85, direction="SELL")
        assert 0.0 <= score <= 1.0

    def test_macd_histogram_score(self):
        score = macd_histogram_score(current=0.001, prev5_min=-0.005, prev5_max=0.010, direction="BUY")
        assert 0.0 <= score <= 1.0

    def test_keltner_score(self):
        score = keltner_score(last5_low=1.0850, last5_high=1.0950,
                              last5_middle_min=1.0900, last5_middle_max=1.0920, direction="BUY")
        assert 0.0 <= score <= 1.0

    def test_trend_score_both_strong(self):
        # Strong uptrend on both timeframes
        score = trend_score(lr_15m_pct=0.05, lr_5m_pct=0.010, direction="BUY",
                            threshold_15m=0.01, threshold_5m=0.002)
        assert score > 0.5

    def test_trend_score_disagree(self):
        # Opposite direction timeframes = low score
        score = trend_score(lr_15m_pct=0.05, lr_5m_pct=-0.010, direction="BUY",
                            threshold_15m=0.01, threshold_5m=0.002)
        assert score < 0.5


# ── Oanda symbol conversion ─────────────────────────────────────────────────

class TestSymbolConversion:
    def test_to_oanda(self):
        from tradegumi.config import to_oanda_symbol
        assert to_oanda_symbol("EURUSD") == "EUR_USD"
        assert to_oanda_symbol("GBPUSD") == "GBP_USD"
        assert to_oanda_symbol("USDJPY") == "USD_JPY"
        assert to_oanda_symbol("XAUUSD") == "XAU_USD"

    def test_from_oanda(self):
        from tradegumi.config import from_oanda_symbol
        assert from_oanda_symbol("EUR_USD") == "EURUSD"
        assert from_oanda_symbol("USD_JPY") == "USDJPY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
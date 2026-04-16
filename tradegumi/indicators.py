"""Technical indicator stack for TradeGumi.

Adapted from CTI_Scripts/py_scripts/trading_scripts/api/indicators.py
Pure pandas_ta — no API dependencies. Client-agnostic.
"""
import pandas as pd
import pandas_ta as ta  # noqa: F401 — used by getattr on ta.*

from tradegumi.api.base_client import Candle


# ── DataFrame helpers ─────────────────────────────────────────────────────────

def candles_to_df(candles: list[Candle]) -> pd.DataFrame:
    """Convert list of Candle to pandas DataFrame with OHLCV columns."""
    records = [{"t": c.t, "o": c.o, "h": c.h, "l": c.l, "c": c.c, "s": c.s} for c in candles]
    df = pd.DataFrame(records)
    if "s" in df.columns and df["s"].isna().all():
        df.drop(columns=["s"], inplace=True)
    return df


def validate_data(data: pd.DataFrame) -> None:
    """Validate required OHLC columns."""
    for col in ("o", "h", "l", "c"):
        if col not in data.columns:
            raise ValueError(f"Missing required column: {col}")


def prepare_data(data: pd.DataFrame) -> pd.DataFrame:
    """Rename o/h/l/c/s → open/high/low/close/volume for pandas_ta compat."""
    validate_data(data)
    return data.rename(columns={
        "o": "open", "h": "high", "l": "low", "c": "close", "s": "volume"
    })


# ── Individual Indicators ────────────────────────────────────────────────────

def calculate_rsi(data: pd.DataFrame, length: int = 14) -> pd.Series:
    """RSI."""
    return prepare_data(data).ta.rsi(length=length)


def calculate_stoch_rsi(data: pd.DataFrame, length: int = 14, k: int = 3, d: int = 3) -> pd.DataFrame:
    """Stochastic RSI. Returns DataFrame with STOCHRSIk and STOCHRSId columns."""
    df = prepare_data(data)
    result = df.ta.stochrsi(length=length, k=k, d=d)
    if isinstance(result, pd.Series):
        return pd.DataFrame({result.name: result})
    return result


def calculate_macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD. Returns DataFrame with MACD, MACD Signal, MACDh columns."""
    df = prepare_data(data)
    result = df.ta.macd(fast=fast, slow=slow, signal=signal)
    if isinstance(result, pd.Series):
        return pd.DataFrame({result.name: result})
    return result


def calculate_atr(data: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average True Range."""
    return prepare_data(data).ta.atr(length=length)


def calculate_keltner_channels(data: pd.DataFrame, length: int = 20, multiplier: float = 1.5, mamode: str = "ema") -> pd.DataFrame:
    """Keltner Channels. Returns DataFrame with KCLe, KCBe, KCUe columns."""
    df = prepare_data(data)
    result = df.ta.kc(length=length, scalar=multiplier, mamode=mamode)
    if isinstance(result, pd.Series):
        return pd.DataFrame({result.name: result})
    return result


def calculate_ema(data: pd.DataFrame, length: int = 20) -> pd.Series:
    """Exponential Moving Average."""
    return prepare_data(data).ta.ema(length=length)


def calculate_super_trend(data: pd.DataFrame, length: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Super Trend."""
    df = prepare_data(data)
    result = df.ta.supertrend(length=length, multiplier=multiplier)
    if isinstance(result, pd.Series):
        return pd.DataFrame({result.name: result})
    return result


def calculate_candlestick_patterns(data: pd.DataFrame, name: str = "all") -> pd.DataFrame:
    """Candlestick pattern detection.

    Returns DataFrame with binary columns per pattern (1=bearish, -1=bullish, 0=none).
    Set name="all" or a specific pattern string e.g. "CDL_ENGULFING".
    """
    return prepare_data(data).ta.cdl_pattern(name=name)


def calculate_linear_regression(data: pd.DataFrame, close: str = "c", length: int = 14) -> pd.Series:
    """Linear Regression slope as percentage of price."""
    df = prepare_data(data).copy()
    close_col = df["close"]
    lr_result = close_col.to_frame()
    lr_result.ta.linreg(length=length, append=True)
    col = f"LINREG_{length}"
    if col not in lr_result.columns:
        raise ValueError(f"Linear regression column {col} not found")
    diff = lr_result[col].diff()
    pct = (diff / lr_result["close"]) * 100
    return pct


# ── Layer 2: Signal Strength Scoring ─────────────────────────────────────────
# Each function returns a float in [0.0, 1.0] representing indicator strength.

def stoch_rsi_score(k: float, d: float, k_prev3_min: float, k_prev3_max: float,
                    direction: str) -> float:
    """Score StochRSI condition strength.

    Args:
        k: Current K value
        d: Current D value
        k_prev3_min: Minimum of K over prior 3 bars
        k_prev3_max: Maximum of K over prior 3 bars
        direction: "BUY" or "SELL"

    Returns:
        0.0–1.0 strength score
    """
    if direction == "BUY":
        # How far below 30 was the prev-3 min? Deeper = stronger
        oversold_depth = max(0.0, 30.0 - k_prev3_min)
        score = min(1.0, oversold_depth / 30.0)
        # Bonus if K just crossed above D
        if k > d:
            score = min(1.0, score + 0.2)
    else:  # SELL
        overbought_height = max(0.0, k_prev3_max - 70.0)
        score = min(1.0, overbought_height / 30.0)
        if k < d:
            score = min(1.0, score + 0.2)
    return round(score, 3)


def macd_histogram_score(current: float, prev5_min: float, prev5_max: float,
                          direction: str) -> float:
    """Score MACD histogram momentum.

    Args:
        current: Current MACD histogram value
        prev5_min: Min of histogram over prior 5 bars
        prev5_max: Max of histogram over prior 5 bars
        direction: "BUY" or "SELL"

    Returns:
        0.0–1.0 strength score
    """
    if direction == "BUY":
        # How far above prev-5 min is current? Bigger delta = stronger
        delta = current - prev5_min
        # Normalise: 0 delta = 0.0, 5 pip delta ≈ 1.0 (arbitrary scale)
        score = min(1.0, delta / (abs(prev5_min) * 0.05 + 1e-9))
    else:
        delta = prev5_max - current
        score = min(1.0, delta / (abs(prev5_max) * 0.05 + 1e-9))
    return round(score, 3)


def keltner_score(last5_low: float, last5_high: float,
                  last5_middle_min: float, last5_middle_max: float,
                  direction: str) -> float:
    """Score Keltner Channel position.

    Args:
        last5_low: Lowest low over last 5 bars
        last5_high: Highest high over last 5 bars
        last5_middle_min: Minimum KC middle band over last 5 bars
        last5_middle_max: Maximum KC middle band over last 5 bars
        direction: "BUY" or "SELL"

    Returns:
        0.0–1.0 strength score
    """
    if direction == "BUY":
        # Tightness: how close is last5_low to the lower middle band?
        band_range = last5_middle_min - last5_low
        score = min(1.0, band_range / (abs(last5_middle_min) * 0.02 + 1e-9))
    else:
        band_range = last5_high - last5_middle_max
        score = min(1.0, band_range / (abs(last5_middle_max) * 0.02 + 1e-9))
    return round(score, 3)


def candlestick_score(patterns: pd.DataFrame, direction: str) -> float:
    """Score candlestick confirmation.

    Args:
        patterns: DataFrame from calculate_candlestick_patterns
        direction: "BUY" or "SELL"

    Returns:
        0.0 if no pattern, 0.5 for weak pattern, 1.0 for strong pattern
    """
    if patterns.empty or patterns.iloc[-1].sum() == 0:
        return 0.0

    last = patterns.iloc[-1]
    bullish = {"CDL_HAMMER", "CDL_ENGULFING", "CDL_PIERCING", "CDL_DRAGONFLY"}
    bearish = {"CDL_SHOOTINGSTAR", "CDL_ENGULFING", "CDL_SPINNINGTOP", "CDL_HANGINGMAN"}

    strong_bull = {"CDL_ENGULFING", "CDL_HAMMER"}
    strong_bear = {"CDL_ENGULFING", "CDL_SHOOTINGSTAR"}

    if direction == "BUY":
        for col in patterns.columns:
            if col in strong_bull and last[col] == -1:
                return 1.0
            if col in bullish and last[col] == -1:
                return 0.5
    else:
        for col in patterns.columns:
            if col in strong_bear and last[col] == 1:
                return 1.0
            if col in bearish and last[col] == 1:
                return 0.5

    return 0.0


def trend_score(lr_15m_pct: float, lr_5m_pct: float, direction: str,
                threshold_15m: float = 0.01, threshold_5m: float = 0.002) -> float:
    """Score linear regression trend strength.

    Returns 0.0–1.0 based on how decisively both timeframes agree.
    """
    if direction == "BUY":
        score_15 = min(1.0, lr_15m_pct / (threshold_15m * 3))
        score_5 = min(1.0, lr_5m_pct / (threshold_5m * 3))
    else:
        score_15 = min(1.0, abs(lr_15m_pct) / (threshold_15m * 3))
        score_5 = min(1.0, abs(lr_5m_pct) / (threshold_5m * 3))
    return round((score_15 + score_5) / 2, 3)
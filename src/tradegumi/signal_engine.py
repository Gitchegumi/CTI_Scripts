"""CTI Signal Engine — trend filter + 4-layer signal stack + Layer 2 scoring.

Ported from weekday_entries.py (CTI_Scripts). No MT5, no API calls here —
just pure indicator logic driven by a client passed at construction time.
"""
import logging as log
import time
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from tradegumi import config
from tradegumi.api.base_client import ExecutionClient, Candle
from tradegumi.indicators import (
    calculate_stoch_rsi,
    calculate_macd,
    calculate_keltner_channels,
    calculate_candlestick_patterns,
    calculate_linear_regression,
    calculate_atr,
    stoch_rsi_score,
    macd_histogram_score,
    keltner_score,
    candlestick_score,
    trend_score,
    candles_to_df,
)

log = log.getLogger(__name__)


# ── Signal dataclass ─────────────────────────────────────────────────────────

@dataclass
class Signal:
    """A complete trade signal with Layer 2 quality score."""
    symbol: str
    direction: str           # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    atr: float
    lot_size: float
    risk_pct: float
    confidence: float        # Layer 2 aggregate score 0–1
    breakdown: dict          # Per-indicator scores
    trend_direction: str     # "Uptrend" or "Downtrend"
    patterns_found: list     # Candlestick patterns detected
    strategy: str = "CTI-v1"
    blocked_reason: Optional[str] = None
    # Indicator snapshot for journal
    stochrsi_k: float = 0.0
    stochrsi_d: float = 0.0
    macd_line: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    kc_upper: float = 0.0
    kc_mid: float = 0.0
    kc_lower: float = 0.0
    lr_1h: float = 0.0
    lr_15m: float = 0.0
    lr_5m: float = 0.0

    def is_blocked(self) -> bool:
        return self.blocked_reason is not None


# ── Main Engine ───────────────────────────────────────────────────────────────

class SignalEngine:
    """CTI signal generator.

    Args:
        client: ExecutionClient (Oanda or MatchTrader)
        watchlist: Optional[set[str]] — Layer 1 pre-session watchlist.
                   Symbols not in this set are skipped.
    """

    LR_1H_THRESHOLD   = 0.005   # % — 1H macro trend anchor
    LR_15M_THRESHOLD  = 0.008   # % — shortened from 0.01 (50→25 candles)
    LR_5M_THRESHOLD   = 0.002   # %
    SIGNAL_COOLDOWN_SECONDS = 300  # 5-minute cooldown per symbol/direction
    CANDLE_CLOSE_GATE = True    # Require candle close for fresh entries

    # Cooldown tracking: key = f"{symbol}:{trend}", value = last_signal_ts
    _cooldown: dict[str, float] = {}

    def __init__(self, client: ExecutionClient, watchlist: Optional[set[str]] = None):
        self.client = client
        self.watchlist = watchlist or set(config.EXECUTION_SYMBOLS)

    # ── Trend Filter ─────────────────────────────────────────────────────────

    def _get_trend(self, symbol: str) -> tuple[Optional[str], float, float, float]:
        """Linear Regression trend filter.

        All 3 TFs must agree: 1H (count=30, length=20), 15m (length=25), 5m (length=14).
        Returns (trend, lr_1h, lr_15m, lr_5) where trend is "Uptrend",
        "Downtrend", or None.
        """
        candles_1h  = self.client.get_candles(symbol, "H1",  count=30)
        candles_15m = self.client.get_candles(symbol, "M15", count=60)
        candles_5m  = self.client.get_candles(symbol, "M5",  count=24)

        df_1h = candles_to_df(candles_1h)
        df_15 = candles_to_df(candles_15m)
        df_5  = candles_to_df(candles_5m)

        lr_1h = calculate_linear_regression(df_1h, length=20).iloc[-1]
        lr_15 = calculate_linear_regression(df_15, length=25).iloc[-1]
        lr_5  = calculate_linear_regression(df_5,  length=14).iloc[-1]

        log.debug("%s LR_1h=%.4f%% LR_15m=%.4f%% LR_5m=%.4f%%", symbol, lr_1h, lr_15, lr_5)

        if lr_1h > self.LR_1H_THRESHOLD and lr_15 > self.LR_15M_THRESHOLD and lr_5 > self.LR_5M_THRESHOLD:
            return "Uptrend", lr_1h, lr_15, lr_5
        if lr_1h < -self.LR_1H_THRESHOLD and lr_15 < -self.LR_15M_THRESHOLD and lr_5 < -self.LR_5M_THRESHOLD:
            return "Downtrend", lr_1h, lr_15, lr_5
        return None, lr_1h, lr_15, lr_5

    # ── 4-Layer Signal Stack ─────────────────────────────────────────────────

    def _get_signal(self, symbol: str, trend: str) -> Optional[Signal]:
        """Run the 4-layer signal stack on 5m candles.

        Args:
            symbol: Trading symbol
            trend: "Uptrend" or "Downtrend"

        Returns:
            Signal or None
        """
        candles = self.client.get_candles(symbol, "M5", count=100)
        df = candles_to_df(candles)

        # ── Candle-close gate ───────────────────────────────────────────────
        # Only allow fresh entries near candle close to avoid mid-candle noise
        if self.CANDLE_CLOSE_GATE:
            last_candle = candles[-1] if candles else None
            if last_candle:
                age_sec = time.time() - last_candle.time.timestamp()
                # Require candle to be in last 60 seconds of its 5m period
                if age_sec > 240:  # More than 4 minutes into the candle
                    log.debug("%s signal skipped: candle-close gate (age=%.0fs)", symbol, age_sec)
                    return None

        # Swap ignored — session/timing filters disabled for early development

        # ── Layer 1: StochRSI ────────────────────────────────────────────────
        stoch = calculate_stoch_rsi(df, length=14, k=3, d=3)
        k_col = [c for c in stoch.columns if "k" in c.lower()][0]
        d_col = [c for c in stoch.columns if "d" in c.lower()][0]
        k = stoch[k_col].iloc[-1]
        d = stoch[d_col].iloc[-1]
        k_prev3 = stoch[k_col].iloc[-4:]

        if trend == "Uptrend":
            stoch_ok = k_prev3.min() < 30 and k > d
        else:
            stoch_ok = k_prev3.max() > 70 and k < d

        stoch_strength = stoch_rsi_score(
            k, d, k_prev3.min(), k_prev3.max(), trend
        )

        # ── Layer 2: MACD histogram ───────────────────────────────────────────
        macd_df = calculate_macd(df, fast=12, slow=26, signal=9)
        hist_col = [c for c in macd_df.columns if "h" in c.lower()][0]
        macd_line_col = [c for c in macd_df.columns if "macd" in c.lower() and "h" not in c.lower() and "s" not in c.lower()][0]
        macd_signal_col = [c for c in macd_df.columns if "signal" in c.lower()][0]
        macd_current = macd_df[hist_col].iloc[-1]
        macd_prev5   = macd_df[hist_col].iloc[-6:-1]
        macd_line = macd_df[macd_line_col].iloc[-1]
        macd_signal_val = macd_df[macd_signal_col].iloc[-1]

        if trend == "Uptrend":
            macd_ok = macd_current > macd_prev5.min()
        else:
            macd_ok = macd_current < macd_prev5.max()

        macd_strength = macd_histogram_score(
            macd_current,
            macd_prev5.min(),
            macd_prev5.max(),
            trend,
        )

        # ── Layer 3: Keltner Channel — band breach (outer bands) ───────────
        kc = calculate_keltner_channels(df, length=20, multiplier=1.5, mamode="ema")
        kc_upper_col = [c for c in kc.columns if "upper" in c.lower() or ("b" in c.lower() and "u" in c.lower())][0]
        kc_lower_col = [c for c in kc.columns if "lower" in c.lower() or ("b" in c.lower() and "l" in c.lower())][0]
        kc_mid_col   = [c for c in kc.columns if "mid" in c.lower() or "b" in c.lower()][0]
        last5_low  = df["l"].iloc[-5:].min()
        last5_high = df["h"].iloc[-5:].max()
        kc_upper_last5 = kc[kc_upper_col].iloc[-5:]
        kc_lower_last5 = kc[kc_lower_col].iloc[-5:]

        if trend == "Uptrend":
            # Price must breach lower band (pullback into support)
            kc_ok = last5_low <= kc_lower_last5.min()
        else:
            # Price must breach upper band (rally into resistance)
            kc_ok = last5_high >= kc_upper_last5.max()

        keltner_strength = keltner_score(
            last5_low, last5_high, kc_lower_last5.min(), kc_upper_last5.max(), trend
        )

        # ── Layer 4: Candlestick (optional) ──────────────────────────────────
        patterns_df = calculate_candlestick_patterns(df)
        recent = patterns_df.iloc[-5:].dropna(how="all")
        identified = recent.columns[(recent != 0).any(axis=0)].tolist()

        if trend == "Uptrend":
            bullish_patterns = {"CDL_ENGULFING", "CDL_HAMMER"}
            candle_ok = bool(set(identified) & bullish_patterns)
        else:
            bearish_patterns = {"CDL_ENGULFING", "CDL_SHOOTINGSTAR", "CDL_SPINNINGTOP"}
            candle_ok = bool(set(identified) & bearish_patterns)

        candle_strength = candlestick_score(patterns_df, trend)

        # ── Aggregate ───────────────────────────────────────────────────────
        # StochRSI, MACD, KC must all pass; candle is optional confirmation
        all_pass = stoch_ok and macd_ok and kc_ok
        if not all_pass:
            log.debug("%s signal blocked: stoch=%s macd=%s kc=%s",
                      symbol, stoch_ok, macd_ok, kc_ok)
            return None

        # Layer 2 score breakdown
        breakdown = {
            "stoch_rsi": stoch_strength,
            "macd": macd_strength,
            "keltner": keltner_strength,
            "candlestick": candle_strength,
        }

        # Trend strength component
        candles_1h  = self.client.get_candles(symbol, "H1",  count=30)
        candles_15m = self.client.get_candles(symbol, "M15", count=60)
        candles_5m  = self.client.get_candles(symbol, "M5",  count=24)
        df_1h = candles_to_df(candles_1h)
        df_15 = candles_to_df(candles_15m)
        df_5  = candles_to_df(candles_5m)
        lr_1h = calculate_linear_regression(df_1h, length=20).iloc[-1]
        lr_15 = calculate_linear_regression(df_15, length=25).iloc[-1]
        lr_5  = calculate_linear_regression(df_5,  length=14).iloc[-1]
        trend_str = trend_score(lr_15, lr_5, trend,
                                self.LR_15M_THRESHOLD, self.LR_5M_THRESHOLD)
        breakdown["trend"] = trend_str

        # Weighted confidence (candle optional — lower weight)
        raw_confidence = (
            breakdown["stoch_rsi"] * 0.30 +
            breakdown["macd"] * 0.25 +
            breakdown["keltner"] * 0.20 +
            breakdown["trend"] * 0.15 +
            breakdown["candlestick"] * 0.10
        )
        # ── Confidence gate ──────────────────────────────────────────────────
        # Signals below 55% confidence are too weak to act on
        MIN_CONFIDENCE = 0.55
        if raw_confidence < MIN_CONFIDENCE:
            log.debug("%s signal rejected: confidence %.1f%% < %.0f%% threshold",
                      symbol, raw_confidence * 100, MIN_CONFIDENCE * 100)
            return None

        confidence = round(raw_confidence, 3)

        # ── Risk / Pricing ───────────────────────────────────────────────────
        atr_ser = calculate_atr(df)
        atr = atr_ser.iloc[-1]
        entry_price = df["c"].iloc[-1]

        if trend == "Uptrend":
            sl = entry_price - (atr * config.SL_ATR_MULTIPLIER)
            tp = entry_price + (atr * config.TP_ATR_MULTIPLIER)
        else:
            sl = entry_price + (atr * config.SL_ATR_MULTIPLIER)
            tp = entry_price - (atr * config.TP_ATR_MULTIPLIER)

        sl = round(sl, _price_decimals(entry_price))
        tp = round(tp, _price_decimals(entry_price))

        return Signal(
            symbol=symbol,
            direction=trend,
            entry_price=round(entry_price, _price_decimals(entry_price)),
            stop_loss=sl,
            take_profit=tp,
            atr=round(atr, 6),
            lot_size=0.0,   # filled by caller via risk.py
            risk_pct=config.RISK_PER_TRADE * 100,
            confidence=confidence,
            breakdown=breakdown,
            trend_direction=trend,
            patterns_found=identified,
            # Indicator snapshot
            stochrsi_k=k,
            stochrsi_d=d,
            macd_line=macd_line,
            macd_signal=macd_signal_val,
            macd_histogram=macd_current,
            kc_upper=float(kc_upper_last5.iloc[-1]),
            kc_mid=float(kc[kc_mid_col].iloc[-1]),
            kc_lower=float(kc_lower_last5.iloc[-1]),
            lr_1h=lr_1h,
            lr_15m=lr_15,
            lr_5m=lr_5,
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def check_symbol(self, symbol: str) -> tuple[Optional[Signal], Optional[str], float, float, float]:
        """Full pipeline: Layer 1 watchlist → trend filter → signal stack.

        Returns (signal, trend, lr_1h, lr_15, lr_5).
        signal is None if symbol fails any filter.
        trend is None if no clear trend (flat).
        """
        if symbol not in self.watchlist:
            log.debug("%s not on watchlist, skipping", symbol)
            return None, None, 0.0, 0.0, 0.0

        trend, lr_1h, lr_15, lr_5 = self._get_trend(symbol)
        if trend is None:
            log.debug("%s no trend, skipping", symbol)
            return None, trend, lr_1h, lr_15, lr_5

        # ── Cooldown check ───────────────────────────────────────────────────
        cooldown_key = f"{symbol}:{trend}"
        last_signal_ts = self._cooldown.get(cooldown_key, 0.0)
        if time.time() - last_signal_ts < self.SIGNAL_COOLDOWN_SECONDS:
            log.debug("%s in cooldown (%.0fs remaining), skipping", symbol,
                      self.SIGNAL_COOLDOWN_SECONDS - (time.time() - last_signal_ts))
            return None, trend, lr_1h, lr_15, lr_5

        signal = self._get_signal(symbol, trend)
        if signal:
            # Record signal timestamp for cooldown
            self._cooldown[cooldown_key] = time.time()
        return signal, trend, lr_1h, lr_15, lr_5


def _price_decimals(price: float) -> int:
    if price >= 1000:
        return 2
    elif price >= 100:
        return 3
    elif price >= 10:
        return 4
    elif price >= 1:
        return 5
    else:
        return 6

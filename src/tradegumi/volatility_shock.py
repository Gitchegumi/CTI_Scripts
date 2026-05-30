"""Volatility shock detection and suppression.

Detects abnormal candles/spikes that would distort trend classification
and signal generation. When enabled, suppresses new signals for a
configurable number of candles after a shock is detected.

Pipeline placement: AFTER candle-close validation, BEFORE trend classification.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from tradegumi import config
from tradegumi.api.base_client import Candle
from tradegumi.indicators import candles_to_df, calculate_atr

log = logging.getLogger(__name__)


@dataclass
class ShockDetectionResult:
    """Result of a volatility-shock check on a single timeframe."""
    detected: bool
    timeframe: str
    candle_time: Optional[str] = None
    true_range: Optional[float] = None
    atr: Optional[float] = None
    atr_multiple: Optional[float] = None
    lookback_bars: int = 0
    direction: str = "none"   # "up", "down", or "none"
    rule: str = "none"        # which rule triggered
    suppression_until: Optional[str] = None
    suppression_candles_remaining: int = 0

    def to_dict(self) -> dict:
        return {
            "volatility_shock_detected": self.detected,
            "shock_timeframe": self.timeframe,
            "shock_candle_time": self.candle_time,
            "shock_true_range": self.true_range,
            "shock_atr": self.atr,
            "shock_atr_multiple": self.atr_multiple,
            "shock_lookback_bars": self.lookback_bars,
            "shock_direction": self.direction,
            "shock_rule": self.rule,
            "shock_suppression_until": self.suppression_until,
            "shock_suppression_candles_remaining": self.suppression_candles_remaining,
        }


@dataclass
class VolatilityShockState:
    """Per-symbol suppression state."""
    symbol: str
    suppressed_until: Optional[datetime] = None
    shock_results: list[ShockDetectionResult] = field(default_factory=list)


class VolatilityShockFilter:
    """Detects volatility shocks and manages per-symbol suppression.

    Configurable thresholds (from config.py or env):
        SHOCK_CANDLE_ATR_MULTIPLE   — single candle TR >= N x ATR
        SHOCK_2_BAR_ATR_MULTIPLE    — abs(close - close_2) >= N x ATR
        SHOCK_3_BAR_ATR_MULTIPLE    — abs(close - close_3) >= N x ATR
        SHOCK_SUPPRESSION_CANDLES   — how many closed candles to block signals
        SHOCK_LOOKBACK_CANDLES      — how many recent candles to scan
    """

    def __init__(self):
        self._initializing = True
        self.enabled = getattr(config, "VOLATILITY_SHOCK_ENABLED", True)
        self.candle_multiple = getattr(config, "SHOCK_CANDLE_ATR_MULTIPLE", 3.0)
        self.bar2_multiple = getattr(config, "SHOCK_2_BAR_ATR_MULTIPLE", 4.0)
        self.bar3_multiple = getattr(config, "SHOCK_3_BAR_ATR_MULTIPLE", 5.0)
        self._suppression_candles = getattr(config, "SHOCK_SUPPRESSION_CANDLES", 3)
        self._legacy_suppression_override: Optional[int] = None
        self.lookback_candles = getattr(config, "SHOCK_LOOKBACK_CANDLES", 3)
        self.m5_true_range_multiple = getattr(config, "SHOCK_M5_TRUE_RANGE_ATR_MULTIPLE", 4.0)
        self.m15_true_range_multiple = getattr(config, "SHOCK_M15_TRUE_RANGE_ATR_MULTIPLE", 3.5)
        self.body_multiple = getattr(config, "SHOCK_BODY_ATR_MULTIPLE", 3.0)
        self.body_range_multiple = getattr(config, "SHOCK_BODY_RANGE_ATR_MULTIPLE", 3.5)
        self.m5_suppression_candles = getattr(config, "SHOCK_M5_SUPPRESSION_CANDLES", 4)
        self.m15_suppression_candles = getattr(config, "SHOCK_M15_SUPPRESSION_CANDLES", 3)
        # Per-symbol state: symbol -> VolatilityShockState
        self._state: dict[str, VolatilityShockState] = {}
        self._initializing = False

    @property
    def suppression_candles(self) -> int:
        """Legacy suppression window used for non-M5/M15 and explicit overrides."""
        return self._suppression_candles

    @suppression_candles.setter
    def suppression_candles(self, value: int) -> None:
        self._suppression_candles = int(value)
        if not getattr(self, "_initializing", False):
            self._legacy_suppression_override = int(value)

    def _true_range(self, high: float, low: float, prev_close: float) -> float:
        """Return the true range for a single bar."""
        return max(high - low, abs(high - prev_close), abs(low - prev_close))

    def _true_range_multiple_for_timeframe(self, timeframe: str) -> float:
        """Return the timeframe-specific true-range shock threshold."""
        normalized = timeframe.upper()
        if normalized == "M5":
            return self.m5_true_range_multiple
        if normalized == "M15":
            return self.m15_true_range_multiple
        return self.candle_multiple

    def _suppression_candles_for_timeframe(self, timeframe: str) -> int:
        """Return the configured suppression candle count for a shock timeframe."""
        if self._legacy_suppression_override is not None:
            return self._legacy_suppression_override
        normalized = timeframe.upper()
        if normalized == "M5":
            return self.m5_suppression_candles
        if normalized == "M15":
            return self.m15_suppression_candles
        return self.suppression_candles

    def _detect_shock_single_candle(
        self,
        df: pd.DataFrame,
        atr_series: pd.Series,
    ) -> Optional[ShockDetectionResult]:
        """Rule 1: single candle TR >= N x ATR.

        ATR is shifted by 1 so the shock candle does not influence its own baseline.
        """
        shifted_atr = atr_series.shift(1)
        for i in range(-self.lookback_candles, 0):
            if i < -len(df) + 1:
                continue
            high = df["h"].iloc[i]
            low = df["l"].iloc[i]
            prev_close = df["c"].iloc[i - 1]
            atr = shifted_atr.iloc[i]
            if pd.isna(atr) or atr <= 0:
                continue
            tr = self._true_range(high, low, prev_close)
            multiple = tr / atr
            threshold = self._true_range_multiple_for_timeframe(df.attrs.get("timeframe", "unknown"))
            if multiple >= threshold:
                direction = "up" if df["c"].iloc[i] > prev_close else "down"
                return ShockDetectionResult(
                    detected=True,
                    timeframe=df.attrs.get("timeframe", "unknown"),
                    candle_time=str(df.index[i]),
                    true_range=round(tr, 6),
                    atr=round(atr, 6),
                    atr_multiple=round(multiple, 2),
                    lookback_bars=abs(i),
                    direction=direction,
                    rule="single_candle_tr",
                )
        return None

    def _detect_shock_body_and_range(
        self,
        df: pd.DataFrame,
        atr_series: pd.Series,
    ) -> Optional[ShockDetectionResult]:
        """Rule 1b: candle body and range are both extreme versus prior ATR."""
        shifted_atr = atr_series.shift(1)
        for i in range(-self.lookback_candles, 0):
            if i < -len(df) + 1:
                continue
            atr = shifted_atr.iloc[i]
            if pd.isna(atr) or atr <= 0:
                continue
            body = abs(df["c"].iloc[i] - df["o"].iloc[i])
            prev_close = df["c"].iloc[i - 1]
            tr = self._true_range(df["h"].iloc[i], df["l"].iloc[i], prev_close)
            body_multiple = body / atr
            range_multiple = tr / atr
            if body_multiple >= self.body_multiple and range_multiple >= self.body_range_multiple:
                direction = "up" if df["c"].iloc[i] > df["o"].iloc[i] else "down"
                return ShockDetectionResult(
                    detected=True,
                    timeframe=df.attrs.get("timeframe", "unknown"),
                    candle_time=str(df.index[i]),
                    true_range=round(tr, 6),
                    atr=round(atr, 6),
                    atr_multiple=round(range_multiple, 2),
                    lookback_bars=abs(i),
                    direction=direction,
                    rule="body_and_range",
                )
        return None

    def _detect_shock_2_bar(
        self,
        df: pd.DataFrame,
        atr_series: pd.Series,
    ) -> Optional[ShockDetectionResult]:
        """Rule 2: abs(close - close_2) >= N x ATR.

        ATR is shifted by 1 so the shock candle does not influence its own baseline.
        """
        shifted_atr = atr_series.shift(1)
        for i in range(-self.lookback_candles, 0):
            if i < -len(df) + 2:
                continue
            close = df["c"].iloc[i]
            close_2 = df["c"].iloc[i - 2]
            atr = shifted_atr.iloc[i]
            if pd.isna(atr) or atr <= 0:
                continue
            diff = abs(close - close_2)
            multiple = diff / atr
            if multiple >= self.bar2_multiple:
                direction = "up" if close > close_2 else "down"
                return ShockDetectionResult(
                    detected=True,
                    timeframe=df.attrs.get("timeframe", "unknown"),
                    candle_time=str(df.index[i]),
                    true_range=round(diff, 6),
                    atr=round(atr, 6),
                    atr_multiple=round(multiple, 2),
                    lookback_bars=abs(i),
                    direction=direction,
                    rule="2_bar_close",
                )
        return None

    def _detect_shock_3_bar(
        self,
        df: pd.DataFrame,
        atr_series: pd.Series,
    ) -> Optional[ShockDetectionResult]:
        """Rule 3: abs(close - close_3) >= N x ATR.

        ATR is shifted by 1 so the shock candle does not influence its own baseline.
        """
        shifted_atr = atr_series.shift(1)
        for i in range(-self.lookback_candles, 0):
            if i < -len(df) + 3:
                continue
            close = df["c"].iloc[i]
            close_3 = df["c"].iloc[i - 3]
            atr = shifted_atr.iloc[i]
            if pd.isna(atr) or atr <= 0:
                continue
            diff = abs(close - close_3)
            multiple = diff / atr
            if multiple >= self.bar3_multiple:
                direction = "up" if close > close_3 else "down"
                return ShockDetectionResult(
                    detected=True,
                    timeframe=df.attrs.get("timeframe", "unknown"),
                    candle_time=str(df.index[i]),
                    true_range=round(diff, 6),
                    atr=round(atr, 6),
                    atr_multiple=round(multiple, 2),
                    lookback_bars=abs(i),
                    direction=direction,
                    rule="3_bar_close",
                )
        return None

    def detect(
        self,
        candles: list[Candle],
        timeframe: str,
    ) -> ShockDetectionResult:
        """Scan recent candles for volatility shocks.

        Returns the most severe shock found (highest ATR multiple), or
        a clean result if none detected.
        """
        if not self.enabled or len(candles) < self.lookback_candles + 3:
            return ShockDetectionResult(
                detected=False,
                timeframe=timeframe,
                lookback_bars=0,
            )

        df = candles_to_df(candles)
        df.attrs["timeframe"] = timeframe
        df.index = pd.DatetimeIndex([c.time for c in candles])
        atr_series = calculate_atr(df, length=14)

        results: list[ShockDetectionResult] = []
        r1 = self._detect_shock_single_candle(df, atr_series)
        if r1:
            results.append(r1)
        r_body = self._detect_shock_body_and_range(df, atr_series)
        if r_body:
            results.append(r_body)
        r2 = self._detect_shock_2_bar(df, atr_series)
        if r2:
            results.append(r2)
        r3 = self._detect_shock_3_bar(df, atr_series)
        if r3:
            results.append(r3)

        if not results:
            return ShockDetectionResult(
                detected=False,
                timeframe=timeframe,
                lookback_bars=self.lookback_candles,
            )

        # Return the most severe (highest ATR multiple)
        best = max(results, key=lambda r: r.atr_multiple or 0.0)
        return best

    def check_symbol(
        self,
        symbol: str,
        candles_by_timeframe: dict[str, list[Candle]],
    ) -> tuple[bool, Optional[ShockDetectionResult], list[ShockDetectionResult]]:
        """Check all timeframes for a symbol and update suppression state.

        Returns:
            (is_suppressed, active_shock, all_shocks_this_check)
        """
        if not self.enabled:
            return False, None, []

        state = self._state.setdefault(symbol, VolatilityShockState(symbol=symbol))
        now = datetime.now(timezone.utc)

        # Check if existing suppression has expired
        if state.suppressed_until is not None and now >= state.suppressed_until:
            state.suppressed_until = None
            state.shock_results = []

        shocks: list[ShockDetectionResult] = []
        for timeframe, candles in candles_by_timeframe.items():
            if not candles:
                continue
            result = self.detect(candles, timeframe)
            if result.detected:
                shocks.append(result)
                log.warning(
                    "VOLATILITY SHOCK detected on %s %s: %s at %s — TR=%.5f ATR=%.5f (%.1fx)",
                    symbol, timeframe, result.rule, result.candle_time,
                    result.true_range, result.atr, result.atr_multiple,
                )

        if shocks:
            # Start/extend suppression
            most_recent = max(
                shocks,
                key=lambda s: datetime.fromisoformat(s.candle_time or "1970-01-01")
                if s.candle_time
                else datetime.min.replace(tzinfo=timezone.utc),
            )
            # Suppression lasts the timeframe-specific candle count.
            tf_seconds = _timeframe_seconds(most_recent.timeframe)
            suppression_candles = self._suppression_candles_for_timeframe(most_recent.timeframe)
            suppression_seconds = tf_seconds * suppression_candles
            suppressed_until = now + pd.Timedelta(seconds=suppression_seconds)
            state.suppressed_until = suppressed_until
            state.shock_results = shocks

            for shock in shocks:
                shock.suppression_until = suppressed_until.isoformat()
                shock.suppression_candles_remaining = self._suppression_candles_for_timeframe(shock.timeframe)

            return True, most_recent, shocks

        # If still under suppression but no new shock this tick
        if state.suppressed_until is not None:
            remaining = max(0, int((state.suppressed_until - now).total_seconds()))
            # Build a synthetic result for diagnostics
            active = state.shock_results[0] if state.shock_results else None
            if active:
                active = ShockDetectionResult(
                    detected=True,
                    timeframe=active.timeframe,
                    candle_time=active.candle_time,
                    true_range=active.true_range,
                    atr=active.atr,
                    atr_multiple=active.atr_multiple,
                    lookback_bars=active.lookback_bars,
                    direction=active.direction,
                    rule=active.rule,
                    suppression_until=state.suppressed_until.isoformat(),
                    suppression_candles_remaining=max(1, remaining // _timeframe_seconds(active.timeframe)),
                )
            return True, active, []

        return False, None, []

    def filter_candles_for_lr(self, candles: list[Candle]) -> tuple[list[Candle], list[int]]:
        """Return (clean_candles, excluded_indices) after removing shock candles.

        Uses a simple heuristic: any candle whose TR > 2.5x ATR is excluded.
        This is intentionally stricter than the shock threshold so we filter
        borderline abnormal candles too.

        ATR is shifted by 1 so the judged candle does not influence its own baseline.
        """
        if not self.enabled or len(candles) < 15:
            return candles, []

        df = candles_to_df(candles)
        df.index = pd.DatetimeIndex([c.time for c in candles])
        atr_series = calculate_atr(df, length=14)
        shifted_atr = atr_series.shift(1)

        excluded: list[int] = []
        clean: list[Candle] = []
        for i, candle in enumerate(candles):
            if i == 0:
                clean.append(candle)
                continue
            atr = shifted_atr.iloc[i]
            if pd.isna(atr) or atr <= 0:
                clean.append(candle)
                continue
            tr = self._true_range(candle.h, candle.l, candles[i - 1].c)
            if tr > atr * 2.5:
                excluded.append(i)
                continue
            clean.append(candle)

        return clean, excluded


def _timeframe_seconds(timeframe: str) -> int:
    """Return the number of seconds represented by a common candle timeframe."""
    normalized = timeframe.upper()
    if normalized.startswith("M"):
        return int(normalized[1:]) * 60
    if normalized.startswith("H"):
        return int(normalized[1:]) * 60 * 60
    if normalized.startswith("D"):
        return int(normalized[1:]) * 24 * 60 * 60
    return 300

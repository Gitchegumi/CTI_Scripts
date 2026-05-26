"""CTI Signal Engine — trend filter + 4-layer signal stack + Layer 2 scoring.

Ported from weekday_entries.py (CTI_Scripts). No MT5, no API calls here —
just pure indicator logic driven by a client passed at construction time.
"""
import hashlib
import json
import logging as log
import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

import pandas as pd

from tradegumi import config
from tradegumi.api.base_client import ExecutionClient, Candle, ProviderRequestError
from tradegumi.strategy_metrics import CriterionResult, EvaluatedOpportunity
from tradegumi.volatility_shock import VolatilityShockFilter, ShockDetectionResult
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


def _chop_diagnostic_criterion(
    chop_type: str,
    context: dict,
) -> CriterionResult:
    """Build a chop/regime filter criterion for diagnostics.

    All chop blocks are market_validity criteria with required=True so they
    appear as blockers in strategy metrics.
    """
    reason_map = {
        "opposite_signal_chop": "market_invalid:opposite_signal_chop",
        "chop_suppression": "market_invalid:chop_suppression",
        "weak_15m_bridge": "trend:weak_15m_bridge",
        "trend_not_persistent": "trend:not_persistent",
        "direction_flip_chop": "market_invalid:direction_flip_chop",
    }
    reason = reason_map.get(chop_type, f"chop:{chop_type}")
    return _criterion(
        "chop_filter",
        "trend",
        context,
        "chop_safe",
        False,
        None,
        "boolean",
        required=True,
        reason=reason,
        context=context,
    )


def _direction_label(trend: Optional[str]) -> str:
    """Normalize trend string into BUY/SELL/none for chop comparison."""
    if trend is None:
        return "none"
    t = str(trend).strip().upper()
    if t in {"UPTREND", "UP", "BUY"}:
        return "BUY"
    if t in {"DOWNTREND", "DOWN", "SELL"}:
        return "SELL"
    return "none"


def _actionable_direction(value: object) -> str:
    """Return BUY/SELL/none for an lr numeric value or trend string."""
    if isinstance(value, str):
        v = value.strip().upper()
        if v in {"BUY", "UPTREND", "UP"}:
            return "BUY"
        if v in {"SELL", "DOWNTREND", "DOWN"}:
            return "SELL"
        return "none"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "none"
    if not math.isfinite(numeric):
        return "none"
    if numeric > 0:
        return "BUY"
    if numeric < 0:
        return "SELL"
    return "none"

log = log.getLogger(__name__)


def _shock_diagnostic_criterion(shock: ShockDetectionResult) -> CriterionResult:
    """Build an informational criterion that records a volatility-shock event.

    A detected shock is a triggered safety condition, NOT a failed calculation.
    The criterion is non-blocking (required=False) and carries no pass/fail verdict
    so the dashboard does not present "volatility_shock failed".
    """
    return _criterion(
        "volatility_shock",
        "data_quality",
        shock.to_dict(),
        "no_shock",
        None,
        None,
        "boolean",
        required=False,
        reason="market_invalid:volatility_shock",
        context=shock.to_dict(),
    )


def _market_validity_criterion(
    valid: bool, reason: str, context: dict
) -> CriterionResult:
    """Build a market-validity criterion for diagnostics."""
    return _criterion(
        "market_validity",
        "data_quality",
        context,
        "valid",
        valid,
        None,
        "boolean",
        reason=reason,
        context=context,
    )


def evaluate_threshold(measured: float, threshold: float, operator: str) -> bool:
    """Evaluate a threshold condition. Supports:

    gte, lte, gt, lt, abs_gte, abs_lte, eq, boolean
    """
    if operator == "gte":
        return measured >= threshold
    if operator == "lte":
        return measured <= threshold
    if operator == "gt":
        return measured > threshold
    if operator == "lt":
        return measured < threshold
    if operator == "abs_gte":
        return abs(measured) >= threshold
    if operator == "abs_lte":
        return abs(measured) <= threshold
    if operator == "eq":
        return measured == threshold
    if operator == "boolean":
        return bool(measured)
    return False


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
    signal_type: str = "pullback"  # "pullback" or "continuation"
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
    raw_lr_1h: float = 0.0
    raw_lr_15m: float = 0.0
    raw_lr_5m: float = 0.0
    filtered_lr_1h: float = 0.0
    filtered_lr_15m: float = 0.0
    filtered_lr_5m: float = 0.0
    trend_changed_after_filter: bool = False
    volatility_shock_detected: bool = False
    shock_timeframe: Optional[str] = None
    shock_candle_time: Optional[str] = None
    shock_true_range: Optional[float] = None
    shock_atr: Optional[float] = None
    shock_atr_multiple: Optional[float] = None
    shock_lookback_bars: int = 0
    shock_direction: str = "none"
    shock_suppression_until: Optional[str] = None
    shock_suppression_candles_remaining: int = 0
    market_validity_state: str = "valid"
    market_validity_reason: Optional[str] = None
    signal_price: Optional[float] = None
    suggested_entry: Optional[float] = None
    entry_tolerance: Optional[float] = None
    setup_condition_first_true_at: Optional[str] = None
    recent_candles: Optional[list[Candle]] = None

    def is_blocked(self) -> bool:
        return self.blocked_reason is not None


@dataclass
class SignalDiagnostic:
    """Diagnostic result for one evaluated symbol."""
    symbol: str
    evaluated_at: str
    trend: Optional[str]
    lr_1h: float
    lr_15m: float
    lr_5m: float
    final_decision: str
    decision_reason: str
    raw_lr_1h: float = 0.0
    raw_lr_15m: float = 0.0
    raw_lr_5m: float = 0.0
    filtered_lr_1h: float = 0.0
    filtered_lr_15m: float = 0.0
    filtered_lr_5m: float = 0.0
    trend_changed_after_filter: bool = False
    volatility_shock_detected: bool = False
    shock_timeframe: Optional[str] = None
    shock_candle_time: Optional[str] = None
    shock_true_range: Optional[float] = None
    shock_atr: Optional[float] = None
    shock_atr_multiple: Optional[float] = None
    shock_lookback_bars: int = 0
    shock_direction: str = "none"
    shock_suppression_until: Optional[str] = None
    shock_suppression_candles_remaining: int = 0
    market_validity_state: str = "valid"
    market_validity_reason: Optional[str] = None
    direction: str = "none"
    confidence: Optional[float] = None
    criteria: list[CriterionResult] = None
    data_quality_notes: list[str] = None
    threshold_version: str = "unknown"
    trend_decision: Optional[dict] = None
    signal_type: str = "pullback"  # "pullback" or "continuation"

    def to_opportunity(self, mode: str) -> EvaluatedOpportunity:
        return EvaluatedOpportunity(
            id=f"{self.symbol}:{self.evaluated_at}",
            evaluated_at=self.evaluated_at,
            symbol=self.symbol,
            mode=mode,
            direction=self.direction,
            trend=self.trend or "flat",
            final_decision=self.final_decision,
            decision_reason=self.decision_reason,
            confidence=self.confidence,
            data_quality_notes=self.data_quality_notes or [],
            threshold_version=self.threshold_version,
            criteria=self.criteria or [],
            trend_decision=self.trend_decision,
            # Volatility shock + filtered LR fields
            volatility_shock_detected=self.volatility_shock_detected,
            shock_timeframe=self.shock_timeframe,
            shock_candle_time=self.shock_candle_time,
            shock_true_range=self.shock_true_range,
            shock_atr=self.shock_atr,
            shock_atr_multiple=self.shock_atr_multiple,
            shock_lookback_bars=self.shock_lookback_bars,
            shock_direction=self.shock_direction,
            shock_suppression_until=self.shock_suppression_until,
            shock_suppression_candles_remaining=self.shock_suppression_candles_remaining,
            raw_lr_1h=self.raw_lr_1h,
            raw_lr_15m=self.raw_lr_15m,
            raw_lr_5m=self.raw_lr_5m,
            filtered_lr_1h=self.filtered_lr_1h,
            filtered_lr_15m=self.filtered_lr_15m,
            filtered_lr_5m=self.filtered_lr_5m,
            trend_changed_after_filter=self.trend_changed_after_filter,
            market_validity_state=self.market_validity_state,
            market_validity_reason=self.market_validity_reason,
        )


def get_threshold_version() -> str:
    """Stable hash of active signal thresholds that affect diagnostics."""
    payload = {
        "lr_1h": SignalEngine.LR_1H_THRESHOLD,
        "lr_15m": SignalEngine.LR_15M_THRESHOLD,
        "lr_5m": SignalEngine.LR_5M_THRESHOLD,
        "cooldown_seconds": SignalEngine.SIGNAL_COOLDOWN_SECONDS,
        "candle_close_gate": SignalEngine.CANDLE_CLOSE_GATE,
        "sl_atr": config.SL_ATR_MULTIPLIER,
        "tp_atr": config.TP_ATR_MULTIPLIER,
        "risk_per_trade": config.RISK_PER_TRADE,
        # CTI-v1.1 dual-path thresholds
        "continuation_kc_proximity_atr": config.CONTINUATION_KC_PROXIMITY_ATR,
        "continuation_structure_bars": config.CONTINUATION_STRUCTURE_BARS,
        "pullback_kc_proximity_atr": config.PULLBACK_KC_PROXIMITY_ATR,
        "pullback_stoch_rsi_relaxed": config.PULLBACK_STOCH_RSI_RELAXED,
        "continuation_trend_require_5m": config.CONTINUATION_TREND_REQUIRE_5M,
        # Chop / regime filter thresholds
        "chop_filter_enabled": config.CHOP_FILTER_ENABLED,
        "chop_opposite_signal_suppression_candles": config.CHOP_OPPOSITE_SIGNAL_SUPPRESSION_CANDLES,
        "chop_direction_flip_lookback_candles": config.CHOP_DIRECTION_FLIP_LOOKBACK_CANDLES,
        "chop_max_direction_flips": config.CHOP_MAX_DIRECTION_FLIPS,
        "chop_require_15m_strength_multiplier": config.CHOP_REQUIRE_15M_STRENGTH_MULTIPLIER,
        "chop_require_trend_persistence_candles": config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES,
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def _criterion(
    name: str,
    layer: str,
    measured: object,
    threshold: object,
    passed: Optional[bool],
    margin: Optional[float] = None,
    operator: str = "boolean",
    required: bool = True,
    quality: str = "complete",
    diagnostic_state: str = "evaluated",
    reason: Optional[str] = None,
    context: Optional[dict] = None,
) -> CriterionResult:
    """Build one metrics criterion with optional structured diagnostic context."""
    normalized = None
    if margin is not None:
        try:
            normalized = min(1.0, abs(float(margin)))
        except (TypeError, ValueError):
            normalized = None
    return CriterionResult(
        criterion_name=name,
        layer=layer,
        measured_value=measured,
        threshold_value=threshold,
        threshold_operator=operator,
        passed=passed,
        margin=margin,
        normalized_margin=normalized,
        required=required,
        blocked_signal=required and (passed is False or quality in {"missing", "malformed"}),
        data_quality=quality,
        diagnostic_state=diagnostic_state,
        reason=reason,
        context=context or {},
    )


def _lr_direction(value: object) -> str:
    """Classify a linear regression result into a normalized direction label."""
    if value is None:
        return "missing"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "invalid"
    if not math.isfinite(numeric):
        return "invalid"
    if numeric > 0:
        return "up"
    if numeric < 0:
        return "down"
    return "flat"


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


def _candle_close_context(candle: Candle, timeframe: str, current_time: Optional[datetime] = None) -> dict:
    """Describe candle-close timing in stable export fields."""
    now = current_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    candle_open = candle.time
    if candle_open.tzinfo is None:
        candle_open = candle_open.replace(tzinfo=timezone.utc)
    candle_close = candle_open + timedelta(seconds=_timeframe_seconds(timeframe))
    seconds_until_close = max(0.0, (candle_close - now).total_seconds())
    seconds_since_close = max(0.0, (now - candle_close).total_seconds())
    return {
        "current_time": now.isoformat(),
        "candle_open_time": candle_open.isoformat(),
        "candle_close_time": candle_close.isoformat(),
        "seconds_until_close": round(seconds_until_close, 3),
        "seconds_since_close": round(seconds_since_close, 3),
        "timeframe": timeframe,
        "gate_rule": "pass_after_candle_close",
        "margin_units": "seconds",
    }


def _closed_candle_index(
    candles: Sequence[Candle],
    timeframe: str,
    current_time: Optional[datetime] = None,
) -> Optional[int]:
    """Return the latest index whose candle has fully closed."""
    now = current_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    latest_index: Optional[int] = None
    for index, candle in enumerate(candles):
        if not getattr(candle, "complete", True):
            continue
        candle_open = candle.time
        if candle_open.tzinfo is None:
            candle_open = candle_open.replace(tzinfo=timezone.utc)
        candle_close = candle_open + timedelta(seconds=_timeframe_seconds(timeframe))
        if candle_close <= now:
            latest_index = index
    return latest_index


def _last_closed_candle_window(
    candles: Sequence[Candle],
    timeframe: str,
    current_time: Optional[datetime] = None,
) -> tuple[Optional[Candle], list[Candle], dict]:
    """Select the latest closed candle and complete window ending at it."""
    if not candles:
        return None, [], {
            "timeframe": timeframe,
            "missing_input": "candles",
            "available_count": 0,
            "gate_rule": "pass_after_candle_close",
        }
    closed_index = _closed_candle_index(candles, timeframe, current_time)
    if closed_index is None:
        return None, [], _candle_close_context(candles[-1], timeframe, current_time)
    window = list(candles[: closed_index + 1])
    return window[-1], window, _candle_close_context(window[-1], timeframe, current_time)


def _signal_window_issue(candles: Sequence[Candle], required_count: int) -> Optional[dict]:
    """Describe missing signal inputs when the closed candle window is too short."""
    available = len(candles)
    if available >= required_count:
        return None
    return {
        "stage": "signal_stack",
        "timeframe": "M5",
        "missing_input": "last_closed_candle_or_indicator_window",
        "error_type": "DataNotReady",
        "required_candles": required_count,
        "available_candles": available,
        "required_closed_candles": required_count,
        "available_closed_candles": available,
        "required_indicator_window": 14,
        "available_indicator_window": 0,
        "available_count": available,
        "required_count": required_count,
        "message": "Signal stack skipped because the last closed candle or required indicator window is unavailable.",
    }


def _signal_readiness_issue(
    *,
    raw_candles: Sequence[Candle],
    closed_candles: Sequence[Candle],
    required_candles: int,
    required_indicator_window: int = 14,
    available_indicator_window: int = 0,
    selected_closed_candle: Optional[Candle] = None,
) -> dict:
    """Build a structured data-not-ready diagnostic for signal-stack inputs."""
    context = {
        "stage": "signal_stack",
        "timeframe": "M5",
        "missing_input": "last_closed_candle_or_indicator_window",
        "error_type": "DataNotReady",
        "required_candles": required_candles,
        "available_candles": len(raw_candles),
        "required_closed_candles": required_candles,
        "available_closed_candles": len(closed_candles),
        "required_indicator_window": required_indicator_window,
        "available_indicator_window": available_indicator_window,
        "available_count": len(closed_candles),
        "required_count": required_candles,
        "message": "Signal stack skipped because the last closed candle or required indicator window is unavailable.",
    }
    if selected_closed_candle is not None:
        context["selected_closed_candle_time"] = selected_closed_candle.time.isoformat()
    return context


def _signal_data_not_ready_criterion(context: dict) -> CriterionResult:
    """Return the blocking signal-engine criterion for readiness diagnostics."""
    return _criterion(
        "signal_engine_data",
        "data_quality",
        context,
        "complete candles and indicators",
        None,
        quality="missing",
        diagnostic_state="missing_data",
        reason="signal_engine_data:missing",
        context=context,
    )


def _first_matching_column(frame: pd.DataFrame, predicate, label: str) -> str:
    """Return the first column matching a signal indicator role."""
    matches = [column for column in frame.columns if predicate(str(column).lower())]
    if not matches:
        raise ValueError(f"Missing required indicator column: {label}")
    return matches[0]


def _usable_indicator_window(
    frame: pd.DataFrame,
    columns: Sequence[str],
    required_window: int,
    selected_closed_candle: Candle,
) -> tuple[pd.DataFrame, int, bool]:
    """Return usable indicator rows and whether they align with the closed candle."""
    if frame.empty:
        return frame, 0, False
    usable = frame.dropna(subset=list(columns))
    available = len(usable)
    if available == 0:
        return usable, 0, False
    index_value = usable.index[-1]
    aligned = True
    if isinstance(index_value, pd.Timestamp):
        selected_time = selected_closed_candle.time
        if selected_time.tzinfo is None:
            selected_time = selected_time.replace(tzinfo=timezone.utc)
        aligned = index_value.to_pydatetime() == selected_time
    return usable, available, aligned and available >= required_window


def _compact_data_issue_context(exc: Exception, *, stage: str, timeframe: str = "M5") -> dict:
    """Summarize missing signal inputs without exporting raw candle data."""
    message = str(exc)
    missing_input = "signal_stack_input"
    if isinstance(exc, IndexError):
        missing_input = "last_closed_candle_or_indicator_window"
    elif isinstance(exc, KeyError):
        missing_input = f"indicator_column:{message.strip()}"
    elif isinstance(exc, ValueError):
        missing_input = "malformed_price_or_indicator_data"
    return {
        "stage": stage,
        "timeframe": timeframe,
        "missing_input": missing_input,
        "error_type": exc.__class__.__name__,
        "error_message": message,
    }


def _provider_request_issue_context(exc: ProviderRequestError, *, stage: str) -> dict:
    """Return signal diagnostic context for upstream provider request failures."""
    context = exc.to_diagnostic_context(stage=stage)
    context["timeframe"] = context.get("granularity") or "M5"
    context["missing_input"] = "oanda_candle_data" if exc.operation == "candle_fetch" else "oanda_api_response"
    return context


def classify_trend_bias(
    lr_1h: object,
    lr_15m: object,
    lr_5m: object,
    threshold_1h: float,
    threshold_15m: float,
    threshold_5m: float,
) -> dict:
    """CTI-v1.1 continuation path: 1H+15M define bias, 5M is timing only.

    For continuation entries, we only require 1H+15M to agree and pass strength.
    The 5M is allowed to temporarily conflict (it's the entry point timing).
    """
    values = {"1h": lr_1h, "15m": lr_15m, "5m": lr_5m}
    directions = {name: _lr_direction(value) for name, value in values.items()}
    missing = [name for name, direction in directions.items() if direction == "missing"]
    invalid = [name for name, direction in directions.items() if direction == "invalid"]

    numeric_values: dict[str, Optional[float]] = {}
    for name, value in values.items():
        try:
            numeric_values[name] = float(value)
        except (TypeError, ValueError):
            numeric_values[name] = None

    strength_passed = {
        "1h": numeric_values["1h"] is not None and math.isfinite(numeric_values["1h"]) and abs(numeric_values["1h"]) >= threshold_1h,
        "15m": numeric_values["15m"] is not None and math.isfinite(numeric_values["15m"]) and abs(numeric_values["15m"]) >= threshold_15m,
        "5m": numeric_values["5m"] is not None and math.isfinite(numeric_values["5m"]) and abs(numeric_values["5m"]) >= threshold_5m,
    }
    # Only require 1H + 15M to agree and pass strength for continuation bias
    bias_directions = [directions["1h"], directions["15m"]]
    bias_agree = len(set(bias_directions)) == 1 and bias_directions[0] in {"up", "down"}
    bias_strength_passed = strength_passed["1h"] and strength_passed["15m"]

    if missing:
        no_bias_reason = "missing_data"
    elif invalid:
        no_bias_reason = "invalid_lr_result"
    else:
        insufficient = [name for name, passed in strength_passed.items() if not passed and name in ("1h", "15m")]
        if len(insufficient) > 1:
            no_bias_reason = "multiple_insufficient_strength"
        elif insufficient:
            no_bias_reason = f"insufficient_strength_{insufficient[0]}"
        elif not bias_agree:
            no_bias_reason = "bias_direction_conflict"
        else:
            no_bias_reason = None

    if no_bias_reason is None and bias_strength_passed and bias_agree:
        bias_result = "up" if bias_directions[0] == "up" else "down"
        final_direction = "BUY" if bias_result == "up" else "SELL"
    else:
        bias_result = "flat"
        final_direction = "none"
        no_bias_reason = no_bias_reason or "flat_after_bias_classification"

    return {
        "strength_passed_1h": strength_passed["1h"],
        "strength_passed_15m": strength_passed["15m"],
        "strength_passed_5m": strength_passed["5m"],
        "direction_1h": directions["1h"],
        "direction_15m": directions["15m"],
        "direction_5m": directions["5m"],
        "bias_directions_agree": bias_agree,
        "bias_strength_passed": bias_strength_passed,
        "trend_classification_input": {
            "lr_1h": numeric_values["1h"],
            "lr_15m": numeric_values["15m"],
            "lr_5m": numeric_values["5m"],
            "threshold_1h": threshold_1h,
            "threshold_15m": threshold_15m,
            "threshold_5m": threshold_5m,
        },
        "trend_classification_output": {
            "bias_result": bias_result,
            "final_direction": final_direction,
            "no_bias_reason": no_bias_reason,
        },
        "bias_result": bias_result,
        "final_direction": final_direction,
        "no_bias_reason": no_bias_reason,
    }


def classify_trend_decision(
    lr_1h: object,
    lr_15m: object,
    lr_5m: object,
    threshold_1h: float,
    threshold_15m: float,
    threshold_5m: float,
) -> dict:
    """Explain the existing three-timeframe trend classification decision."""
    values = {"1h": lr_1h, "15m": lr_15m, "5m": lr_5m}
    directions = {name: _lr_direction(value) for name, value in values.items()}
    missing = [name for name, direction in directions.items() if direction == "missing"]
    invalid = [name for name, direction in directions.items() if direction == "invalid"]

    numeric_values: dict[str, Optional[float]] = {}
    for name, value in values.items():
        try:
            numeric_values[name] = float(value)
        except (TypeError, ValueError):
            numeric_values[name] = None

    strength_passed = {
        "1h": numeric_values["1h"] is not None and math.isfinite(numeric_values["1h"]) and abs(numeric_values["1h"]) >= threshold_1h,
        "15m": numeric_values["15m"] is not None and math.isfinite(numeric_values["15m"]) and abs(numeric_values["15m"]) >= threshold_15m,
        "5m": numeric_values["5m"] is not None and math.isfinite(numeric_values["5m"]) and abs(numeric_values["5m"]) >= threshold_5m,
    }
    actionable_directions = [directions["1h"], directions["15m"], directions["5m"]]
    directions_agree = len(set(actionable_directions)) == 1 and actionable_directions[0] in {"up", "down"}
    strengths_all_passed = all(strength_passed.values())

    if missing:
        no_trend_reason = "missing_data"
    elif invalid:
        no_trend_reason = "invalid_lr_result"
    else:
        insufficient = [name for name, passed in strength_passed.items() if not passed]
        if len(insufficient) > 1:
            no_trend_reason = "multiple_insufficient_strength"
        elif insufficient:
            no_trend_reason = f"insufficient_strength_{insufficient[0]}"
        elif not directions_agree:
            no_trend_reason = "direction_conflict"
        else:
            no_trend_reason = None

    if no_trend_reason is None and strengths_all_passed and directions_agree:
        trend_result = "up" if actionable_directions[0] == "up" else "down"
        final_direction = "BUY" if trend_result == "up" else "SELL"
    else:
        trend_result = "flat"
        final_direction = "none"
        no_trend_reason = no_trend_reason or "flat_after_classification"

    return {
        "strength_passed_1h": strength_passed["1h"],
        "strength_passed_15m": strength_passed["15m"],
        "strength_passed_5m": strength_passed["5m"],
        "direction_1h": directions["1h"],
        "direction_15m": directions["15m"],
        "direction_5m": directions["5m"],
        "directions_agree": directions_agree,
        "strengths_all_passed": strengths_all_passed,
        "trend_classification_input": {
            "lr_1h": numeric_values["1h"],
            "lr_15m": numeric_values["15m"],
            "lr_5m": numeric_values["5m"],
            "threshold_1h": threshold_1h,
            "threshold_15m": threshold_15m,
            "threshold_5m": threshold_5m,
        },
        "trend_classification_output": {
            "trend_result": trend_result,
            "final_direction": final_direction,
            "no_trend_reason": no_trend_reason,
        },
        "trend_result": trend_result,
        "final_direction": final_direction,
        "no_trend_reason": no_trend_reason,
    }


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
    SIGNAL_WINDOW_MIN_CANDLES = 35
    SIGNAL_INDICATOR_MIN_WINDOW = 14

    # Cooldown tracking: key = f"{symbol}:{trend}", value = last_signal_ts
    _cooldown: dict[str, float] = {}

    def __init__(self, client: ExecutionClient, watchlist: Optional[set[str]] = None, shock_filter: Optional[VolatilityShockFilter] = None):
        self.client = client
        self.watchlist = watchlist or set(config.EXECUTION_SYMBOLS)
        self.shock_filter = shock_filter or VolatilityShockFilter()
        # Per-instance chop filter state (was class-level; isolation fix)
        self._chop_state: dict[str, dict] = {}

    # ── Chop / Regime Filter helpers ──────────────────────────────────────────

    def _record_signal_direction(self, symbol: str, direction: str, timestamp: Optional[datetime] = None) -> None:
        """Record the most recent emitted usable signal direction per symbol.

        Called whenever a signal is actually emitted.
        """
        now = timestamp or datetime.now(timezone.utc)
        state = self._chop_state.setdefault(symbol, {})
        state["last_signal_direction"] = direction
        state["last_signal_timestamp"] = now.isoformat()
        state["last_signal_timestamp_unix"] = now.timestamp()

    def _has_opposite_signal_conflict(self, symbol: str, direction: str) -> tuple[bool, dict]:
        """Check if a prior same-symbol signal is unresolved (no opposite-direction conflict).

        Returns (conflict, context) where context is None when no conflict.
        """
        state = self._chop_state.get(symbol)
        if state is None:
            return False, {}
        last_dir = state.get("last_signal_direction")
        if last_dir is None:
            return False, {}
        current = _direction_label(direction)
        last = _direction_label(last_dir)
        if current != "none" and last != "none" and current != last:
            return True, {
                "symbol": symbol,
                "current_direction": current,
                "conflicting_direction": last,
                "last_signal_timestamp": state.get("last_signal_timestamp"),
                "last_signal_direction": last,
            }
        return False, {}

    def _set_chop_suppression(self, symbol: str, candles_remaining: int, current_time: Optional[datetime] = None) -> None:
        """Enter chop suppression for a symbol after an opposite-direction conflict."""
        now = current_time or datetime.now(timezone.utc)
        # M5 candles: suppression ends after N candles from now
        suppression_until = now + timedelta(minutes=5 * candles_remaining)
        state = self._chop_state.setdefault(symbol, {})
        state["chop_suppression_until"] = suppression_until.isoformat()
        state["chop_suppression_candles"] = candles_remaining

    def _is_chop_suppressed(self, symbol: str, current_time: Optional[datetime] = None) -> tuple[bool, dict]:
        """Check if symbol is currently under chop suppression.

        Returns (suppressed, context).
        """
        state = self._chop_state.get(symbol)
        if state is None:
            return False, {}
        until_str = state.get("chop_suppression_until")
        if until_str is None:
            return False, {}
        now = current_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        try:
            until = datetime.fromisoformat(until_str)
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
        except ValueError:
            return False, {}
        remaining = max(0, int((until - now).total_seconds() / 300))
        if now < until:
            return True, {
                "symbol": symbol,
                "suppression_until": until.isoformat(),
                "suppression_candles_remaining": remaining,
                "last_signal_timestamp": state.get("last_signal_timestamp"),
                "last_signal_direction": state.get("last_signal_direction"),
            }
        # Expired — clean up
        state.pop("chop_suppression_until", None)
        state.pop("chop_suppression_candles", None)
        return False, {}

    def _record_trend_evaluation(self, symbol: str, direction: str, current_time: Optional[datetime] = None) -> None:
        """Append the latest evaluated direction to per-symbol trend history."""
        now = current_time or datetime.now(timezone.utc)
        state = self._chop_state.setdefault(symbol, {})
        evaluations = state.setdefault("trend_evaluations", [])
        evaluations.append({"direction": direction, "timestamp": now.isoformat()})
        # Keep only needed history for flip detection + persistence
        max_keep = max(config.CHOP_DIRECTION_FLIP_LOOKBACK_CANDLES, config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES) + 2
        if len(evaluations) > max_keep:
            state["trend_evaluations"] = evaluations[-max_keep:]

    def _recent_actionable_directions(self, symbol: str, count: int) -> list[str]:
        """Return the last N actionable (BUY/SELL) directions, newest last."""
        state = self._chop_state.get(symbol, {})
        evaluations = state.get("trend_evaluations", [])
        dirs = []
        for ev in reversed(evaluations):
            d = _direction_label(ev.get("direction", "none"))
            if d != "none":
                dirs.append(d)
            if len(dirs) >= count:
                break
        return list(reversed(dirs))

    def _count_direction_flips(self, symbol: str, lookback: int) -> tuple[int, list[str]]:
        """Count direction flips in the last N actionable evaluations.

        Ignore none/flat transitions. Returns (flip_count, recent_directions).
        """
        dirs = self._recent_actionable_directions(symbol, lookback)
        flips = 0
        for i in range(1, len(dirs)):
            if dirs[i] != dirs[i - 1]:
                flips += 1
        return flips, dirs

    def _check_chop_filters(
        self,
        symbol: str,
        trend: str,
        lr_15m: float,
        current_time: Optional[datetime] = None,
    ) -> tuple[bool, list[CriterionResult], Optional[str], Optional[dict]]:
        """Run all chop/regime filters after trend classification and before signal stack.

        Returns (blocked, criteria, reason, context) where reason is a stable
        decision_reason string, and context is extra diagnostic info.
        """
        if not config.CHOP_FILTER_ENABLED:
            return False, [], None, None

        criteria: list[CriterionResult] = []
        current_dir = _direction_label(trend)

        # 1. Chop suppression (ongoing from prior opposite-direction conflict)
        suppressed, suppression_ctx = self._is_chop_suppressed(symbol, current_time)
        if suppressed:
            criteria.append(_chop_diagnostic_criterion("chop_suppression", suppression_ctx))
            return (
                True,
                criteria,
                "market_invalid:chop_suppression",
                suppression_ctx,
            )

        # 2. Opposite-direction same-symbol conflict → trigger suppression
        conflict, conflict_ctx = self._has_opposite_signal_conflict(symbol, trend)
        if conflict:
            # Enter suppression for future candles
            self._set_chop_suppression(symbol, config.CHOP_OPPOSITE_SIGNAL_SUPPRESSION_CANDLES, current_time)
            criteria.append(_chop_diagnostic_criterion("opposite_signal_chop", conflict_ctx))
            return (
                True,
                criteria,
                "market_invalid:opposite_signal_chop",
                conflict_ctx,
            )

        # 3. Stronger 15M bridge requirement
        required_15m = self.LR_15M_THRESHOLD * config.CHOP_REQUIRE_15M_STRENGTH_MULTIPLIER
        if abs(lr_15m) < required_15m:
            strength_ctx = {
                "lr_15m": lr_15m,
                "threshold_15m": self.LR_15M_THRESHOLD,
                "multiplier": config.CHOP_REQUIRE_15M_STRENGTH_MULTIPLIER,
                "required_15m_strength": required_15m,
                "margin": abs(lr_15m) - required_15m,
            }
            criteria.append(_chop_diagnostic_criterion("weak_15m_bridge", strength_ctx))
            return (
                True,
                criteria,
                "trend:weak_15m_bridge",
                strength_ctx,
            )

        # 4. Trend persistence requirement
        persistence_needed = config.CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES
        if persistence_needed > 0 and current_dir != "none":
            recent_dirs = self._recent_actionable_directions(symbol, persistence_needed)
            if len(recent_dirs) < persistence_needed:
                persistent = False
            else:
                persistent = all(d == current_dir for d in recent_dirs)
            if not persistent:
                persist_ctx = {
                    "required_persistence_candles": persistence_needed,
                    "recent_directions": recent_dirs,
                    "current_direction": current_dir,
                }
                criteria.append(_chop_diagnostic_criterion("trend_not_persistent", persist_ctx))
                return (
                    True,
                    criteria,
                    "trend:not_persistent",
                    persist_ctx,
                )

        # 5. Direction flip chop detection
        lookback = config.CHOP_DIRECTION_FLIP_LOOKBACK_CANDLES
        max_flips = config.CHOP_MAX_DIRECTION_FLIPS
        if lookback > 0 and current_dir != "none":
            flips, recent_dirs = self._count_direction_flips(symbol, lookback)
            if flips > max_flips:
                flip_ctx = {
                    "lookback_candles": lookback,
                    "max_allowed_flips": max_flips,
                    "observed_flips": flips,
                    "recent_directions": recent_dirs,
                }
                criteria.append(_chop_diagnostic_criterion("direction_flip_chop", flip_ctx))
                return (
                    True,
                    criteria,
                    "market_invalid:direction_flip_chop",
                    flip_ctx,
                )

        return False, [], None, None

    # ── Trend Filter ─────────────────────────────────────────────────────────

    def _get_trend(
        self,
        symbol: str,
        candles_by_tf: Optional[dict[str, list[Candle]]] = None,
    ) -> tuple[Optional[str], float, float, float, float, float, float, list[int], list[int], list[int], dict]:
        """Linear Regression trend filter with raw + filtered LR.

        All 3 TFs must agree: 1H (count=30, length=20), 15m (length=25), 5m (length=14).
        Returns (trend, raw_lr_1h, raw_lr_15m, raw_lr_5m, filtered_lr_1h, filtered_lr_15m, filtered_lr_5m,
                 excluded_1h, excluded_15m, excluded_5m, trend_decision).
        """
        if candles_by_tf is None:
            candles_1h  = self.client.get_candles(symbol, "H1",  count=30)
            candles_15m = self.client.get_candles(symbol, "M15", count=60)
            candles_5m  = self.client.get_candles(symbol, "M5",  count=24)
        else:
            candles_1h  = candles_by_tf.get("H1", [])
            candles_15m = candles_by_tf.get("M15", [])
            candles_5m  = candles_by_tf.get("M5", [])

        # Filtered LR: exclude abnormal candles
        clean_1h, excluded_1h = self.shock_filter.filter_candles_for_lr(candles_1h)
        clean_15m, excluded_15m = self.shock_filter.filter_candles_for_lr(candles_15m)
        clean_5m, excluded_5m = self.shock_filter.filter_candles_for_lr(candles_5m)

        df_1h_raw = candles_to_df(candles_1h)
        df_15_raw = candles_to_df(candles_15m)
        df_5_raw  = candles_to_df(candles_5m)

        df_1h_clean = candles_to_df(clean_1h) if clean_1h else df_1h_raw
        df_15_clean = candles_to_df(clean_15m) if clean_15m else df_15_raw
        df_5_clean  = candles_to_df(clean_5m) if clean_5m else df_5_raw

        raw_lr_1h = calculate_linear_regression(df_1h_raw, length=20).iloc[-1] if len(df_1h_raw) >= 20 else 0.0
        raw_lr_15 = calculate_linear_regression(df_15_raw, length=25).iloc[-1] if len(df_15_raw) >= 25 else 0.0
        raw_lr_5  = calculate_linear_regression(df_5_raw,  length=14).iloc[-1] if len(df_5_raw) >= 14 else 0.0

        # If too many excluded → insufficient clean data → flat
        MIN_CLEAN_RATIO = 0.5
        filtered_lr_1h = raw_lr_1h
        filtered_lr_15 = raw_lr_15
        filtered_lr_5 = raw_lr_5
        trend = None

        def _usable(candles, excluded, min_needed, length):
            if len(candles) < min_needed:
                return False
            return (len(candles) - len(excluded)) / len(candles) >= MIN_CLEAN_RATIO

        usable_1h = _usable(candles_1h, excluded_1h, 20, 20)
        usable_15m = _usable(candles_15m, excluded_15m, 25, 25)
        usable_5m = _usable(candles_5m, excluded_5m, 14, 14)

        if usable_1h:
            filtered_lr_1h = calculate_linear_regression(df_1h_clean, length=20).iloc[-1]
        if usable_15m:
            filtered_lr_15 = calculate_linear_regression(df_15_clean, length=25).iloc[-1]
        if usable_5m:
            filtered_lr_5 = calculate_linear_regression(df_5_clean, length=14).iloc[-1]

        # Use filtered LRs for trend classification when enabled
        if self.shock_filter.enabled:
            if usable_1h and usable_15m and usable_5m:
                trend_decision = classify_trend_decision(
                    filtered_lr_1h, filtered_lr_15, filtered_lr_5,
                    self.LR_1H_THRESHOLD, self.LR_15M_THRESHOLD, self.LR_5M_THRESHOLD,
                )
            else:
                # Shock filter enabled but insufficient clean data → no trend, do NOT fall back to raw LR
                trend_decision = {
                    "strength_passed_1h": usable_1h and abs(filtered_lr_1h) >= self.LR_1H_THRESHOLD,
                    "strength_passed_15m": usable_15m and abs(filtered_lr_15) >= self.LR_15M_THRESHOLD,
                    "strength_passed_5m": usable_5m and abs(filtered_lr_5) >= self.LR_5M_THRESHOLD,
                    "direction_1h": _lr_direction(filtered_lr_1h),
                    "direction_15m": _lr_direction(filtered_lr_15),
                    "direction_5m": _lr_direction(filtered_lr_5),
                    "directions_agree": False,
                    "strengths_all_passed": False,
                    "trend_classification_input": {
                        "lr_1h": filtered_lr_1h,
                        "lr_15m": filtered_lr_15,
                        "lr_5m": filtered_lr_5,
                        "threshold_1h": self.LR_1H_THRESHOLD,
                        "threshold_15m": self.LR_15M_THRESHOLD,
                        "threshold_5m": self.LR_5M_THRESHOLD,
                    },
                    "trend_classification_output": {
                        "trend_result": "flat",
                        "final_direction": "none",
                        "no_trend_reason": "insufficient_clean_data",
                    },
                    "trend_result": "flat",
                    "final_direction": "none",
                    "no_trend_reason": "insufficient_clean_data",
                }
                return trend, raw_lr_1h, raw_lr_15, raw_lr_5, filtered_lr_1h, filtered_lr_15, filtered_lr_5, excluded_1h, excluded_15m, excluded_5m, trend_decision
        else:
            trend_decision = classify_trend_decision(
                raw_lr_1h, raw_lr_15, raw_lr_5,
                self.LR_1H_THRESHOLD, self.LR_15M_THRESHOLD, self.LR_5M_THRESHOLD,
            )

        log.debug("%s raw_LR_1h=%.4f%% raw_LR_15m=%.4f%% raw_LR_5m=%.4f%% | filtered_LR_1h=%.4f%% filtered_LR_15m=%.4f%% filtered_LR_5m=%.4f%%",
                  symbol, raw_lr_1h, raw_lr_15, raw_lr_5, filtered_lr_1h, filtered_lr_15, filtered_lr_5)

        if trend_decision["trend_result"] == "up":
            trend = "Uptrend"
        elif trend_decision["trend_result"] == "down":
            trend = "Downtrend"
        else:
            trend = None

        return trend, raw_lr_1h, raw_lr_15, raw_lr_5, filtered_lr_1h, filtered_lr_15, filtered_lr_5, excluded_1h, excluded_15m, excluded_5m, trend_decision

    # ── 4-Layer Signal Stack ─────────────────────────────────────────────────

    def _get_signal(
        self,
        symbol: str,
        trend: str,
        trend_lr: Optional[tuple[float, float, float]] = None,
        *,
        raw_lr_1h: float = 0.0,
        raw_lr_15m: float = 0.0,
        raw_lr_5m: float = 0.0,
        filtered_lr_1h: float = 0.0,
        filtered_lr_15m: float = 0.0,
        filtered_lr_5m: float = 0.0,
        trend_changed_after_filter: bool = False,
        shock_result: Optional[ShockDetectionResult] = None,
    ) -> tuple[Optional[Signal], list[CriterionResult], str, Optional[float]]:
        """Run the 4-layer signal stack on 5m candles.

        Args:
            symbol: Trading symbol
            trend: "Uptrend" or "Downtrend"
            trend_lr: Optional LR values already computed by the trend filter.
                      When provided, these are used as the primary LR values.
                      Raw/filtered LR values are still passed for shock diagnostics.

        Returns:
            Signal or None
        """
        candles = self.client.get_candles(symbol, "M5", count=100)
        if not candles:
            context = _signal_readiness_issue(
                raw_candles=[],
                closed_candles=[],
                required_candles=self.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=self.SIGNAL_INDICATOR_MIN_WINDOW,
            )
            return None, [_signal_data_not_ready_criterion(context)], "signal_stack_data_not_ready", None
        closed_candle, closed_window, close_context = _last_closed_candle_window(candles, "M5")

        # ── Candle-close gate ───────────────────────────────────────────────
        # Only allow fresh entries near candle close to avoid mid-candle noise
        criteria: list[CriterionResult] = []

        if self.CANDLE_CLOSE_GATE:
            if not closed_candle:
                context = {"timeframe": "M5", "gate_rule": "pass_after_candle_close", "missing_input": "last_closed_candle"}
                context.update(close_context)
                seconds_until_close = context.get("seconds_until_close", 0)
                if seconds_until_close > 0:
                    criteria.append(
                        _criterion(
                            "candle_close_gate",
                            "timing",
                            seconds_until_close,
                            "0 seconds until close",
                            False,
                            -seconds_until_close,
                            "lte",
                            diagnostic_state="waiting",
                            reason="candle_close_gate:waiting_for_close",
                            context=context,
                        )
                    )
                    return None, criteria, "candle_close_gate:waiting_for_close", None
                criteria.append(
                    _criterion(
                        "candle_close_gate",
                        "timing",
                        None,
                        "closed candle",
                        None,
                        None,
                        quality="missing",
                        diagnostic_state="missing_data",
                        reason="candle_close_gate:missing_timing_data",
                        context=close_context,
                    )
                )
                return None, criteria, "missing_candle_time", None
            seconds_until_close = close_context["seconds_until_close"]
            seconds_since_close = close_context["seconds_since_close"]
            if seconds_until_close > 0:
                log.debug("%s signal waiting for candle close (%.0fs remaining)", symbol, seconds_until_close)
                criteria.append(
                    _criterion(
                        "candle_close_gate",
                        "timing",
                        seconds_until_close,
                        "0 seconds until close",
                        False,
                        -seconds_until_close,
                        "lte",
                        diagnostic_state="waiting",
                        reason="candle_close_gate:waiting_for_close",
                        context=close_context,
                    )
                )
                return None, criteria, "candle_close_gate:waiting_for_close", None
            if seconds_since_close > _timeframe_seconds("M5") * 2:
                criteria.append(
                    _criterion(
                        "candle_close_gate",
                        "timing",
                        seconds_since_close,
                        f"<={_timeframe_seconds('M5') * 2} seconds since close",
                        False,
                        (_timeframe_seconds("M5") * 2) - seconds_since_close,
                        "lte",
                        diagnostic_state="evaluated",
                        reason="candle_close_gate:stale_candle",
                        context=close_context,
                    )
                )
                return None, criteria, "candle_close_gate:stale_candle", None
            criteria.append(
                _criterion(
                    "candle_close_gate",
                    "timing",
                    seconds_since_close,
                    ">=0 seconds since close",
                    True,
                    seconds_since_close,
                    "gte",
                    reason="candle_close_gate:passed",
                    context=close_context,
                )
            )

        # Swap ignored — session/timing filters disabled for early development

        # ── Layer 1: StochRSI ────────────────────────────────────────────────
        window_issue = _signal_window_issue(closed_window, self.SIGNAL_WINDOW_MIN_CANDLES)
        if window_issue:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=self.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=self.SIGNAL_INDICATOR_MIN_WINDOW,
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return None, criteria, "signal_stack_data_not_ready", None

        df = candles_to_df(closed_window)
        df.index = pd.DatetimeIndex([candle.time for candle in closed_window])
        stoch = calculate_stoch_rsi(df, length=14, k=3, d=3)
        k_col = _first_matching_column(stoch, lambda name: "k" in name, "stoch_rsi_k")
        d_col = _first_matching_column(stoch, lambda name: "d" in name, "stoch_rsi_d")
        stoch, stoch_available, stoch_ready = _usable_indicator_window(
            stoch,
            [k_col, d_col],
            self.SIGNAL_INDICATOR_MIN_WINDOW,
            closed_candle,
        )
        if not stoch_ready:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=self.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=self.SIGNAL_INDICATOR_MIN_WINDOW,
                available_indicator_window=stoch_available,
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return None, criteria, "signal_stack_data_not_ready", None
        k = stoch[k_col].iloc[-1]
        d = stoch[d_col].iloc[-1]
        k_prev3 = stoch[k_col].iloc[-4:]

        if trend == "Uptrend":
            if config.PULLBACK_STOCH_RSI_RELAXED:
                # CTI-v1.1 pullback: allow curling up from below 40 (not strictly oversold)
                stoch_ok = (
                    (k_prev3.min() < 30 and k > d)  # strict cross from oversold
                    or (k_prev3.min() < 40 and k > d and k < 50)  # curling up from below 40
                )
            else:
                stoch_ok = k_prev3.min() < 30 and k > d
            stoch_margin = min(30 - float(k_prev3.min()), float(k - d))
        else:
            if config.PULLBACK_STOCH_RSI_RELAXED:
                # CTI-v1.1 pullback: allow rolling down from above 60 (not strictly overbought)
                stoch_ok = (
                    (k_prev3.max() > 70 and k < d)  # strict cross from overbought
                    or (k_prev3.max() > 60 and k < d and k > 50)  # rolling down from above 60
                )
            else:
                stoch_ok = k_prev3.max() > 70 and k < d
            stoch_margin = min(float(k_prev3.max()) - 70, float(d - k))

        stoch_strength = stoch_rsi_score(
            k, d, k_prev3.min(), k_prev3.max(), trend
        )

        # ── Layer 2: MACD histogram ───────────────────────────────────────────
        macd_df = calculate_macd(df, fast=12, slow=26, signal=9)
        hist_col = _first_matching_column(macd_df, lambda name: "h" in name, "macd_histogram")
        macd_line_col = _first_matching_column(
            macd_df,
            lambda name: "macd" in name and "h" not in name and "s" not in name,
            "macd_line",
        )
        macd_signal_col = _first_matching_column(macd_df, lambda name: "s" in name and "h" not in name, "macd_signal")
        macd_df, macd_available, macd_ready = _usable_indicator_window(
            macd_df,
            [hist_col, macd_line_col, macd_signal_col],
            self.SIGNAL_INDICATOR_MIN_WINDOW,
            closed_candle,
        )
        if not macd_ready or len(macd_df[hist_col].iloc[-6:-1]) < 5:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=self.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=self.SIGNAL_INDICATOR_MIN_WINDOW,
                available_indicator_window=macd_available,
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return None, criteria, "signal_stack_data_not_ready", None
        macd_current = macd_df[hist_col].iloc[-1]
        macd_prev5   = macd_df[hist_col].iloc[-6:-1]
        macd_line = macd_df[macd_line_col].iloc[-1]
        macd_signal_val = macd_df[macd_signal_col].iloc[-1]

        if trend == "Uptrend":
            macd_ok = macd_current > macd_prev5.min()
            macd_margin = float(macd_current - macd_prev5.min())
        else:
            macd_ok = macd_current < macd_prev5.max()
            macd_margin = float(macd_prev5.max() - macd_current)

        macd_strength = macd_histogram_score(
            macd_current,
            macd_prev5.min(),
            macd_prev5.max(),
            trend,
        )

        # ── Layer 3: Keltner Channel — band breach (outer bands) ───────────
        kc = calculate_keltner_channels(df, length=20, multiplier=1.5, mamode="ema")
        kc_upper_col = _first_matching_column(kc, lambda name: "u" in name and "l" not in name and "b" not in name, "keltner_upper")
        kc_lower_col = _first_matching_column(kc, lambda name: "l" in name and "u" not in name and "b" not in name, "keltner_lower")
        kc_mid_col = _first_matching_column(kc, lambda name: ("b" in name and "u" not in name and "l" not in name) or "m" in name, "keltner_mid")
        kc, kc_available, kc_ready = _usable_indicator_window(
            kc,
            [kc_upper_col, kc_lower_col, kc_mid_col],
            self.SIGNAL_INDICATOR_MIN_WINDOW,
            closed_candle,
        )
        if not kc_ready:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=self.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=self.SIGNAL_INDICATOR_MIN_WINDOW,
                available_indicator_window=kc_available,
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return None, criteria, "signal_stack_data_not_ready", None

        # Compute ATR early for use in Keltner proximity threshold
        atr_ser = calculate_atr(df)
        atr = atr_ser.iloc[-1]

        last5_low  = df["l"].iloc[-5:].min()
        last5_high = df["h"].iloc[-5:].max()
        kc_upper_last5 = kc[kc_upper_col].iloc[-5:]
        kc_lower_last5 = kc[kc_lower_col].iloc[-5:]

        if trend == "Uptrend":
            # CTI-v1.1 pullback: must breach OR come within proximity of lower band
            channel_width = float(kc_upper_last5.iloc[-1] - kc_lower_last5.iloc[-1])
            proximity_threshold = min(float(atr) * config.PULLBACK_KC_PROXIMITY_ATR, channel_width * 0.25)
            kc_ok = last5_low <= kc_lower_last5.min() or last5_low <= kc_lower_last5.min() + proximity_threshold
            kc_margin = float(kc_lower_last5.min() - last5_low)
        else:
            channel_width = float(kc_upper_last5.iloc[-1] - kc_lower_last5.iloc[-1])
            proximity_threshold = min(float(atr) * config.PULLBACK_KC_PROXIMITY_ATR, channel_width * 0.25)
            kc_ok = last5_high >= kc_upper_last5.max() or last5_high >= kc_upper_last5.max() - proximity_threshold
            kc_margin = float(last5_high - kc_upper_last5.max())

        keltner_strength = keltner_score(
            last5_low, last5_high, kc_lower_last5.min(), kc_upper_last5.max(), trend
        )

        # ── Layer 4: Candlestick (optional) ──────────────────────────────────
        patterns_df = calculate_candlestick_patterns(df)
        usable_patterns = patterns_df.dropna(how="all")
        if len(usable_patterns) < 5:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=self.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=5,
                available_indicator_window=len(usable_patterns),
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return None, criteria, "signal_stack_data_not_ready", None
        recent = patterns_df.iloc[-5:].dropna(how="all")
        identified = recent.columns[(recent != 0).any(axis=0)].tolist()

        if trend == "Uptrend":
            bullish_patterns = {"CDL_ENGULFING", "CDL_HAMMER"}
            candle_ok = bool(set(identified) & bullish_patterns)
        else:
            bearish_patterns = {"CDL_ENGULFING", "CDL_SHOOTINGSTAR", "CDL_SPINNINGTOP"}
            candle_ok = bool(set(identified) & bearish_patterns)

        candle_strength = candlestick_score(patterns_df, trend)

        # ── CTI-v1.1 Dual Path: Try Continuation first, then Pullback ──────
        # Continuation path: trend aligned, MACD supports, price on correct side of midline, structure OK
        # No StochRSI required for continuation

        continuation_ok = False
        continuation_criteria: list[CriterionResult] = []

        # Check continuation: MACD supports direction
        if trend == "Uptrend":
            macd_continuation_ok = macd_current > 0
            macd_continuation_margin = float(macd_current)
        else:
            macd_continuation_ok = macd_current < 0
            macd_continuation_margin = float(abs(macd_current))

        # Check continuation: price on correct side of Keltner midline
        midline = float(kc[kc_mid_col].iloc[-1])
        last_close = float(df["c"].iloc[-1])
        if trend == "Uptrend":
            kc_continuation_ok = last_close > midline
            kc_continuation_margin = last_close - midline
        else:
            kc_continuation_ok = last_close < midline
            kc_continuation_margin = midline - last_close

        # Check continuation: structure (last N candles show HH/HL or LH/LL)
        # Require at least one strictly progressive bar (not just flat/equal)
        structure_bars = config.CONTINUATION_STRUCTURE_BARS
        recent_highs = df["h"].iloc[-structure_bars:].tolist()
        recent_lows = df["l"].iloc[-structure_bars:].tolist()
        if trend == "Uptrend":
            has_higher_high = any(recent_highs[i] > recent_highs[i-1] for i in range(1, len(recent_highs)))
            has_higher_low = any(recent_lows[i] > recent_lows[i-1] for i in range(1, len(recent_lows)))
            structure_ok = has_higher_high or has_higher_low
        else:
            has_lower_high = any(recent_highs[i] < recent_highs[i-1] for i in range(1, len(recent_highs)))
            has_lower_low = any(recent_lows[i] < recent_lows[i-1] for i in range(1, len(recent_lows)))
            structure_ok = has_lower_high or has_lower_low

        # 5M trend alignment check for continuation (configurable)
        trend_5m_aligned = True
        if config.CONTINUATION_TREND_REQUIRE_5M:
            trend_5m_aligned = (trend == "Uptrend" and raw_lr_5m > 0) or (trend == "Downtrend" and raw_lr_5m < 0)

        continuation_all_pass = macd_continuation_ok and kc_continuation_ok and structure_ok and trend_5m_aligned

        continuation_criteria.extend([
            _criterion("macd", "signal_stack", float(macd_current), "supports direction", bool(macd_continuation_ok), macd_continuation_margin),
            _criterion("keltner", "signal_stack", {"close": last_close, "midline": midline}, "correct side of midline", bool(kc_continuation_ok), kc_continuation_margin),
            _criterion("structure", "signal_stack", {"recent_highs": recent_highs, "recent_lows": recent_lows}, "HH/HL or LH/LL", bool(structure_ok), None),
            _criterion("trend_5m", "signal_stack", raw_lr_5m, "aligned with bias" if config.CONTINUATION_TREND_REQUIRE_5M else "optional", bool(trend_5m_aligned), abs(raw_lr_5m), required=config.CONTINUATION_TREND_REQUIRE_5M),
        ])

        if continuation_all_pass:
            log.debug("%s continuation signal passed: macd=%s kc=%s structure=%s 5m=%s",
                      symbol, macd_continuation_ok, kc_continuation_ok, structure_ok, trend_5m_aligned)
            # Build continuation signal
            breakdown = {
                "stoch_rsi": 0.0,  # not used for continuation
                "macd": macd_strength,
                "keltner": keltner_strength,
                "candlestick": 0.0,  # not required for continuation
                "structure": 1.0 if structure_ok else 0.0,
            }

            lr_1h = filtered_lr_1h if self.shock_filter.enabled else raw_lr_1h
            lr_15 = filtered_lr_15m if self.shock_filter.enabled else raw_lr_15m
            lr_5 = filtered_lr_5m if self.shock_filter.enabled else raw_lr_5m
            trend_str = trend_score(lr_15, lr_5, trend,
                                    self.LR_15M_THRESHOLD, self.LR_5M_THRESHOLD)
            breakdown["trend"] = trend_str

            # Weighted confidence for continuation (no stoch/candle requirement)
            raw_confidence = (
                breakdown["macd"] * 0.35 +
                breakdown["keltner"] * 0.25 +
                breakdown["trend"] * 0.20 +
                breakdown["structure"] * 0.20
            )
            MIN_CONFIDENCE = 0.55
            if raw_confidence < MIN_CONFIDENCE:
                log.debug("%s continuation signal rejected: confidence %.1f%% < %.0f%% threshold",
                          symbol, raw_confidence * 100, MIN_CONFIDENCE * 100)
                continuation_criteria.append(_criterion("confidence", "confidence", raw_confidence, MIN_CONFIDENCE, False, raw_confidence - MIN_CONFIDENCE, "gte"))
                # Don't return here — fall through to try pullback
            else:
                continuation_criteria.append(_criterion("confidence", "confidence", raw_confidence, MIN_CONFIDENCE, True, raw_confidence - MIN_CONFIDENCE, "gte"))
                confidence = round(raw_confidence, 3)

                entry_price = df["c"].iloc[-1]
                setup_condition_first_true_at = closed_candle.time.isoformat() if closed_candle else None

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
                    lot_size=0.0,
                    risk_pct=config.RISK_PER_TRADE * 100,
                    confidence=confidence,
                    breakdown=breakdown,
                    trend_direction=trend,
                    patterns_found=[],
                    strategy="CTI-v1.1-continuation-test",
                    signal_type="continuation",
                    # Indicator snapshot
                    stochrsi_k=0.0,
                    stochrsi_d=0.0,
                    macd_line=macd_line,
                    macd_signal=macd_signal_val,
                    macd_histogram=macd_current,
                    kc_upper=float(kc_upper_last5.iloc[-1]),
                    kc_mid=midline,
                    kc_lower=float(kc_lower_last5.iloc[-1]),
                    # Shock diagnostics
                    raw_lr_1h=raw_lr_1h,
                    raw_lr_15m=raw_lr_15m,
                    raw_lr_5m=raw_lr_5m,
                    filtered_lr_1h=filtered_lr_1h,
                    filtered_lr_15m=filtered_lr_15m,
                    filtered_lr_5m=filtered_lr_5m,
                    trend_changed_after_filter=trend_changed_after_filter,
                    volatility_shock_detected=shock_result.detected if shock_result else False,
                    shock_timeframe=shock_result.timeframe if shock_result else None,
                    shock_candle_time=shock_result.candle_time if shock_result else None,
                    shock_true_range=shock_result.true_range if shock_result else None,
                    shock_atr=shock_result.atr if shock_result else None,
                    shock_atr_multiple=shock_result.atr_multiple if shock_result else None,
                    shock_lookback_bars=shock_result.lookback_bars if shock_result else 0,
                    shock_direction=shock_result.direction if shock_result else "none",
                    shock_suppression_until=shock_result.suppression_until if shock_result else None,
                    shock_suppression_candles_remaining=shock_result.suppression_candles_remaining if shock_result else 0,
                    market_validity_state="invalid" if (shock_result and shock_result.detected) else "valid",
                    market_validity_reason="market_invalid:volatility_shock" if (shock_result and shock_result.detected) else None,
                    lr_1h=lr_1h,
                    lr_15m=lr_15,
                    lr_5m=lr_5,
                    signal_price=round(entry_price, _price_decimals(entry_price)),
                    suggested_entry=round(entry_price, _price_decimals(entry_price)),
                    entry_tolerance=round(atr * config.SIGNAL_ENTRY_TOLERANCE_ATR, _price_decimals(entry_price)),
                    setup_condition_first_true_at=setup_condition_first_true_at,
                ), continuation_criteria, "emitted", confidence

        # ── Pullback Path ────────────────────────────────────────────────────
        # Fall through to existing pullback logic (relaxed Keltner + StochRSI)
        criteria.extend([
            _criterion("stoch_rsi", "signal_stack", {"k": float(k), "d": float(d)}, "pullback+cross", bool(stoch_ok), stoch_margin),
            _criterion("macd", "signal_stack", float(macd_current), "histogram improves", bool(macd_ok), macd_margin),
            _criterion("keltner", "signal_stack", {"last5_low": float(last5_low), "last5_high": float(last5_high)}, "band breach", bool(kc_ok), kc_margin),
            _criterion("candlestick", "confirmation", identified, "optional pattern", bool(candle_ok), None, required=False),
        ])

        # StochRSI, MACD, KC must all pass; candle is optional confirmation
        all_pass = stoch_ok and macd_ok and kc_ok
        if not all_pass:
            log.debug("%s pullback signal blocked: stoch=%s macd=%s kc=%s",
                      symbol, stoch_ok, macd_ok, kc_ok)
            return None, criteria, "criteria_failed", None

        # Layer 2 score breakdown
        breakdown = {
            "stoch_rsi": stoch_strength,
            "macd": macd_strength,
            "keltner": keltner_strength,
            "candlestick": candle_strength,
        }

        # Trend strength component. check_symbol passes these values from
        # _get_trend so scan cycles do not fetch H1/M15/M5 candles twice.
        # When trend_lr is provided (remote tuple API), use it directly.
        # Otherwise fetch the trend candles ourselves (legacy / standalone call).
        if trend_lr is None:
            candles_1h  = self.client.get_candles(symbol, "H1",  count=30)
            candles_15m = self.client.get_candles(symbol, "M15", count=60)
            candles_5m  = self.client.get_candles(symbol, "M5",  count=24)
            df_1h = candles_to_df(candles_1h)
            df_15 = candles_to_df(candles_15m)
            df_5  = candles_to_df(candles_5m)
            raw_lr_1h = calculate_linear_regression(df_1h, length=20).iloc[-1]
            raw_lr_15m = calculate_linear_regression(df_15, length=25).iloc[-1]
            raw_lr_5m = calculate_linear_regression(df_5,  length=14).iloc[-1]
            lr_1h = raw_lr_1h
            lr_15 = raw_lr_15m
            lr_5 = raw_lr_5m
        else:
            lr_1h, lr_15, lr_5 = trend_lr
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
            criteria.append(_criterion("confidence", "confidence", raw_confidence, MIN_CONFIDENCE, False, raw_confidence - MIN_CONFIDENCE, "gte"))
            return None, criteria, "confidence_failed", raw_confidence

        criteria.append(_criterion("confidence", "confidence", raw_confidence, MIN_CONFIDENCE, True, raw_confidence - MIN_CONFIDENCE, "gte"))

        confidence = round(raw_confidence, 3)

        # ── Risk / Pricing ───────────────────────────────────────────────────
        # atr already computed at Keltner layer
        entry_price = df["c"].iloc[-1]
        setup_condition_first_true_at = closed_candle.time.isoformat() if closed_candle else None

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
            strategy="CTI-v1.1-continuation-test",
            signal_type="pullback",
            # Indicator snapshot
            stochrsi_k=k,
            stochrsi_d=d,
            macd_line=macd_line,
            macd_signal=macd_signal_val,
            macd_histogram=macd_current,
            kc_upper=float(kc_upper_last5.iloc[-1]),
            kc_mid=float(kc[kc_mid_col].iloc[-1]),
            kc_lower=float(kc_lower_last5.iloc[-1]),
            # Shock diagnostics
            raw_lr_1h=raw_lr_1h,
            raw_lr_15m=raw_lr_15m,
            raw_lr_5m=raw_lr_5m,
            filtered_lr_1h=filtered_lr_1h,
            filtered_lr_15m=filtered_lr_15m,
            filtered_lr_5m=filtered_lr_5m,
            trend_changed_after_filter=trend_changed_after_filter,
            volatility_shock_detected=shock_result.detected if shock_result else False,
            shock_timeframe=shock_result.timeframe if shock_result else None,
            shock_candle_time=shock_result.candle_time if shock_result else None,
            shock_true_range=shock_result.true_range if shock_result else None,
            shock_atr=shock_result.atr if shock_result else None,
            shock_atr_multiple=shock_result.atr_multiple if shock_result else None,
            shock_lookback_bars=shock_result.lookback_bars if shock_result else 0,
            shock_direction=shock_result.direction if shock_result else "none",
            shock_suppression_until=shock_result.suppression_until if shock_result else None,
            shock_suppression_candles_remaining=shock_result.suppression_candles_remaining if shock_result else 0,
            market_validity_state="invalid" if (shock_result and shock_result.detected) else "valid",
            market_validity_reason="market_invalid:volatility_shock" if (shock_result and shock_result.detected) else None,
            lr_1h=lr_1h,
            lr_15m=lr_15,
            lr_5m=lr_5,
            signal_price=round(entry_price, _price_decimals(entry_price)),
            suggested_entry=round(entry_price, _price_decimals(entry_price)),
            entry_tolerance=round(atr * config.SIGNAL_ENTRY_TOLERANCE_ATR, _price_decimals(entry_price)),
            setup_condition_first_true_at=setup_condition_first_true_at,
            recent_candles=candles,
        ), criteria, "emitted", confidence

    def _indeterminate_diagnostic(
        self,
        symbol: str,
        reason: str,
        note: str,
        *,
        trend: Optional[str] = None,
        lr_1h: float = 0.0,
        lr_15: float = 0.0,
        lr_5: float = 0.0,
        criteria: Optional[list[CriterionResult]] = None,
        trend_decision: Optional[dict] = None,
        context: Optional[dict] = None,
    ) -> SignalDiagnostic:
        """Build an indeterminate diagnostic for incomplete data instead of raising."""
        data_criterion = _criterion(
            "signal_engine_data",
            "data_quality",
            context or {"note": note},
            "complete candles and indicators",
            None,
            None,
            quality="missing",
            diagnostic_state="missing_data",
            reason="signal_engine_data:missing",
            context=context or {"note": note},
        )
        return SignalDiagnostic(
            symbol=symbol,
            evaluated_at=datetime.now().astimezone().isoformat(),
            trend=trend,
            lr_1h=lr_1h,
            lr_15m=lr_15,
            lr_5m=lr_5,
            final_decision="indeterminate",
            decision_reason=reason,
            direction="BUY" if trend == "Uptrend" else ("SELL" if trend == "Downtrend" else "none"),
            criteria=(criteria or []) + [data_criterion],
            data_quality_notes=[note],
            threshold_version=get_threshold_version(),
            trend_decision=trend_decision,
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def check_symbol(self, symbol: str) -> tuple[Optional[Signal], Optional[str], float, float, float, SignalDiagnostic]:
        """Full pipeline: watchlist → shock detection → trend filter → signal stack.

        Returns (signal, trend, lr_1h, lr_15, lr_5, diagnostic).
        signal is None if symbol fails any filter.
        trend is None if no clear trend (flat) or suppressed by shock.
        """
        if symbol not in self.watchlist:
            log.debug("%s not on watchlist, skipping", symbol)
            diag = SignalDiagnostic(
                symbol=symbol,
                evaluated_at=datetime.now().astimezone().isoformat(),
                trend=None,
                lr_1h=0.0,
                lr_15m=0.0,
                lr_5m=0.0,
                final_decision="skipped",
                decision_reason="not_on_watchlist",
                criteria=[],
                threshold_version=get_threshold_version(),
            )
            return None, None, 0.0, 0.0, 0.0, diag

        # ── Fetch candles ────────────────────────────────────────────────────
        try:
            candles_1h  = self.client.get_candles(symbol, "H1",  count=30)
            candles_15m = self.client.get_candles(symbol, "M15", count=60)
            candles_5m  = self.client.get_candles(symbol, "M5",  count=24)
        except ProviderRequestError as exc:
            context = _provider_request_issue_context(exc, stage="trend_filter")
            note = f"trend data incomplete: {context['error_type']}"
            log.warning("%s provider data issue: %s", symbol, note)
            diag = self._indeterminate_diagnostic(symbol, context["error_type"], note, context=context)
            return None, None, 0.0, 0.0, 0.0, diag
        except (IndexError, KeyError, ValueError) as exc:
            context = _compact_data_issue_context(exc, stage="trend_filter", timeframe="mixed")
            note = f"trend data incomplete: {context['missing_input']}"
            log.warning("%s signal engine data quality issue: %s", symbol, note)
            diag = self._indeterminate_diagnostic(symbol, "missing_signal_engine_data", note, context=context)
            return None, None, 0.0, 0.0, 0.0, diag

        # ── Volatility Shock Detection (after data, before trend) ────────────
        shock_suppressed = False
        active_shock: Optional[ShockDetectionResult] = None
        shock_criteria: list[CriterionResult] = []
        if self.shock_filter.enabled:
            is_suppressed, active_shock, _ = self.shock_filter.check_symbol(
                symbol,
                {"H1": candles_1h, "M15": candles_15m, "M5": candles_5m},
            )
            if is_suppressed:
                shock_suppressed = True
                shock_criteria.append(_shock_diagnostic_criterion(active_shock))
                shock_criteria.append(_market_validity_criterion(
                    False, "market_invalid:volatility_shock", active_shock.to_dict()
                ))
                log.warning("%s suppressed by volatility shock (%s %s) until %s",
                            symbol, active_shock.rule, active_shock.timeframe,
                            active_shock.suppression_until)

        # ── Trend Filter (with raw + filtered LR) ───────────────────────────
        try:
            (
                trend,
                raw_lr_1h, raw_lr_15, raw_lr_5,
                filtered_lr_1h, filtered_lr_15, filtered_lr_5,
                excluded_1h, excluded_15m, excluded_5m,
                trend_decision,
            ) = self._get_trend(symbol, candles_by_tf={"H1": candles_1h, "M15": candles_15m, "M5": candles_5m})
        except ProviderRequestError as exc:
            context = _provider_request_issue_context(exc, stage="trend_filter")
            note = f"trend data incomplete: {context['error_type']}"
            log.warning("%s provider data issue: %s", symbol, note)
            diag = self._indeterminate_diagnostic(symbol, context["error_type"], note, context=context)
            return None, None, 0.0, 0.0, 0.0, diag
        except (IndexError, KeyError, ValueError) as exc:
            context = _compact_data_issue_context(exc, stage="trend_filter", timeframe="mixed")
            note = f"trend data incomplete: {context['missing_input']}"
            log.warning("%s signal engine data quality issue: %s", symbol, note)
            diag = self._indeterminate_diagnostic(symbol, "missing_signal_engine_data", note, context=context)
            return None, None, 0.0, 0.0, 0.0, diag

        trend_changed_after_filter = False
        if self.shock_filter.enabled:
            raw_trend = classify_trend_decision(
                raw_lr_1h, raw_lr_15, raw_lr_5,
                self.LR_1H_THRESHOLD, self.LR_15M_THRESHOLD, self.LR_5M_THRESHOLD,
            )
            trend_changed_after_filter = raw_trend["trend_result"] != trend_decision["trend_result"]

        lr_1h = filtered_lr_1h if self.shock_filter.enabled else raw_lr_1h
        lr_15 = filtered_lr_15 if self.shock_filter.enabled else raw_lr_15
        lr_5 = filtered_lr_5 if self.shock_filter.enabled else raw_lr_5

        trend_criteria = [
            _criterion("trend_1h", "trend", lr_1h, self.LR_1H_THRESHOLD, abs(lr_1h) >= self.LR_1H_THRESHOLD, abs(lr_1h) - self.LR_1H_THRESHOLD, "abs_gte"),
            _criterion("trend_15m", "trend", lr_15, self.LR_15M_THRESHOLD, abs(lr_15) >= self.LR_15M_THRESHOLD, abs(lr_15) - self.LR_15M_THRESHOLD, "abs_gte"),
            _criterion("trend_5m", "trend", lr_5, self.LR_5M_THRESHOLD, abs(lr_5) >= self.LR_5M_THRESHOLD, abs(lr_5) - self.LR_5M_THRESHOLD, "abs_gte"),
        ]

        if shock_suppressed:
            # CTI-v1.1: Only suppress if shock changed the trend AND shock direction matches signal direction
            # This preserves continuation signals when shock direction conflicts with trend direction
            signal_direction = "up" if trend == "Uptrend" else "down"
            if trend_changed_after_filter and active_shock and active_shock.direction == signal_direction:
                log.debug("%s suppressed by volatility shock (direction=%s, changed_trend=%s), skipping signal stack",
                          symbol, active_shock.direction, trend_changed_after_filter)
                diag = SignalDiagnostic(
                symbol=symbol,
                evaluated_at=datetime.now().astimezone().isoformat(),
                trend=trend,
                lr_1h=lr_1h,
                lr_15m=lr_15,
                lr_5m=lr_5,
                raw_lr_1h=raw_lr_1h,
                raw_lr_15m=raw_lr_15,
                raw_lr_5m=raw_lr_5,
                filtered_lr_1h=filtered_lr_1h,
                filtered_lr_15m=filtered_lr_15,
                filtered_lr_5m=filtered_lr_5,
                trend_changed_after_filter=trend_changed_after_filter,
                volatility_shock_detected=True,
                shock_timeframe=active_shock.timeframe if active_shock else None,
                shock_candle_time=active_shock.candle_time if active_shock else None,
                shock_true_range=active_shock.true_range if active_shock else None,
                shock_atr=active_shock.atr if active_shock else None,
                shock_atr_multiple=active_shock.atr_multiple if active_shock else None,
                shock_lookback_bars=active_shock.lookback_bars if active_shock else 0,
                shock_direction=active_shock.direction if active_shock else "none",
                shock_suppression_until=active_shock.suppression_until if active_shock else None,
                shock_suppression_candles_remaining=active_shock.suppression_candles_remaining if active_shock else 0,
                market_validity_state="invalid",
                market_validity_reason="market_invalid:volatility_shock",
                final_decision="skipped",
                decision_reason="market_invalid:volatility_shock",
                direction="BUY" if trend == "Uptrend" else ("SELL" if trend == "Downtrend" else "none"),
                criteria=trend_criteria + shock_criteria,
                threshold_version=get_threshold_version(),
                trend_decision=trend_decision,
            )
                return None, trend, lr_1h, lr_15, lr_5, diag
            # else: shock detected but direction mismatch or trend not changed → proceed with signal stack

        if trend is None:
            log.debug("%s no trend, skipping", symbol)
            diag = SignalDiagnostic(
                symbol=symbol,
                evaluated_at=datetime.now().astimezone().isoformat(),
                trend=trend,
                lr_1h=lr_1h,
                lr_15m=lr_15,
                lr_5m=lr_5,
                raw_lr_1h=raw_lr_1h,
                raw_lr_15m=raw_lr_15,
                raw_lr_5m=raw_lr_5,
                filtered_lr_1h=filtered_lr_1h,
                filtered_lr_15m=filtered_lr_15,
                filtered_lr_5m=filtered_lr_5,
                trend_changed_after_filter=trend_changed_after_filter,
                volatility_shock_detected=active_shock.detected if active_shock else False,
                shock_timeframe=active_shock.timeframe if active_shock else None,
                shock_candle_time=active_shock.candle_time if active_shock else None,
                shock_true_range=active_shock.true_range if active_shock else None,
                shock_atr=active_shock.atr if active_shock else None,
                shock_atr_multiple=active_shock.atr_multiple if active_shock else None,
                shock_lookback_bars=active_shock.lookback_bars if active_shock else 0,
                shock_direction=active_shock.direction if active_shock else "none",
                shock_suppression_until=active_shock.suppression_until if active_shock else None,
                shock_suppression_candles_remaining=active_shock.suppression_candles_remaining if active_shock else 0,
                market_validity_state="invalid" if (active_shock and active_shock.detected) else "valid",
                market_validity_reason="market_invalid:volatility_shock" if (active_shock and active_shock.detected) else None,
                final_decision="skipped",
                decision_reason="no_trend",
                criteria=trend_criteria + (shock_criteria if shock_suppressed else []),
                threshold_version=get_threshold_version(),
                trend_decision=trend_decision,
            )
            return None, trend, lr_1h, lr_15, lr_5, diag

        # ── Record trend evaluation for chop filter ──────────────────────────
        self._record_trend_evaluation(symbol, trend)

        # ── Chop / Regime Filter checks (after trend, before signal stack) ───
        chop_blocked, chop_criteria, chop_reason, chop_context = self._check_chop_filters(
            symbol, trend, lr_15,
        )
        if chop_blocked:
            log.debug("%s blocked by chop filter: %s", symbol, chop_reason)
            diag = SignalDiagnostic(
                symbol=symbol,
                evaluated_at=datetime.now().astimezone().isoformat(),
                trend=trend,
                lr_1h=lr_1h,
                lr_15m=lr_15,
                lr_5m=lr_5,
                raw_lr_1h=raw_lr_1h,
                raw_lr_15m=raw_lr_15,
                raw_lr_5m=raw_lr_5,
                filtered_lr_1h=filtered_lr_1h,
                filtered_lr_15m=filtered_lr_15,
                filtered_lr_5m=filtered_lr_5,
                trend_changed_after_filter=trend_changed_after_filter,
                volatility_shock_detected=active_shock.detected if active_shock else False,
                shock_timeframe=active_shock.timeframe if active_shock else None,
                shock_candle_time=active_shock.candle_time if active_shock else None,
                shock_true_range=active_shock.true_range if active_shock else None,
                shock_atr=active_shock.atr if active_shock else None,
                shock_atr_multiple=active_shock.atr_multiple if active_shock else None,
                shock_lookback_bars=active_shock.lookback_bars if active_shock else 0,
                shock_direction=active_shock.direction if active_shock else "none",
                shock_suppression_until=active_shock.suppression_until if active_shock else None,
                shock_suppression_candles_remaining=active_shock.suppression_candles_remaining if active_shock else 0,
                market_validity_state="invalid",
                market_validity_reason=chop_reason,
                final_decision="skipped",
                decision_reason=chop_reason,
                direction="BUY" if trend == "Uptrend" else "SELL",
                criteria=trend_criteria + chop_criteria + (shock_criteria if shock_suppressed else []),
                threshold_version=get_threshold_version(),
                trend_decision=trend_decision,
            )
            return None, trend, lr_1h, lr_15, lr_5, diag

        # ── Cooldown check ───────────────────────────────────────────────────
        cooldown_key = f"{symbol}:{trend}"
        last_signal_ts = self._cooldown.get(cooldown_key, 0.0)
        if time.time() - last_signal_ts < self.SIGNAL_COOLDOWN_SECONDS:
            log.debug("%s in cooldown (%.0fs remaining), skipping", symbol,
                      self.SIGNAL_COOLDOWN_SECONDS - (time.time() - last_signal_ts))
            remaining = self.SIGNAL_COOLDOWN_SECONDS - (time.time() - last_signal_ts)
            diag = SignalDiagnostic(
                symbol=symbol,
                evaluated_at=datetime.now().astimezone().isoformat(),
                trend=trend,
                lr_1h=lr_1h,
                lr_15m=lr_15,
                lr_5m=lr_5,
                raw_lr_1h=raw_lr_1h,
                raw_lr_15m=raw_lr_15,
                raw_lr_5m=raw_lr_5,
                filtered_lr_1h=filtered_lr_1h,
                filtered_lr_15m=filtered_lr_15,
                filtered_lr_5m=filtered_lr_5,
                trend_changed_after_filter=trend_changed_after_filter,
                final_decision="skipped",
                decision_reason="cooldown",
                direction="BUY" if trend == "Uptrend" else "SELL",
                criteria=trend_criteria + [_criterion("cooldown", "timing", remaining, 0, False, -remaining)],
                threshold_version=get_threshold_version(),
                trend_decision=trend_decision,
            )
            return None, trend, lr_1h, lr_15, lr_5, diag

        try:
            signal, criteria, reason, confidence = self._get_signal(
                symbol, trend,
                (lr_1h, lr_15, lr_5),
                raw_lr_1h=raw_lr_1h, raw_lr_15m=raw_lr_15, raw_lr_5m=raw_lr_5,
                filtered_lr_1h=filtered_lr_1h, filtered_lr_15m=filtered_lr_15, filtered_lr_5m=filtered_lr_5,
                trend_changed_after_filter=trend_changed_after_filter,
                shock_result=active_shock,
            )
        except ProviderRequestError as exc:
            context = _provider_request_issue_context(exc, stage="signal_stack")
            note = f"signal stack provider data incomplete: {context['error_type']}"
            log.warning("%s provider data issue: %s", symbol, note)
            criteria = trend_criteria
            diag = self._indeterminate_diagnostic(
                symbol,
                context["error_type"],
                note,
                trend=trend,
                lr_1h=lr_1h,
                lr_15=lr_15,
                lr_5=lr_5,
                criteria=criteria,
                trend_decision=trend_decision,
                context=context,
            )
            return None, trend, lr_1h, lr_15, lr_5, diag
        except (IndexError, KeyError, ValueError) as exc:
            context = _compact_data_issue_context(exc, stage="signal_stack", timeframe="M5")
            note = f"signal stack data incomplete: {context['missing_input']}"
            log.warning("%s signal engine data quality issue: %s", symbol, note)
            criteria = trend_criteria
            diag = self._indeterminate_diagnostic(
                symbol,
                "missing_signal_engine_data",
                note,
                trend=trend,
                lr_1h=lr_1h,
                lr_15=lr_15,
                lr_5=lr_5,
                criteria=criteria,
                trend_decision=trend_decision,
                context=context,
            )
            return None, trend, lr_1h, lr_15, lr_5, diag

        if signal:
            # Record signal timestamp for cooldown
            self._cooldown[cooldown_key] = time.time()
            # Record signal direction for chop filter
            signal_dir = "BUY" if trend == "Uptrend" else "SELL"
            self._record_signal_direction(symbol, signal_dir)

        diag = SignalDiagnostic(
            symbol=symbol,
            evaluated_at=datetime.now().astimezone().isoformat(),
            trend=trend,
            lr_1h=lr_1h,
            lr_15m=lr_15,
            lr_5m=lr_5,
            raw_lr_1h=raw_lr_1h,
            raw_lr_15m=raw_lr_15,
            raw_lr_5m=raw_lr_5,
            filtered_lr_1h=filtered_lr_1h,
            filtered_lr_15m=filtered_lr_15,
            filtered_lr_5m=filtered_lr_5,
            trend_changed_after_filter=trend_changed_after_filter,
            volatility_shock_detected=active_shock.detected if active_shock else False,
            shock_timeframe=active_shock.timeframe if active_shock else None,
            shock_candle_time=active_shock.candle_time if active_shock else None,
            shock_true_range=active_shock.true_range if active_shock else None,
            shock_atr=active_shock.atr if active_shock else None,
            shock_atr_multiple=active_shock.atr_multiple if active_shock else None,
            shock_lookback_bars=active_shock.lookback_bars if active_shock else 0,
            shock_direction=active_shock.direction if active_shock else "none",
            shock_suppression_until=active_shock.suppression_until if active_shock else None,
            shock_suppression_candles_remaining=active_shock.suppression_candles_remaining if active_shock else 0,
            market_validity_state="invalid" if (active_shock and active_shock.detected) else "valid",
            market_validity_reason="market_invalid:volatility_shock" if (active_shock and active_shock.detected) else None,
            final_decision=(
                "emitted"
                if signal
                else (
                    "skipped"
                    if str(reason).startswith("candle_close_gate:waiting_for_close")
                    else (
                        "indeterminate"
                        if reason in {
                            "missing_candle_time",
                            "missing_candle_data",
                            "missing_signal_engine_data",
                            "signal_stack_data_not_ready",
                        }
                        else "rejected"
                    )
                )
            ),
            decision_reason=reason,
            direction=("BUY" if trend == "Uptrend" else "SELL"),
            confidence=confidence if confidence is not None else (signal.confidence if signal else None),
            criteria=trend_criteria + criteria,
            threshold_version=get_threshold_version(),
            trend_decision=trend_decision,
        )
        return signal, trend, lr_1h, lr_15, lr_5, diag


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

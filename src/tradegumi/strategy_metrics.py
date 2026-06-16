"""Strategy diagnostic storage and aggregation.

The signal journal records emitted signals. This module records every evaluated
opportunity so quiet periods can be inspected without changing signal behavior.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from tradegumi import config
from tradegumi.persistence import get_db, DBBackend
from tradegumi.persistence.redis import get_cache

DATA_DIR = Path(__file__).parent / "data"
STATE_FILE = DATA_DIR / "strategy_metrics.json"

VALID_DECISIONS = {"emitted", "rejected", "skipped", "indeterminate"}
VALID_DATA_QUALITY = {"complete", "missing", "malformed", "not_applicable"}
INDETERMINATE_REASONS = {
    "api_error",
    "api_timeout",
    "engine_error",
    "incomplete_diagnostics",
    "missing_candle_data",
    "missing_candle_time",
    "missing_signal_engine_data",
    "signal_stack_data_not_ready",
    "oanda_candle_fetch_failed",
    "oanda_gateway_timeout",
    "oanda_rate_limited",
    "oanda_request_failed",
    "oanda_response_malformed",
}
_LEGACY_CRITERION_NAMES = {"singal_engine_data": "signal_engine_data"}


def _canonical_criterion_name(name: str) -> str:
    """Return the stable diagnostic criterion name used for metrics aggregation."""
    return _LEGACY_CRITERION_NAMES.get(str(name), str(name))


def _stored_criterion_names(canonical: str) -> list[str]:
    """Return every stored ``criterion_name`` spelling that maps to ``canonical``.

    Criterion names are canonicalized on read (see ``_canonical_criterion_name``),
    so a filter expressed in canonical terms must also match any legacy spelling
    persisted before the canonical name existed. Used to build the criterion
    drilldown filter (``get_opportunities(criterion=...)``).
    """
    names = {str(canonical)}
    for raw, canon in _LEGACY_CRITERION_NAMES.items():
        if canon == canonical:
            names.add(raw)
    return sorted(names)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        dt = datetime.fromisoformat(normalized + "T00:00:00")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_date_only(value: str | datetime) -> bool:
    """Return true when a user-supplied range boundary is a bare calendar date."""
    return isinstance(value, str) and len(value.strip()) == 10 and value.strip()[4] == "-" and value.strip()[7] == "-"


def _normalize_range_bounds(start: str | datetime, end: str | datetime) -> tuple[str, str]:
    """Normalize metrics ranges to [start, end) while including a date-only end day.

    The UI sends date-only values for calendar filters. SQLite queries remain
    exclusive on the upper bound, so a selected end date like 2026-05-06 becomes
    2026-05-07T00:00:00 internally.
    """
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if _is_date_only(end):
        end_dt += timedelta(days=1)
    return start_dt.isoformat(), end_dt.isoformat()


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


@dataclass
class CriterionResult:
    criterion_name: str
    layer: str
    measured_value: Any = None
    threshold_value: Any = None
    threshold_operator: str = "boolean"
    passed: Optional[bool] = None
    expected_pass: Optional[bool] = None   # computed from measured, threshold, operator
    pass_mismatch: bool = False            # True when expected_pass != passed
    margin: Optional[float] = None
    normalized_margin: Optional[float] = None
    required: bool = True
    blocked_signal: bool = False
    data_quality: str = "complete"
    id: Optional[int] = None
    opportunity_id: Optional[str] = None
    diagnostic_state: str = "evaluated"
    reason: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluatedOpportunity:
    id: str
    evaluated_at: str
    symbol: str
    timeframe: str = "M5"
    mode: str = "alert_only"
    strategy: str = "CTI-v1"
    signal_type: str = "pullback"  # "pullback" or "continuation"
    direction: str = "none"
    trend: str = "unknown"
    final_decision: str = "indeterminate"
    decision_reason: str = "unknown"
    confidence: Optional[float] = None
    failed_criteria_count: int = 0
    near_miss: bool = False
    data_complete: bool = True
    data_quality_notes: list[str] = field(default_factory=list)
    threshold_version: str = "unknown"
    created_at: str = field(default_factory=_now_iso)
    criteria: list[CriterionResult] = field(default_factory=list)
    first_blocker: Optional[str] = None
    all_blockers: list[str] = field(default_factory=list)
    blocking_layer: Optional[str] = None
    trend_decision: Optional[dict[str, Any]] = None
    pipeline_state: Optional[str] = None
    near_miss_reason: Optional[str] = None
    threshold_version_unknown_reason: Optional[str] = None
    usable_for_strategy_stats: Optional[bool] = None
    stats_exclusion_reason: Optional[str] = None
    # Volatility shock + filtered LR fields
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
    raw_lr_1h: Optional[float] = None
    raw_lr_15m: Optional[float] = None
    raw_lr_5m: Optional[float] = None
    filtered_lr_1h: Optional[float] = None
    filtered_lr_15m: Optional[float] = None
    filtered_lr_5m: Optional[float] = None
    trend_changed_after_filter: bool = False
    market_validity_state: str = "valid"
    market_validity_reason: Optional[str] = None

    def to_dict(self, include_criteria: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if include_criteria:
            data["criteria"] = [c.to_dict() for c in self.criteria]
        else:
            data.pop("criteria", None)
        lifecycle_role = "management" if self.signal_type == "continuation" else "entry" if self.signal_type in {"pullback", "high_value_pullback"} else "legacy_signal"
        data.setdefault("lifecycle_role", lifecycle_role)
        data.setdefault("trade_id", None)
        data.setdefault("entry_signal_id", None)
        data.setdefault("entry_signal_type", None if lifecycle_role == "management" else self.signal_type)
        data.setdefault("management_event_id", None)
        data.setdefault("source_signal_id", None)
        data.setdefault("source_signal_type", "continuation" if lifecycle_role == "management" else None)
        data.setdefault("current_stop_loss", None)
        data.setdefault("current_take_profit", None)
        data.setdefault("managed_exit_reason", None)
        data.setdefault("managed_result_category", None)
        data.setdefault("captured_r", None)
        data.setdefault("managed_original_tp_result", None)
        data.setdefault("managed_result_delta", None)
        return data


@dataclass
class CriterionSummary:
    criterion_name: str
    evaluated_count: int
    pass_count: int
    fail_count: int
    pass_rate: float
    fail_rate: float
    near_miss_contribution: int
    average_failure_margin: Optional[float]
    incomplete_count: int
    # Pipeline layer the criterion belongs to (e.g. "signal_stack"); surfaced in
    # the criterion drilldown header (spec 022 FR-012).
    layer: str = ""


@dataclass
class BlockerSummary:
    criterion_name: str
    blocked_count: int
    frequency_component: float
    margin_component: float
    quality_component: float
    combined_score: float
    example_opportunity_ids: list[str]


@dataclass
class DiagnosticSummary:
    start: str
    end: str
    total_evaluated: int
    emitted_count: int
    rejected_count: int
    skipped_count: int
    indeterminate_count: int
    near_miss_count: int
    trade_opportunity_count: int = 0
    stats_excluded_count: int = 0
    stats_unknown_eligibility_count: int = 0
    stats_exclusion_counts: dict[str, int] = field(default_factory=dict)
    total_prime_suppressed_signals: int = 0
    prime_suppressed_signals_by_symbol: dict[str, int] = field(default_factory=dict)
    prime_suppressed_same_direction_count: int = 0
    prime_suppressed_opposite_direction_count: int = 0
    prime_invalidated_by_prime_count: int = 0
    inferred_tp_close_count: int = 0
    inferred_sl_close_count: int = 0
    ambiguous_prime_close_count: int = 0
    criterion_summaries: list[CriterionSummary] = field(default_factory=list)
    top_blockers: list[BlockerSummary] = field(default_factory=list)
    first_blocker: Optional[str] = None   # criterion_name of the first blocker
    all_blockers: list[str] = field(default_factory=list)  # all blocking criterion_names
    blocking_layer: Optional[str] = None  # layer of the first blocker
    threshold_version_counts: dict[str, int] = field(default_factory=dict)
    strategy_counts: dict[str, int] = field(default_factory=dict)
    signal_type_counts: dict[str, int] = field(default_factory=dict)
    pullback_summary: dict[str, Any] = field(default_factory=dict)
    managed_lifecycle_summary: dict[str, Any] = field(default_factory=dict)
    pullback_entries_opened: int = 0
    continuation_management_events_observed: int = 0
    continuation_management_events_accepted: int = 0
    continuation_management_events_rejected: int = 0
    tp_extension_count: int = 0
    sl_tighten_count: int = 0
    break_even_move_count: int = 0
    profit_protected_sl_win_count: int = 0
    opposite_direction_continuation_warning_count: int = 0
    average_r_captured: Optional[float] = None
    max_favorable_excursion_before_exit: Optional[float] = None
    managed_vs_original_result_delta: dict[str, int] = field(default_factory=dict)
    threshold_version_unknown_reasons: dict[str, int] = field(default_factory=dict)
    near_miss_reason_counts: dict[str, int] = field(default_factory=dict)
    pipeline_funnel: dict[str, int] = field(default_factory=dict)
    data_quality_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["criterion_summaries"] = [asdict(c) for c in self.criterion_summaries]
        data["top_blockers"] = [asdict(b) for b in self.top_blockers]
        return data


@dataclass
class ComparisonPeriod:
    baseline: DiagnosticSummary
    comparison: DiagnosticSummary
    deltas: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline.to_dict(),
            "comparison": self.comparison.to_dict(),
            "deltas": self.deltas,
        }


def _compute_threshold_pass(measured: Any, threshold: Any, operator: str) -> Optional[bool]:
    """Compute expected_pass from measured, threshold, and operator."""
    if operator == "boolean":
        return bool(measured) if measured is not None else None
    if measured is None:
        return None
    try:
        measured_f = float(measured)
    except (TypeError, ValueError):
        return None
    try:
        threshold_f = float(threshold)
    except (TypeError, ValueError):
        return None
    if operator == "gte":
        return measured_f >= threshold_f
    if operator == "lte":
        return measured_f <= threshold_f
    if operator == "gt":
        return measured_f > threshold_f
    if operator == "lt":
        return measured_f < threshold_f
    if operator == "abs_gte":
        return abs(measured_f) >= threshold_f
    if operator == "abs_lte":
        return abs(measured_f) <= threshold_f
    if operator == "eq":
        return measured_f == threshold_f
    return None


def validate_opportunity(opportunity: EvaluatedOpportunity) -> EvaluatedOpportunity:
    """Normalize one diagnostic opportunity before persistence and aggregation."""
    if opportunity.final_decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid final_decision: {opportunity.final_decision}")
    if not opportunity.symbol:
        raise ValueError("symbol is required")
    if not opportunity.evaluated_at:
        raise ValueError("evaluated_at is required")
    if not opportunity.decision_reason:
        raise ValueError("decision_reason is required")
    if opportunity.decision_reason in INDETERMINATE_REASONS:
        opportunity.final_decision = "indeterminate"

    failed_required = 0
    complete = True
    notes = list(opportunity.data_quality_notes)
    for criterion in opportunity.criteria:
        if criterion.data_quality not in VALID_DATA_QUALITY:
            raise ValueError(f"Invalid data_quality: {criterion.data_quality}")
        if criterion.data_quality in {"missing", "malformed"}:
            complete = False
            notes.append(f"{criterion.criterion_name}:{criterion.data_quality}")
            if criterion.required and opportunity.final_decision == "indeterminate":
                criterion.blocked_signal = True
        # Compute expected_pass and pass_mismatch
        criterion.expected_pass = _compute_threshold_pass(
            criterion.measured_value, criterion.threshold_value, criterion.threshold_operator
        )
        if criterion.expected_pass is not None and criterion.passed is not None:
            criterion.pass_mismatch = criterion.expected_pass != criterion.passed
        if criterion.required and criterion.passed is False:
            failed_required += 1
            if opportunity.final_decision in {"rejected", "skipped"}:
                criterion.blocked_signal = True

    if opportunity.final_decision in {"rejected", "skipped", "indeterminate"}:
        blockers = [c for c in opportunity.criteria if c.blocked_signal]
        blockers.sort(key=lambda c: _criterion_pipeline_order(c))  # stable pipeline order
        opportunity.all_blockers = [_criterion_blocker_name(c) for c in blockers]
        if blockers:
            opportunity.first_blocker = _criterion_blocker_name(blockers[0])
            opportunity.blocking_layer = blockers[0].layer
        elif opportunity.decision_reason == "no_trend":
            no_trend_reason = _trend_no_trend_reason(opportunity.trend_decision)
            blocker = f"trend:{no_trend_reason}"
            opportunity.first_blocker = blocker
            opportunity.all_blockers = [blocker]
            opportunity.blocking_layer = "trend"
        elif opportunity.decision_reason not in {"market_closed", "rollover"}:
            blocker = opportunity.decision_reason or "unknown"
            opportunity.first_blocker = blocker
            opportunity.all_blockers = [blocker]
            opportunity.blocking_layer = _layer_from_reason(blocker)

    opportunity.failed_criteria_count = failed_required
    opportunity.pipeline_state = opportunity.pipeline_state or _classify_pipeline_state(opportunity)
    if opportunity.threshold_version == "unknown" and not opportunity.threshold_version_unknown_reason:
        opportunity.threshold_version_unknown_reason = "legacy_or_missing_threshold_version"
    near_miss, near_miss_reason = _classify_near_miss(opportunity, failed_required)
    opportunity.near_miss = near_miss
    opportunity.near_miss_reason = near_miss_reason
    opportunity.data_complete = complete and opportunity.data_complete
    opportunity.data_quality_notes = sorted(set(notes))
    return opportunity


def _criterion_pipeline_order(criterion: CriterionResult) -> tuple[int, str]:
    """Return a deterministic order that follows the signal pipeline."""
    layer_order = {
        "trend": 10,
        "data_quality": 20,
        "signal_engine": 20,
        "timing": 30,
        "signal_stack": 40,
        "confirmation": 50,
        "confidence": 60,
        "risk": 70,
    }
    return layer_order.get(criterion.layer, 90), criterion.criterion_name


def _criterion_blocker_name(criterion: CriterionResult) -> str:
    """Return the stable blocker name exported for a blocking criterion."""
    if criterion.reason:
        return criterion.reason
    if criterion.criterion_name == "signal_engine_data" and criterion.data_quality in {"missing", "malformed"}:
        return f"signal_engine_data:{criterion.data_quality}"
    if criterion.criterion_name == "candle_close_gate":
        return "candle_close_gate:failed"
    return criterion.criterion_name


def _classify_pipeline_state(opportunity: EvaluatedOpportunity) -> str:
    """Classify an opportunity into the highest-signal stage reached."""
    blockers = set(opportunity.all_blockers)
    if opportunity.final_decision == "emitted":
        return "signal_emitted"
    if opportunity.decision_reason == "no_trend" or any(b.startswith("trend:") for b in blockers):
        return "trend_skipped"
    if any(b.startswith("signal_engine_data:") for b in blockers):
        return "trend_candidate_signal_data_missing"
    if any(b == "candle_close_gate:waiting_for_close" for b in blockers):
        return "trend_candidate_candle_close_waiting"
    if any(b.startswith("candle_close_gate:") for b in blockers):
        return "trend_candidate_candle_close_failed"
    if opportunity.final_decision == "rejected":
        return "signal_rejected"
    if opportunity.final_decision == "indeterminate":
        return "indeterminate"
    if opportunity.final_decision == "skipped":
        return "trend_skipped"
    return "signal_rules_evaluated"


def _classify_near_miss(opportunity: EvaluatedOpportunity, failed_required: int) -> tuple[bool, Optional[str]]:
    """Return whether the rejected opportunity satisfies the documented near-miss rule."""
    if opportunity.final_decision != "rejected" or failed_required != 1:
        return False, None
    blocking = [c for c in opportunity.criteria if c.blocked_signal]
    if len(blocking) != 1:
        return False, None
    blocker_name = _criterion_blocker_name(blocking[0])
    if blocker_name == "candle_close_gate:waiting_for_close":
        return False, None
    return True, blocker_name


def _trend_no_trend_reason(trend_decision: Optional[dict[str, Any]]) -> str:
    """Return the normalized no-trend reason from a nested trend diagnostic."""
    if not trend_decision:
        return "unknown"
    output = trend_decision.get("trend_classification_output") or {}
    return str(trend_decision.get("no_trend_reason") or output.get("no_trend_reason") or "unknown")


def _layer_from_reason(reason: str) -> str:
    """Map legacy skip/reject reason strings to a summary blocking layer."""
    if reason.startswith("trend:") or reason == "no_trend":
        return "trend"
    if reason in {"engine_error", "api_error", "api_timeout"}:
        return "engine"
    if reason.startswith("oanda_"):
        return "data_quality"
    if reason.startswith("signal_engine_data:"):
        return "data_quality"
    if reason in {"missing_candle_data", "missing_candle_time", "missing_signal_engine_data", "signal_stack_data_not_ready", "incomplete_diagnostics"}:
        return "data_quality"
    if reason.startswith("candle_close_gate:"):
        return "timing"
    if reason in {"risk", "risk_blocked"}:
        return "risk"
    if reason in {"cooldown", "candle_gate"}:
        return "entry"
    return "entry"


_last_prune_at: Optional[datetime] = None


def record_opportunity(opportunity: EvaluatedOpportunity, db: Optional[DBBackend] = None) -> EvaluatedOpportunity:
    opportunity = validate_opportunity(opportunity)
    db = db or get_db()
    _record_opportunity_db(opportunity, db)
    get_cache().invalidate_strategy_summary(
        symbol=opportunity.symbol,
        strategy=opportunity.strategy,
        signal_type=opportunity.signal_type,
    )
    _prune_retention_if_due(db)
    return opportunity


def _prune_retention_if_due(db: DBBackend, interval: timedelta = timedelta(hours=1)) -> int:
    """Prune old diagnostics at most once per interval (process-wide throttle)."""
    global _last_prune_at
    now = datetime.now(timezone.utc)
    if _last_prune_at is not None and now - _last_prune_at < interval:
        return 0
    removed = prune_retention(db=db)
    _last_prune_at = now
    return removed


def prune_retention(days: Optional[int] = None, db: Optional[DBBackend] = None) -> int:
    """Delete diagnostics older than the retention window (criteria cascade)."""
    days = days or config.STRATEGY_METRICS_RETENTION_DAYS
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    db = db or get_db()
    cur = db.execute("DELETE FROM evaluated_opportunities WHERE evaluated_at < ?", (cutoff,))
    try:
        return int(cur.rowcount) if cur is not None and cur.rowcount is not None else 0
    except Exception:
        return 0


def _row_to_opportunity(row: Any, criteria: list[CriterionResult]) -> EvaluatedOpportunity:
    return EvaluatedOpportunity(
        id=row["id"],
        evaluated_at=row["evaluated_at"],
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        mode=row["mode"],
        strategy=row["strategy"],
        signal_type=row["signal_type"] if "signal_type" in row.keys() else "pullback",
        direction=row["direction"],
        trend=row["trend"],
        final_decision=row["final_decision"],
        decision_reason=row["decision_reason"],
        confidence=row["confidence"],
        failed_criteria_count=row["failed_criteria_count"],
        near_miss=bool(row["near_miss"]),
        data_complete=bool(row["data_complete"]),
        data_quality_notes=json.loads(row["data_quality_notes"] or "[]"),
        threshold_version=row["threshold_version"],
        created_at=row["created_at"],
        criteria=criteria,
        first_blocker=row["first_blocker"] if "first_blocker" in row.keys() else None,
        all_blockers=json.loads(row["all_blockers"] or "[]") if "all_blockers" in row.keys() else [],
        blocking_layer=row["blocking_layer"] if "blocking_layer" in row.keys() else None,
        trend_decision=json.loads(row["trend_decision"]) if "trend_decision" in row.keys() and row["trend_decision"] else None,
        pipeline_state=row["pipeline_state"] if "pipeline_state" in row.keys() else None,
        near_miss_reason=row["near_miss_reason"] if "near_miss_reason" in row.keys() else None,
        threshold_version_unknown_reason=(
            row["threshold_version_unknown_reason"] if "threshold_version_unknown_reason" in row.keys() else None
        ),
        usable_for_strategy_stats=(
            None if "usable_for_strategy_stats" not in row.keys() or row["usable_for_strategy_stats"] is None else bool(row["usable_for_strategy_stats"])
        ),
        stats_exclusion_reason=row["stats_exclusion_reason"] if "stats_exclusion_reason" in row.keys() else None,
        # Volatility shock + filtered LR fields
        volatility_shock_detected=bool(row["volatility_shock_detected"]) if "volatility_shock_detected" in row.keys() else False,
        shock_timeframe=row["shock_timeframe"] if "shock_timeframe" in row.keys() else None,
        shock_candle_time=row["shock_candle_time"] if "shock_candle_time" in row.keys() else None,
        shock_true_range=row["shock_true_range"] if "shock_true_range" in row.keys() else None,
        shock_atr=row["shock_atr"] if "shock_atr" in row.keys() else None,
        shock_atr_multiple=row["shock_atr_multiple"] if "shock_atr_multiple" in row.keys() else None,
        shock_lookback_bars=row["shock_lookback_bars"] if "shock_lookback_bars" in row.keys() else 0,
        shock_direction=row["shock_direction"] if "shock_direction" in row.keys() else "none",
        shock_suppression_until=row["shock_suppression_until"] if "shock_suppression_until" in row.keys() else None,
        shock_suppression_candles_remaining=row["shock_suppression_candles_remaining"] if "shock_suppression_candles_remaining" in row.keys() else 0,
        raw_lr_1h=row["raw_lr_1h"] if "raw_lr_1h" in row.keys() else None,
        raw_lr_15m=row["raw_lr_15m"] if "raw_lr_15m" in row.keys() else None,
        raw_lr_5m=row["raw_lr_5m"] if "raw_lr_5m" in row.keys() else None,
        filtered_lr_1h=row["filtered_lr_1h"] if "filtered_lr_1h" in row.keys() else None,
        filtered_lr_15m=row["filtered_lr_15m"] if "filtered_lr_15m" in row.keys() else None,
        filtered_lr_5m=row["filtered_lr_5m"] if "filtered_lr_5m" in row.keys() else None,
        trend_changed_after_filter=bool(row["trend_changed_after_filter"]) if "trend_changed_after_filter" in row.keys() else False,
        market_validity_state=row["market_validity_state"] if "market_validity_state" in row.keys() else "valid",
        market_validity_reason=row["market_validity_reason"] if "market_validity_reason" in row.keys() else None,
    )


def _opportunity_filter_clauses(
    start: str,
    end: str,
    symbol: Optional[str] = None,
    decision: Optional[str] = None,
    strategy: Optional[str] = None,
    signal_type: Optional[str] = None,
    first_blocker: Optional[str] = None,
    near_miss: Optional[bool] = None,
    table_alias: str = "",
) -> tuple[str, list[Any], str, str]:
    """Return SQL WHERE text and params for indexed metrics filters."""
    start_iso, end_iso = _normalize_range_bounds(start, end)
    prefix = f"{table_alias}." if table_alias else ""
    clauses = [f"{prefix}evaluated_at >= ?", f"{prefix}evaluated_at < ?"]
    params: list[Any] = [start_iso, end_iso]
    if symbol:
        clauses.append(f"{prefix}symbol = ?")
        params.append(symbol.upper())
    if decision:
        clauses.append(f"{prefix}final_decision = ?")
        params.append(decision)
    if strategy:
        clauses.append(f"{prefix}strategy = ?")
        params.append(strategy)
    if signal_type:
        clauses.append(f"{prefix}signal_type = ?")
        params.append(signal_type)
    if first_blocker:
        clauses.append(f"{prefix}first_blocker = ?")
        params.append(first_blocker)
    if near_miss is not None:
        clauses.append(f"{prefix}near_miss = ?")
        params.append(int(near_miss))
    return " AND ".join(clauses), params, start_iso, end_iso


def get_opportunities(
    start: str,
    end: str,
    symbol: Optional[str] = None,
    decision: Optional[str] = None,
    strategy: Optional[str] = None,
    signal_type: Optional[str] = None,
    first_blocker: Optional[str] = None,
    near_miss: Optional[bool] = None,
    criterion: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Optional[DBBackend] = None,
) -> list[dict[str, Any]]:
    """Return evaluated opportunities matching the given filters.

    When ``criterion`` is provided, results are restricted to opportunities that
    have a failing evaluation (``passed`` is false) for that criterion, regardless
    of whether it was the decisive ``first_blocker``. This backs the criterion
    drilldown without loading the full evaluated set (spec 022 FR-023).
    """
    db = db or get_db()
    return _get_opportunities_db(
        start, end, symbol, decision, strategy, signal_type, first_blocker,
        near_miss, criterion, limit, offset, db,
    )


def _journal_timestamp(entry: dict[str, Any]) -> Optional[datetime]:
    """Return the best available journal timestamp for metrics range filters."""
    for key in ("prime_closed_at", "prime_suppressed_last_at", "signal_timestamp", "created_at", "evaluated_at"):
        value = entry.get(key)
        if not value:
            continue
        try:
            return _parse_dt(str(value))
        except (TypeError, ValueError):
            continue
    return None


def _prime_suppression_summary(start_iso: str, end_iso: str, symbol: Optional[str] = None) -> dict[str, Any]:
    """Aggregate prime suppression evidence from persisted Signal Journal records."""
    try:
        from tradegumi import journal as signal_journal

        with signal_journal._lock:
            entries = signal_journal._read_entries_oldest_first()
    except Exception:
        return {
            "total_prime_suppressed_signals": 0,
            "prime_suppressed_signals_by_symbol": {},
            "prime_suppressed_same_direction_count": 0,
            "prime_suppressed_opposite_direction_count": 0,
            "prime_invalidated_by_prime_count": 0,
            "inferred_tp_close_count": 0,
            "inferred_sl_close_count": 0,
            "ambiguous_prime_close_count": 0,
        }

    start_dt = _parse_dt(start_iso)
    end_dt = _parse_dt(end_iso)
    symbol_key = symbol.upper() if symbol else None
    by_symbol: dict[str, int] = {}
    same_direction = 0
    opposite_direction = 0
    invalidated_by_prime = 0
    inferred_tp = 0
    inferred_sl = 0
    ambiguous = 0

    for entry in entries:
        entry_symbol = str(entry.get("symbol") or "").upper()
        if symbol_key and entry_symbol != symbol_key:
            continue
        timestamp = _journal_timestamp(entry)
        if timestamp is not None and not (start_dt <= timestamp < end_dt):
            continue
        suppressed_count = int(entry.get("prime_suppressed_signal_count") or 0)
        if suppressed_count:
            by_symbol[entry_symbol or "UNKNOWN"] = by_symbol.get(entry_symbol or "UNKNOWN", 0) + suppressed_count
        same_direction += int(entry.get("prime_suppressed_same_direction_count") or 0)
        opposite_direction += int(entry.get("prime_suppressed_opposite_direction_count") or 0)
        suppressed_outcomes = entry.get("prime_suppressed_signal_outcomes")
        if isinstance(suppressed_outcomes, list):
            invalidated_by_prime += sum(
                1 for outcome in suppressed_outcomes
                if isinstance(outcome, dict) and outcome.get("outcome") == "invalidated_by_prime"
            )
        elif suppressed_count:
            invalidated_by_prime += suppressed_count
        if entry.get("prime_closed_reason") == "inferred_tp":
            inferred_tp += 1
        if entry.get("prime_closed_reason") == "inferred_sl":
            inferred_sl += 1
        if entry.get("prime_close_ambiguous") is True:
            ambiguous += 1

    return {
        "total_prime_suppressed_signals": sum(by_symbol.values()),
        "prime_suppressed_signals_by_symbol": by_symbol,
        "prime_suppressed_same_direction_count": same_direction,
        "prime_suppressed_opposite_direction_count": opposite_direction,
        "prime_invalidated_by_prime_count": invalidated_by_prime,
        "inferred_tp_close_count": inferred_tp,
        "inferred_sl_close_count": inferred_sl,
        "ambiguous_prime_close_count": ambiguous,
    }


def _managed_lifecycle_summary(start_iso: str, end_iso: str, symbol: Optional[str] = None) -> dict[str, Any]:
    """Aggregate managed trade lifecycle evidence from Signal Journal records."""
    try:
        from tradegumi import journal as signal_journal

        with signal_journal._lock:
            entries = signal_journal._read_entries_oldest_first()
    except Exception:
        entries = []

    start_dt = _parse_dt(start_iso)
    end_dt = _parse_dt(end_iso)
    symbol_key = symbol.upper() if symbol else None
    summary = {
        "pullback_entries_opened": 0,
        "continuation_management_events_observed": 0,
        "continuation_management_events_accepted": 0,
        "continuation_management_events_rejected": 0,
        "tp_extension_count": 0,
        "sl_tighten_count": 0,
        "break_even_move_count": 0,
        "profit_protected_sl_win_count": 0,
        "opposite_direction_continuation_warning_count": 0,
        "average_r_captured": None,
        "max_favorable_excursion_before_exit": None,
        "managed_vs_original_result_delta": {"improved": 0, "unchanged": 0, "worsened": 0, "unknown": 0},
    }
    captured_r_values: list[float] = []
    mfe_values: list[float] = []
    for entry in entries:
        entry_symbol = str(entry.get("symbol") or "").upper()
        if symbol_key and entry_symbol != symbol_key:
            continue
        timestamp = _journal_timestamp(entry)
        if timestamp is not None and not (start_dt <= timestamp < end_dt):
            continue
        role = entry.get("lifecycle_role")
        if role == "entry":
            summary["pullback_entries_opened"] += 1
            summary["tp_extension_count"] += int(entry.get("tp_extension_count") or 0)
            summary["sl_tighten_count"] += int(entry.get("sl_tighten_count") or 0)
            summary["break_even_move_count"] += int(entry.get("break_even_move_count") or 0)
            summary["opposite_direction_continuation_warning_count"] += int(entry.get("opposite_direction_continuation_warning_count") or 0)
        if role in {"management", "warning"}:
            summary["continuation_management_events_observed"] += 1
            if entry.get("management_accepted") is True:
                summary["continuation_management_events_accepted"] += 1
            else:
                summary["continuation_management_events_rejected"] += 1
            if role == "warning":
                summary["opposite_direction_continuation_warning_count"] += 1
        if entry.get("managed_exit_reason") == "sl_hit_with_profit":
            summary["profit_protected_sl_win_count"] += 1
        captured_r = _safe_float(entry.get("captured_r"))
        if captured_r is not None:
            captured_r_values.append(captured_r)
        mfe = _safe_float(entry.get("max_favorable_excursion"))
        if mfe is not None:
            mfe_values.append(mfe)
        delta = str(entry.get("managed_result_delta") or "unknown")
        if delta in summary["managed_vs_original_result_delta"]:
            summary["managed_vs_original_result_delta"][delta] += 1
    if captured_r_values:
        summary["average_r_captured"] = round(sum(captured_r_values) / len(captured_r_values), 4)
    if mfe_values:
        summary["max_favorable_excursion_before_exit"] = max(mfe_values)
    return summary


def _is_pullback_identity(strategy: Any, signal_type: Any) -> bool:
    """Return whether a strategy/signal identity represents a pullback setup."""
    strategy_name = str(strategy or "").lower()
    signal_type_name = str(signal_type or "").lower()
    return signal_type_name == "pullback" or "pullback" in strategy_name


def _journaled_pullback_summary(start_iso: str, end_iso: str, symbol: Optional[str] = None) -> dict[str, int]:
    """Count journaled and prime-suppressed pullbacks from Signal Journal rows."""
    try:
        from tradegumi import journal as signal_journal

        with signal_journal._lock:
            entries = signal_journal._read_entries_oldest_first()
    except Exception:
        return {"journaled_count": 0, "prime_suppressed_count": 0}

    start_dt = _parse_dt(start_iso)
    end_dt = _parse_dt(end_iso)
    symbol_key = symbol.upper() if symbol else None
    journaled_count = 0
    prime_suppressed_count = 0

    for entry in entries:
        entry_symbol = str(entry.get("symbol") or "").upper()
        if symbol_key and entry_symbol != symbol_key:
            continue
        timestamp = _journal_timestamp(entry)
        if timestamp is not None and not (start_dt <= timestamp < end_dt):
            continue
        if _is_pullback_identity(entry.get("strategy"), entry.get("signal_type")):
            journaled_count += 1
        suppressed_outcomes = entry.get("prime_suppressed_signal_outcomes")
        if not isinstance(suppressed_outcomes, list):
            continue
        for outcome in suppressed_outcomes:
            if not isinstance(outcome, dict):
                continue
            outcome_symbol = str(outcome.get("symbol") or entry_symbol).upper()
            if symbol_key and outcome_symbol != symbol_key:
                continue
            if _is_pullback_identity(outcome.get("strategy"), outcome.get("signal_type")):
                prime_suppressed_count += 1

    return {"journaled_count": journaled_count, "prime_suppressed_count": prime_suppressed_count}


def get_summary(
    start: str,
    end: str,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    signal_type: Optional[str] = None,
    decision: Optional[str] = None,
    first_blocker: Optional[str] = None,
    db: Optional[DBBackend] = None,
) -> dict[str, Any]:
    db = db or get_db()
    filters = {
        "start": start,
        "end": end,
        "symbol": symbol,
        "strategy": strategy,
        "signal_type": signal_type,
        "decision": decision,
        "first_blocker": first_blocker,
    }
    cached = get_cache().get_cached_strategy_summary(filters)
    if cached is not None:
        return cached
    result = _get_summary_db(start, end, symbol, strategy, signal_type, decision, first_blocker, db)
    get_cache().cache_strategy_summary(filters, result)
    return result


def compare_periods(
    base_start: str,
    base_end: str,
    compare_start: str,
    compare_end: str,
    symbol: Optional[str] = None,
    db: Optional[DBBackend] = None,
) -> dict[str, Any]:
    db = db or get_db()
    baseline = DiagnosticSummary(**_summary_dataclass_kwargs(get_summary(base_start, base_end, symbol=symbol, db=db)))
    comparison = DiagnosticSummary(**_summary_dataclass_kwargs(get_summary(compare_start, compare_end, symbol=symbol, db=db)))
    base_top = baseline.top_blockers[0].criterion_name if baseline.top_blockers else None
    comp_top = comparison.top_blockers[0].criterion_name if comparison.top_blockers else None
    return ComparisonPeriod(
        baseline=baseline,
        comparison=comparison,
        deltas={
            "total_evaluated": comparison.total_evaluated - baseline.total_evaluated,
            "emitted_count": comparison.emitted_count - baseline.emitted_count,
            "near_miss_count": comparison.near_miss_count - baseline.near_miss_count,
            "rejected_count": comparison.rejected_count - baseline.rejected_count,
            "top_blocker_changed": base_top != comp_top,
            "baseline_top_blocker": base_top,
            "comparison_top_blocker": comp_top,
        },
    ).to_dict()


def _summary_dataclass_kwargs(data: dict[str, Any]) -> dict[str, Any]:
    converted = dict(data)
    converted["criterion_summaries"] = [CriterionSummary(**c) for c in data.get("criterion_summaries", [])]
    converted["top_blockers"] = [BlockerSummary(**b) for b in data.get("top_blockers", [])]
    return converted


def export_summary(
    start: str,
    end: str,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    signal_type: Optional[str] = None,
    decision: Optional[str] = None,
    first_blocker: Optional[str] = None,
    include_opportunities: bool = False,
    db: Optional[DBBackend] = None,
) -> dict[str, Any]:
    db = db or get_db()
    payload = {
        "summary": get_summary(
            start,
            end,
            symbol=symbol,
            strategy=strategy,
            signal_type=signal_type,
            decision=decision,
            first_blocker=first_blocker,
            db=db,
        )
    }
    if include_opportunities:
        payload["opportunities"] = get_opportunities(
            start,
            end,
            symbol=symbol,
            decision=decision,
            strategy=strategy,
            signal_type=signal_type,
            first_blocker=first_blocker,
            limit=config.STRATEGY_METRICS_MAX_OPPORTUNITIES,
            db=db,
        )
    return payload


"""Postgres-native implementations of strategy metrics operations."""


def _record_opportunity_db(opportunity: EvaluatedOpportunity, db: Any) -> None:
    """Append-only insert of an opportunity and its criteria via the persistence layer.

    The opportunity row and its criterion rows are written inside a single
    transaction so the diagnostic is never persisted half-written.
    """
    criterion_rows = [
        (
            opportunity.id,
            opportunity.evaluated_at,
            _canonical_criterion_name(criterion.criterion_name),
            criterion.layer,
            json.dumps(criterion.measured_value),
            json.dumps(criterion.threshold_value),
            criterion.threshold_operator,
            None if criterion.passed is None else int(criterion.passed),
            None if criterion.expected_pass is None else int(criterion.expected_pass),
            int(criterion.pass_mismatch),
            criterion.margin,
            criterion.normalized_margin,
            int(criterion.required),
            int(criterion.blocked_signal),
            criterion.data_quality,
            criterion.diagnostic_state,
            criterion.reason,
            json.dumps(criterion.context),
        )
        for criterion in opportunity.criteria
    ]
    with db.transaction():
        db.execute(
            """
            INSERT INTO evaluated_opportunities (
                id, evaluated_at, symbol, timeframe, mode, strategy, signal_type, direction, trend,
                final_decision, decision_reason, confidence, failed_criteria_count,
                near_miss, data_complete, data_quality_notes, threshold_version, created_at,
                first_blocker, all_blockers, blocking_layer, trend_decision, pipeline_state,
                near_miss_reason, threshold_version_unknown_reason, usable_for_strategy_stats,
                stats_exclusion_reason,
                volatility_shock_detected, shock_timeframe, shock_candle_time, shock_true_range,
                shock_atr, shock_atr_multiple, shock_lookback_bars, shock_direction,
                shock_suppression_until, shock_suppression_candles_remaining,
                raw_lr_1h, raw_lr_15m, raw_lr_5m,
                filtered_lr_1h, filtered_lr_15m, filtered_lr_5m,
                trend_changed_after_filter, market_validity_state, market_validity_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity.id,
                opportunity.evaluated_at,
                opportunity.symbol,
                opportunity.timeframe,
                opportunity.mode,
                opportunity.strategy,
                opportunity.signal_type,
                opportunity.direction,
                opportunity.trend,
                opportunity.final_decision,
                opportunity.decision_reason,
                opportunity.confidence,
                opportunity.failed_criteria_count,
                int(opportunity.near_miss),
                int(opportunity.data_complete),
                json.dumps(opportunity.data_quality_notes),
                opportunity.threshold_version,
                opportunity.created_at,
                opportunity.first_blocker,
                json.dumps(opportunity.all_blockers),
                opportunity.blocking_layer,
                json.dumps(opportunity.trend_decision) if opportunity.trend_decision is not None else None,
                opportunity.pipeline_state,
                opportunity.near_miss_reason,
                opportunity.threshold_version_unknown_reason,
                None if opportunity.usable_for_strategy_stats is None else int(opportunity.usable_for_strategy_stats),
                opportunity.stats_exclusion_reason,
                int(opportunity.volatility_shock_detected),
                opportunity.shock_timeframe,
                opportunity.shock_candle_time,
                opportunity.shock_true_range,
                opportunity.shock_atr,
                opportunity.shock_atr_multiple,
                opportunity.shock_lookback_bars,
                opportunity.shock_direction,
                opportunity.shock_suppression_until,
                opportunity.shock_suppression_candles_remaining,
                opportunity.raw_lr_1h,
                opportunity.raw_lr_15m,
                opportunity.raw_lr_5m,
                opportunity.filtered_lr_1h,
                opportunity.filtered_lr_15m,
                opportunity.filtered_lr_5m,
                int(opportunity.trend_changed_after_filter),
                opportunity.market_validity_state,
                opportunity.market_validity_reason,
            ),
        )
        if criterion_rows:
            db.executemany(
                """
                INSERT INTO criterion_results (
                    opportunity_id, evaluated_at, criterion_name, layer, measured_value, threshold_value,
                    threshold_operator, passed, expected_pass, pass_mismatch, margin,
                    normalized_margin, required, blocked_signal, data_quality, diagnostic_state,
                    reason, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                criterion_rows,
            )


def _get_opportunities_db(
    start: str,
    end: str,
    symbol: Optional[str],
    decision: Optional[str],
    strategy: Optional[str],
    signal_type: Optional[str],
    first_blocker: Optional[str],
    near_miss: Optional[bool],
    criterion: Optional[str],
    limit: int,
    offset: int,
    db: Any,
) -> list[dict[str, Any]]:
    where_sql, params, _, _ = _opportunity_filter_clauses(
        start, end, symbol=symbol, decision=decision, strategy=strategy,
        signal_type=signal_type, first_blocker=first_blocker, near_miss=near_miss,
    )
    if criterion:
        # Keep only opportunities with a failing evaluation for this criterion.
        # Matched on the composite (id, evaluated_at) key like the other joins,
        # and across any legacy spellings of the canonical criterion name.
        stored_names = _stored_criterion_names(criterion)
        name_placeholders = ",".join("?" for _ in stored_names)
        where_sql += (
            " AND EXISTS (SELECT 1 FROM criterion_results cr "
            "WHERE cr.opportunity_id = evaluated_opportunities.id "
            "AND cr.evaluated_at = evaluated_opportunities.evaluated_at "
            f"AND cr.criterion_name IN ({name_placeholders}) AND cr.passed = 0)"
        )
        params = [*params, *stored_names]
    limit = max(1, min(int(limit), config.STRATEGY_METRICS_MAX_OPPORTUNITIES))
    offset = max(0, int(offset))
    rows = db.fetchall(
        f"SELECT * FROM evaluated_opportunities WHERE {where_sql} ORDER BY evaluated_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    ids = [row["id"] for row in rows]
    criteria_by_opportunity: dict[str, list[CriterionResult]] = {oid: [] for oid in ids}
    if ids:
        placeholders = ",".join("?" for _ in ids)
        crit_rows = db.fetchall(
            f"""
            SELECT * FROM criterion_results
            WHERE opportunity_id IN ({placeholders})
            ORDER BY opportunity_id, id
            LIMIT {config.STRATEGY_METRICS_MAX_OPPORTUNITIES * 50}
            """,
            tuple(ids),
        )
        for c in crit_rows:
            criteria_by_opportunity.setdefault(c["opportunity_id"], []).append(
                CriterionResult(
                    id=c["id"],
                    opportunity_id=c["opportunity_id"],
                    criterion_name=_canonical_criterion_name(c["criterion_name"]),
                    layer=c["layer"],
                    measured_value=json.loads(c["measured_value"]) if c["measured_value"] else None,
                    threshold_value=json.loads(c["threshold_value"]) if c["threshold_value"] else None,
                    threshold_operator=c["threshold_operator"],
                    passed=None if c["passed"] is None else bool(c["passed"]),
                    expected_pass=None if c.get("expected_pass") is None else bool(c["expected_pass"]),
                    pass_mismatch=bool(c["pass_mismatch"]) if c.get("pass_mismatch") is not None else False,
                    margin=c["margin"],
                    normalized_margin=c["normalized_margin"],
                    required=bool(c["required"]),
                    blocked_signal=bool(c["blocked_signal"]),
                    data_quality=c["data_quality"],
                    diagnostic_state=c.get("diagnostic_state", "evaluated"),
                    reason=c.get("reason"),
                    context=json.loads(c.get("context") or "{}"),
                )
            )
    result = []
    for row in rows:
        criteria = criteria_by_opportunity.get(row["id"], [])
        result.append(_row_to_opportunity(row, criteria).to_dict())
    return result


_SUMMARY_LIGHTWEIGHT_COLUMNS = (
    "id, evaluated_at, final_decision, near_miss, data_complete, threshold_version, "
    "threshold_version_unknown_reason, strategy, signal_type, usable_for_strategy_stats, "
    "stats_exclusion_reason, near_miss_reason, decision_reason, pipeline_state, "
    "all_blockers, first_blocker, blocking_layer"
)

_PULLBACK_CRITERIA = (
    "pullback_trigger_candle",
    "keltner_pullback_sequence",
    "pullback_structure",
    "pullback_15m_bridge",
    "pullback_macd_hard_block",
)


def _count_by_fallback(value: Any, fallback: str = "unknown") -> str:
    """Mirror SQL COALESCE(NULLIF(col, ''), fallback) for Python-side grouping."""
    text = "" if value is None else str(value)
    return text if text != "" else fallback


def _criterion_summaries_db(db: Any, where_sql: str, params: list[Any]) -> list[CriterionSummary]:
    """Per-criterion pass/fail aggregation via portable SQL (no json functions)."""
    rows = db.fetchall(
        f"""
        SELECT c.criterion_name AS criterion_name,
               MAX(c.layer) AS layer,
               COUNT(*) AS evaluated_count,
               SUM(CASE WHEN c.passed = 1 THEN 1 ELSE 0 END) AS pass_count,
               SUM(CASE WHEN c.passed = 0 THEN 1 ELSE 0 END) AS fail_count,
               SUM(CASE WHEN c.data_quality != 'complete' THEN 1 ELSE 0 END) AS incomplete_count,
               AVG(CASE WHEN c.passed = 0 THEN ABS(c.margin) ELSE NULL END) AS average_failure_margin,
               SUM(CASE WHEN o.near_miss = 1 AND c.blocked_signal = 1 THEN 1 ELSE 0 END) AS near_miss_contribution
        FROM criterion_results c
        JOIN evaluated_opportunities o ON o.id = c.opportunity_id AND o.evaluated_at = c.evaluated_at
        WHERE {where_sql}
        GROUP BY c.criterion_name
        ORDER BY c.criterion_name
        """,
        params,
    )
    summaries = []
    for row in rows:
        evaluated = int(row.get("evaluated_count") or 0)
        passed = int(row.get("pass_count") or 0)
        failed = int(row.get("fail_count") or 0)
        avg_margin = row.get("average_failure_margin")
        summaries.append(
            CriterionSummary(
                criterion_name=_canonical_criterion_name(row.get("criterion_name")),
                evaluated_count=evaluated,
                pass_count=passed,
                fail_count=failed,
                pass_rate=round(passed / evaluated, 4) if evaluated else 0.0,
                fail_rate=round(failed / evaluated, 4) if evaluated else 0.0,
                near_miss_contribution=int(row.get("near_miss_contribution") or 0),
                average_failure_margin=None if avg_margin is None else round(float(avg_margin), 6),
                incomplete_count=int(row.get("incomplete_count") or 0),
                layer=str(row.get("layer") or ""),
            )
        )
    return summaries


def _funnel_candle_rules_db(db: Any, where_sql: str, params: list[Any]) -> tuple[int, int, int]:
    """Return (candle_passed, candle_waiting_or_failed, signal_rules_evaluated) opp counts."""
    def _count(criteria_clause: str, extra: tuple) -> int:
        row = db.fetchone(
            f"""
            SELECT COUNT(*) AS cnt FROM (
                SELECT DISTINCT c.opportunity_id, c.evaluated_at
                FROM criterion_results c
                JOIN evaluated_opportunities o ON o.id = c.opportunity_id AND o.evaluated_at = c.evaluated_at
                WHERE {where_sql} AND {criteria_clause}
            ) t
            """,
            (*params, *extra),
        )
        return int(row.get("cnt") or 0) if row else 0

    rules_placeholders = ", ".join("?" for _ in ("stoch_rsi", "macd", "keltner", "confidence"))
    candle_passed = _count("c.criterion_name = 'candle_close_gate' AND c.passed = 1", ())
    candle_waiting = _count("c.criterion_name = 'candle_close_gate' AND (c.passed = 0 OR c.passed IS NULL)", ())
    rules = _count(f"c.criterion_name IN ({rules_placeholders})", ("stoch_rsi", "macd", "keltner", "confidence"))
    return candle_passed, candle_waiting, rules


def _top_blockers_db(
    db: Any,
    where_sql: str,
    params: list[Any],
    lightweight_rows: list[dict[str, Any]],
    blocked_opportunity_count: int,
) -> list[BlockerSummary]:
    """Score blockers in Python from parsed all_blockers + blocked-opp criteria.

    Mirrors the SQLite ``_blocker_summaries`` weighting (frequency 0.40,
    margin 0.30, quality 0.30) without relying on json_each / GROUP_CONCAT.
    """
    if not blocked_opportunity_count:
        return []
    crit_rows = db.fetchall(
        f"""
        SELECT c.opportunity_id AS opportunity_id, c.evaluated_at AS evaluated_at,
               c.criterion_name AS criterion_name, c.normalized_margin AS normalized_margin,
               c.required AS required, c.passed AS passed
        FROM criterion_results c
        JOIN evaluated_opportunities o ON o.id = c.opportunity_id AND o.evaluated_at = c.evaluated_at
        WHERE {where_sql} AND o.all_blockers != '[]'
        LIMIT {config.STRATEGY_METRICS_MAX_OPPORTUNITIES * 50}
        """,
        params,
    )
    criteria_by_opp: dict[tuple, list[dict[str, Any]]] = {}
    for c in crit_rows:
        criteria_by_opp.setdefault((c["opportunity_id"], c["evaluated_at"]), []).append(c)

    data: dict[str, dict[str, Any]] = {}
    for row in lightweight_rows:
        blockers = _parse_blockers(row.get("all_blockers"))
        if not blockers:
            continue
        crits = criteria_by_opp.get((row["id"], row["evaluated_at"]), [])
        required = [c for c in crits if c["required"]]
        total_required = len(required)
        passed_required = sum(1 for c in required if c["passed"] == 1)
        quality_val = (passed_required / (total_required - 1)) if total_required > 1 else 0.0
        for name in set(blockers):
            bucket = data.setdefault(name, {"ids": set(), "margins": [], "qualities": []})
            bucket["ids"].add(row["id"])
            matching = [c for c in crits if c["criterion_name"] == name]
            for c in (matching or [None]):
                bucket["qualities"].append(quality_val)
                if c is not None and c["normalized_margin"] is not None:
                    nm = float(c["normalized_margin"])
                    bucket["margins"].append(0.0 if abs(nm) > 1.0 else 1.0 - abs(nm))

    result = []
    for name, bucket in data.items():
        blocked_count = len(bucket["ids"])
        frequency = blocked_count / blocked_opportunity_count
        margin = max(0.0, min(1.0, sum(bucket["margins"]) / len(bucket["margins"]))) if bucket["margins"] else 0.0
        quality = max(0.0, min(1.0, sum(bucket["qualities"]) / len(bucket["qualities"]))) if bucket["qualities"] else 0.0
        combined = (frequency * 0.40) + (margin * 0.30) + (quality * 0.30)
        result.append(
            BlockerSummary(
                criterion_name=name,
                blocked_count=blocked_count,
                frequency_component=round(frequency, 4),
                margin_component=round(margin, 4),
                quality_component=round(quality, 4),
                combined_score=round(combined, 4),
                example_opportunity_ids=sorted(bucket["ids"])[:5],
            )
        )
    result.sort(key=lambda b: (-b.combined_score, -b.blocked_count, b.criterion_name))
    return result[:50]


def _pullback_summary_db(
    db: Any, where_sql: str, params: list[Any], start_iso: str, end_iso: str, symbol: Optional[str]
) -> dict[str, Any]:
    """Pullback outcomes via portable SQL EXISTS + Python blocker counting."""
    placeholders = ", ".join("?" for _ in _PULLBACK_CRITERIA)
    pullback_sql = (
        f"{where_sql} AND ("
        "o.signal_type = 'pullback' OR LOWER(o.strategy) LIKE ? OR "
        "EXISTS (SELECT 1 FROM criterion_results pc WHERE pc.opportunity_id = o.id "
        f"AND pc.evaluated_at = o.evaluated_at AND pc.criterion_name IN ({placeholders}))"
        ")"
    )
    pullback_params = [*params, "%pullback%", *_PULLBACK_CRITERIA]
    totals = db.fetchone(
        f"""
        SELECT
            COUNT(*) AS evaluated_count,
            SUM(CASE WHEN o.final_decision = 'rejected' THEN 1 ELSE 0 END) AS rejected_count,
            SUM(CASE WHEN o.final_decision = 'emitted' THEN 1 ELSE 0 END) AS emitted_count,
            SUM(CASE WHEN o.near_miss = 1 THEN 1 ELSE 0 END) AS near_miss_count
        FROM evaluated_opportunities o
        WHERE {pullback_sql}
        """,
        pullback_params,
    )
    rejected_rows = db.fetchall(
        f"SELECT o.id AS id, o.all_blockers AS all_blockers FROM evaluated_opportunities o "
        f"WHERE {pullback_sql} AND o.final_decision = 'rejected'",
        pullback_params,
    )
    rejected_by_gate: dict[str, set] = {}
    for row in rejected_rows:
        for blocker in set(_parse_blockers(row.get("all_blockers"))):
            rejected_by_gate.setdefault(blocker, set()).add(row["id"])
    gate_counts = sorted(
        ((name, len(ids)) for name, ids in rejected_by_gate.items()),
        key=lambda kv: (-kv[1], kv[0]),
    )
    journal_counts = _journaled_pullback_summary(start_iso, end_iso, symbol)
    return {
        "evaluated_count": int(totals.get("evaluated_count") or 0) if totals else 0,
        "rejected_count": int(totals.get("rejected_count") or 0) if totals else 0,
        "emitted_count": int(totals.get("emitted_count") or 0) if totals else 0,
        "near_miss_count": int(totals.get("near_miss_count") or 0) if totals else 0,
        "journaled_count": journal_counts["journaled_count"],
        "prime_suppressed_count": journal_counts["prime_suppressed_count"],
        "rejected_by_gate": {name: count for name, count in gate_counts},
    }


def _parse_blockers(value: Any) -> list[str]:
    """Parse an all_blockers column (TEXT JSON array) into a list of strings."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(v) for v in parsed] if isinstance(parsed, list) else []


def _get_summary_db(
    start: str,
    end: str,
    symbol: Optional[str],
    strategy: Optional[str],
    signal_type: Optional[str],
    decision: Optional[str],
    first_blocker: Optional[str],
    db: Any,
) -> dict[str, Any]:
    """Backend-agnostic summary with full parity to the SQLite-connection path.

    Scalar/criterion aggregates run as portable SQL; the JSON-array (all_blockers)
    logic is computed in Python from a lightweight opportunity fetch so the same
    code path serves both SQLite and Postgres backends.
    """
    where_sql, params, start_iso, end_iso = _opportunity_filter_clauses(
        start, end, symbol=symbol, decision=decision, strategy=strategy,
        signal_type=signal_type, first_blocker=first_blocker, table_alias="o",
    )
    rows = db.fetchall(
        f"SELECT {_SUMMARY_LIGHTWEIGHT_COLUMNS} FROM evaluated_opportunities o WHERE {where_sql}",
        params,
    )

    total = len(rows)
    emitted = rejected = skipped = indeterminate = 0
    near_miss_count = trade_opportunity_count = stats_excluded_count = 0
    stats_unknown_eligibility_count = incomplete_count = 0
    threshold_version_counts: dict[str, int] = {}
    strategy_counts: dict[str, int] = {}
    signal_type_counts: dict[str, int] = {}
    stats_exclusion_counts: dict[str, int] = {}
    threshold_version_unknown_reasons: dict[str, int] = {}
    near_miss_reason_counts: dict[str, int] = {}
    threshold_versions_seen: set = set()
    all_blockers_set: set = set()
    blocked_opportunity_count = 0
    trend_skipped = signal_data_missing = 0
    earliest_first_blocker: Optional[tuple] = None  # (evaluated_at, first_blocker, blocking_layer)

    for row in rows:
        fd = row.get("final_decision")
        if fd == "emitted":
            emitted += 1
        elif fd == "rejected":
            rejected += 1
        elif fd == "skipped":
            skipped += 1
        elif fd == "indeterminate":
            indeterminate += 1
        usable = row.get("usable_for_strategy_stats")
        if fd == "emitted":
            if usable == 1:
                trade_opportunity_count += 1
            elif usable == 0:
                stats_excluded_count += 1
                stats_exclusion_counts[_count_by_fallback(row.get("stats_exclusion_reason"))] = (
                    stats_exclusion_counts.get(_count_by_fallback(row.get("stats_exclusion_reason")), 0) + 1
                )
            elif usable is None:
                stats_unknown_eligibility_count += 1
        if row.get("near_miss"):
            near_miss_count += 1
            reason = row.get("near_miss_reason")
            if reason is not None:
                near_miss_reason_counts[reason] = near_miss_reason_counts.get(reason, 0) + 1
        if not row.get("data_complete"):
            incomplete_count += 1

        tv = _count_by_fallback(row.get("threshold_version"))
        threshold_version_counts[tv] = threshold_version_counts.get(tv, 0) + 1
        threshold_versions_seen.add(row.get("threshold_version"))
        if tv == "unknown":
            tvur = _count_by_fallback(row.get("threshold_version_unknown_reason"), "legacy_or_missing_threshold_version")
            threshold_version_unknown_reasons[tvur] = threshold_version_unknown_reasons.get(tvur, 0) + 1
        sc = _count_by_fallback(row.get("strategy"))
        strategy_counts[sc] = strategy_counts.get(sc, 0) + 1
        stc = _count_by_fallback(row.get("signal_type"))
        signal_type_counts[stc] = signal_type_counts.get(stc, 0) + 1

        blockers = _parse_blockers(row.get("all_blockers"))
        if blockers:
            blocked_opportunity_count += 1
            all_blockers_set.update(blockers)
        if row.get("decision_reason") == "no_trend" or row.get("pipeline_state") == "trend_skipped" or any(
            b.startswith("trend:") for b in blockers
        ):
            trend_skipped += 1
        if (not row.get("data_complete")) or any(b.startswith("signal_engine_data:") for b in blockers):
            signal_data_missing += 1
        fb = row.get("first_blocker")
        if fb is not None:
            key = (row.get("evaluated_at"), fb, row.get("blocking_layer"))
            if earliest_first_blocker is None or key[0] < earliest_first_blocker[0]:
                earliest_first_blocker = key

    summary_first_blocker = earliest_first_blocker[1] if earliest_first_blocker else None
    blocking_layer = earliest_first_blocker[2] if earliest_first_blocker else None

    candle_passed, candle_waiting, rules_evaluated = _funnel_candle_rules_db(db, where_sql, params)
    trend_candidate_found = max(0, total - trend_skipped)
    pipeline_funnel = {
        "total_evaluated": total,
        "trend_skipped": trend_skipped,
        "trend_candidate_found": trend_candidate_found,
        "signal_data_complete": max(0, trend_candidate_found - signal_data_missing),
        "signal_data_missing": signal_data_missing,
        "candle_close_gate_passed": candle_passed,
        "candle_close_gate_waiting_or_failed": candle_waiting,
        "signal_rules_evaluated": rules_evaluated,
        "signal_rejected": rejected,
        "signal_emitted": emitted,
        "indeterminate": indeterminate,
    }

    warnings: list[str] = []
    if total == 0:
        warnings.append("No evaluated opportunities in selected period")
    if incomplete_count:
        warnings.append("Some opportunities have incomplete diagnostics")
    if len(threshold_versions_seen) > 1:
        warnings.append("Strategy threshold version changed during selected period")

    prime_summary = _prime_suppression_summary(start_iso, end_iso, symbol)
    managed_summary = _managed_lifecycle_summary(start_iso, end_iso, symbol)
    summary = DiagnosticSummary(
        start=start_iso,
        end=end_iso,
        total_evaluated=total,
        emitted_count=emitted,
        rejected_count=rejected,
        skipped_count=skipped,
        indeterminate_count=indeterminate,
        near_miss_count=near_miss_count,
        trade_opportunity_count=trade_opportunity_count,
        stats_excluded_count=stats_excluded_count,
        stats_unknown_eligibility_count=stats_unknown_eligibility_count,
        stats_exclusion_counts=stats_exclusion_counts,
        total_prime_suppressed_signals=prime_summary["total_prime_suppressed_signals"],
        prime_suppressed_signals_by_symbol=prime_summary["prime_suppressed_signals_by_symbol"],
        prime_suppressed_same_direction_count=prime_summary["prime_suppressed_same_direction_count"],
        prime_suppressed_opposite_direction_count=prime_summary["prime_suppressed_opposite_direction_count"],
        prime_invalidated_by_prime_count=prime_summary["prime_invalidated_by_prime_count"],
        inferred_tp_close_count=prime_summary["inferred_tp_close_count"],
        inferred_sl_close_count=prime_summary["inferred_sl_close_count"],
        ambiguous_prime_close_count=prime_summary["ambiguous_prime_close_count"],
        criterion_summaries=_criterion_summaries_db(db, where_sql, params),
        top_blockers=_top_blockers_db(db, where_sql, params, rows, blocked_opportunity_count),
        first_blocker=summary_first_blocker,
        all_blockers=sorted(b for b in all_blockers_set if b),
        blocking_layer=blocking_layer,
        threshold_version_counts=threshold_version_counts,
        strategy_counts=strategy_counts,
        signal_type_counts=signal_type_counts,
        pullback_summary=_pullback_summary_db(db, where_sql, params, start_iso, end_iso, symbol),
        managed_lifecycle_summary=managed_summary,
        pullback_entries_opened=managed_summary["pullback_entries_opened"],
        continuation_management_events_observed=managed_summary["continuation_management_events_observed"],
        continuation_management_events_accepted=managed_summary["continuation_management_events_accepted"],
        continuation_management_events_rejected=managed_summary["continuation_management_events_rejected"],
        tp_extension_count=managed_summary["tp_extension_count"],
        sl_tighten_count=managed_summary["sl_tighten_count"],
        break_even_move_count=managed_summary["break_even_move_count"],
        profit_protected_sl_win_count=managed_summary["profit_protected_sl_win_count"],
        opposite_direction_continuation_warning_count=managed_summary["opposite_direction_continuation_warning_count"],
        average_r_captured=managed_summary["average_r_captured"],
        max_favorable_excursion_before_exit=managed_summary["max_favorable_excursion_before_exit"],
        managed_vs_original_result_delta=managed_summary["managed_vs_original_result_delta"],
        threshold_version_unknown_reasons=threshold_version_unknown_reasons,
        near_miss_reason_counts=near_miss_reason_counts,
        pipeline_funnel=pipeline_funnel,
        data_quality_warnings=warnings,
    )
    return summary.to_dict()


def write_state_snapshot(summary: dict[str, Any], state_file: Path = STATE_FILE) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": _now_iso(), "summary": summary}
    tmp = state_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(state_file)

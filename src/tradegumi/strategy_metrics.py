"""Strategy diagnostic storage and aggregation.

The signal journal records emitted signals. This module records every evaluated
opportunity so quiet periods can be inspected without changing signal behavior.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from tradegumi import config

DATA_DIR = Path(__file__).parent / "data"
DB_FILE = DATA_DIR / "strategy_metrics.db"
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
_lock = threading.Lock()
_initialized_db_paths: set[str] = set()
_last_prune_by_db_path: dict[str, datetime] = {}
_write_connections_by_db_path: dict[str, sqlite3.Connection] = {}
_LEGACY_CRITERION_NAMES = {"singal_engine_data": "signal_engine_data"}


def _canonical_criterion_name(name: str) -> str:
    """Return the stable diagnostic criterion name used for metrics aggregation."""
    return _LEGACY_CRITERION_NAMES.get(str(name), str(name))


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


def init_schema(db_path: Path = DB_FILE) -> None:
    db_key = str(db_path.resolve())
    if db_key in _initialized_db_paths:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluated_opportunities (
                id TEXT PRIMARY KEY,
                evaluated_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                mode TEXT NOT NULL,
                strategy TEXT NOT NULL,
                signal_type TEXT NOT NULL DEFAULT 'pullback',
                direction TEXT NOT NULL,
                trend TEXT NOT NULL,
                final_decision TEXT NOT NULL,
                decision_reason TEXT NOT NULL,
                confidence REAL,
                failed_criteria_count INTEGER NOT NULL,
                near_miss INTEGER NOT NULL,
                data_complete INTEGER NOT NULL,
                data_quality_notes TEXT NOT NULL,
                threshold_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                first_blocker TEXT,
                all_blockers TEXT NOT NULL DEFAULT '[]',
                blocking_layer TEXT,
                trend_decision TEXT,
                pipeline_state TEXT,
                near_miss_reason TEXT,
                threshold_version_unknown_reason TEXT,
                usable_for_strategy_stats INTEGER,
                stats_exclusion_reason TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS criterion_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_id TEXT NOT NULL,
                criterion_name TEXT NOT NULL,
                layer TEXT NOT NULL,
                measured_value TEXT,
                threshold_value TEXT,
                threshold_operator TEXT NOT NULL,
                passed INTEGER,
                expected_pass INTEGER,
                pass_mismatch INTEGER NOT NULL DEFAULT 0,
                margin REAL,
                normalized_margin REAL,
                required INTEGER NOT NULL,
                blocked_signal INTEGER NOT NULL,
                data_quality TEXT NOT NULL,
                diagnostic_state TEXT NOT NULL DEFAULT 'evaluated',
                reason TEXT,
                context TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(opportunity_id) REFERENCES evaluated_opportunities(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_at ON evaluated_opportunities(evaluated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_symbol ON evaluated_opportunities(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_decision ON evaluated_opportunities(final_decision)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_symbol ON evaluated_opportunities(evaluated_at, symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_decision ON evaluated_opportunities(evaluated_at, final_decision)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_criteria_opp ON criterion_results(opportunity_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_criteria_name_opp ON criterion_results(criterion_name, opportunity_id)")
        _ensure_column(conn, "evaluated_opportunities", "first_blocker", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "all_blockers", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "evaluated_opportunities", "blocking_layer", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "trend_decision", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "pipeline_state", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "near_miss_reason", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "threshold_version_unknown_reason", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "usable_for_strategy_stats", "INTEGER")
        _ensure_column(conn, "evaluated_opportunities", "stats_exclusion_reason", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "signal_type", "TEXT NOT NULL DEFAULT 'pullback'")
        _ensure_column(conn, "criterion_results", "expected_pass", "INTEGER")
        _ensure_column(conn, "criterion_results", "pass_mismatch", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "criterion_results", "diagnostic_state", "TEXT NOT NULL DEFAULT 'evaluated'")
        _ensure_column(conn, "criterion_results", "reason", "TEXT")
        _ensure_column(conn, "criterion_results", "context", "TEXT NOT NULL DEFAULT '{}'")
        # ── Volatility shock + filtered LR columns ────────────────────────────
        _ensure_column(conn, "evaluated_opportunities", "volatility_shock_detected", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "evaluated_opportunities", "shock_timeframe", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "shock_candle_time", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "shock_true_range", "REAL")
        _ensure_column(conn, "evaluated_opportunities", "shock_atr", "REAL")
        _ensure_column(conn, "evaluated_opportunities", "shock_atr_multiple", "REAL")
        _ensure_column(conn, "evaluated_opportunities", "shock_lookback_bars", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "evaluated_opportunities", "shock_direction", "TEXT NOT NULL DEFAULT 'none'")
        _ensure_column(conn, "evaluated_opportunities", "shock_suppression_until", "TEXT")
        _ensure_column(conn, "evaluated_opportunities", "shock_suppression_candles_remaining", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "evaluated_opportunities", "raw_lr_1h", "REAL")
        _ensure_column(conn, "evaluated_opportunities", "raw_lr_15m", "REAL")
        _ensure_column(conn, "evaluated_opportunities", "raw_lr_5m", "REAL")
        _ensure_column(conn, "evaluated_opportunities", "filtered_lr_1h", "REAL")
        _ensure_column(conn, "evaluated_opportunities", "filtered_lr_15m", "REAL")
        _ensure_column(conn, "evaluated_opportunities", "filtered_lr_5m", "REAL")
        _ensure_column(conn, "evaluated_opportunities", "trend_changed_after_filter", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "evaluated_opportunities", "market_validity_state", "TEXT NOT NULL DEFAULT 'valid'")
        _ensure_column(conn, "evaluated_opportunities", "market_validity_reason", "TEXT")
    _initialized_db_paths.add(db_key)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Add an additive SQLite column when an existing metrics database predates it."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _write_connection(db_path: Path) -> sqlite3.Connection:
    """Return a reusable SQLite write connection for high-volume diagnostic inserts."""
    db_key = str(db_path.resolve())
    conn = _write_connections_by_db_path.get(db_key)
    if conn is None:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _write_connections_by_db_path[db_key] = conn
    return conn


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


def record_opportunity(opportunity: EvaluatedOpportunity, db_path: Path = DB_FILE) -> EvaluatedOpportunity:
    opportunity = validate_opportunity(opportunity)
    init_schema(db_path)
    with _lock:
        conn = _write_connection(db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO evaluated_opportunities (
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
        conn.execute("DELETE FROM criterion_results WHERE opportunity_id = ?", (opportunity.id,))
        criterion_rows = [
            (
                opportunity.id,
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
        if criterion_rows:
            conn.executemany(
                """
                INSERT INTO criterion_results (
                    opportunity_id, criterion_name, layer, measured_value, threshold_value,
                    threshold_operator, passed, expected_pass, pass_mismatch, margin,
                    normalized_margin, required, blocked_signal, data_quality, diagnostic_state,
                    reason, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                criterion_rows,
            )
        conn.commit()
    _prune_retention_if_due(db_path=db_path)
    return opportunity


def _prune_retention_if_due(db_path: Path = DB_FILE, interval: timedelta = timedelta(hours=1)) -> int:
    """Prune old diagnostics at most once per interval for each database path."""
    db_key = str(db_path.resolve())
    now = datetime.now(timezone.utc)
    last_prune = _last_prune_by_db_path.get(db_key)
    if last_prune is not None and now - last_prune < interval:
        return 0
    removed = prune_retention(db_path=db_path)
    _last_prune_by_db_path[db_key] = now
    return removed


def prune_retention(days: Optional[int] = None, db_path: Path = DB_FILE) -> int:
    days = days or config.STRATEGY_METRICS_RETENTION_DAYS
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    init_schema(db_path)
    with _lock, sqlite3.connect(db_path) as conn:
        old_ids = [r[0] for r in conn.execute("SELECT id FROM evaluated_opportunities WHERE evaluated_at < ?", (cutoff,))]
        if old_ids:
            conn.executemany("DELETE FROM criterion_results WHERE opportunity_id = ?", [(i,) for i in old_ids])
            conn.executemany("DELETE FROM evaluated_opportunities WHERE id = ?", [(i,) for i in old_ids])
    return len(old_ids)


def _row_to_opportunity(row: sqlite3.Row, criteria: list[CriterionResult]) -> EvaluatedOpportunity:
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
    limit: int = 100,
    offset: int = 0,
    db_path: Path = DB_FILE,
) -> list[dict[str, Any]]:
    init_schema(db_path)
    limit = max(1, min(int(limit), config.STRATEGY_METRICS_MAX_OPPORTUNITIES))
    offset = max(0, int(offset))
    where_sql, params, _, _ = _opportunity_filter_clauses(
        start,
        end,
        symbol=symbol,
        decision=decision,
        strategy=strategy,
        signal_type=signal_type,
        first_blocker=first_blocker,
        near_miss=near_miss,
    )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM evaluated_opportunities WHERE {where_sql} ORDER BY evaluated_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        ids = [row["id"] for row in rows]
        criteria_by_opportunity: dict[str, list[CriterionResult]] = {opportunity_id: [] for opportunity_id in ids}
        if ids:
            placeholders = ",".join("?" for _ in ids)
            crit_rows = conn.execute(
                f"SELECT * FROM criterion_results WHERE opportunity_id IN ({placeholders}) ORDER BY opportunity_id, id",
                ids,
            ).fetchall()
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
                        expected_pass=None if "expected_pass" not in c.keys() or c["expected_pass"] is None else bool(c["expected_pass"]),
                        pass_mismatch=bool(c["pass_mismatch"]) if "pass_mismatch" in c.keys() else False,
                        margin=c["margin"],
                        normalized_margin=c["normalized_margin"],
                        required=bool(c["required"]),
                        blocked_signal=bool(c["blocked_signal"]),
                        data_quality=c["data_quality"],
                        diagnostic_state=c["diagnostic_state"] if "diagnostic_state" in c.keys() else "evaluated",
                        reason=c["reason"] if "reason" in c.keys() else None,
                        context=json.loads(c["context"] or "{}") if "context" in c.keys() else {},
                    )
                )
        result = []
        for row in rows:
            criteria = criteria_by_opportunity.get(row["id"], [])
            result.append(_row_to_opportunity(row, criteria).to_dict())
        return result


def _criterion_summaries(conn: sqlite3.Connection, where_sql: str, params: list[Any]) -> list[CriterionSummary]:
    rows = conn.execute(
        f"""
        SELECT c.criterion_name,
               COUNT(*) AS evaluated_count,
               SUM(CASE WHEN c.passed = 1 THEN 1 ELSE 0 END) AS pass_count,
               SUM(CASE WHEN c.passed = 0 THEN 1 ELSE 0 END) AS fail_count,
               SUM(CASE WHEN c.data_quality != 'complete' THEN 1 ELSE 0 END) AS incomplete_count,
               AVG(CASE WHEN c.passed = 0 THEN ABS(c.margin) ELSE NULL END) AS average_failure_margin,
               SUM(CASE WHEN o.near_miss = 1 AND c.blocked_signal = 1 THEN 1 ELSE 0 END) AS near_miss_contribution
        FROM criterion_results c
        JOIN evaluated_opportunities o ON o.id = c.opportunity_id
        WHERE {where_sql}
        GROUP BY c.criterion_name
        ORDER BY c.criterion_name
        """,
        params,
    ).fetchall()
    summaries = []
    for name, evaluated, passed, failed, incomplete, avg_margin, near_miss_contribution in rows:
        evaluated = evaluated or 0
        passed = passed or 0
        failed = failed or 0
        summaries.append(
            CriterionSummary(
                criterion_name=name,
                evaluated_count=evaluated,
                pass_count=passed,
                fail_count=failed,
                pass_rate=round(passed / evaluated, 4) if evaluated else 0.0,
                fail_rate=round(failed / evaluated, 4) if evaluated else 0.0,
                near_miss_contribution=int(near_miss_contribution or 0),
                average_failure_margin=None if avg_margin is None else round(float(avg_margin), 6),
                incomplete_count=incomplete or 0,
            )
        )
    return summaries


def _blocker_summaries(conn: sqlite3.Connection, where_sql: str, params: list[Any], blocked_opportunity_count: int) -> list[BlockerSummary]:
    """Summarize blockers with SQL JSON aggregation instead of loading all rows."""
    if not blocked_opportunity_count:
        return []
    rows = conn.execute(
        f"""
        SELECT
            CAST(blocker.value AS TEXT) AS criterion_name,
            COUNT(DISTINCT o.id) AS blocked_count,
            AVG(CASE
                WHEN c.normalized_margin IS NULL THEN NULL
                WHEN ABS(c.normalized_margin) > 1.0 THEN 0.0
                ELSE 1.0 - ABS(c.normalized_margin)
            END) AS margin_component,
            AVG(CASE
                WHEN req.total_required > 1 THEN CAST(req.passed_required AS REAL) / (req.total_required - 1)
                ELSE 0.0
            END) AS quality_component,
            GROUP_CONCAT(DISTINCT o.id) AS example_ids
        FROM evaluated_opportunities o
        JOIN json_each(o.all_blockers) blocker
        LEFT JOIN criterion_results c
            ON c.opportunity_id = o.id
           AND c.criterion_name = CAST(blocker.value AS TEXT)
        LEFT JOIN (
            SELECT opportunity_id,
                   COUNT(*) AS total_required,
                   SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS passed_required
            FROM criterion_results
            WHERE required = 1
            GROUP BY opportunity_id
        ) req ON req.opportunity_id = o.id
        WHERE {where_sql}
          AND o.all_blockers != '[]'
        GROUP BY CAST(blocker.value AS TEXT)
        ORDER BY blocked_count DESC, criterion_name
        LIMIT 50
        """,
        params,
    ).fetchall()
    result = []
    for name, blocked_count, margin_component, quality_component, example_ids in rows:
        frequency = int(blocked_count or 0) / blocked_opportunity_count
        margin = 0.0 if margin_component is None else max(0.0, min(1.0, float(margin_component)))
        quality = 0.0 if quality_component is None else max(0.0, min(1.0, float(quality_component)))
        combined = (frequency * 0.40) + (margin * 0.30) + (quality * 0.30)
        examples = sorted(str(example_ids or "").split(","))[:5]
        result.append(
            BlockerSummary(
                criterion_name=name,
                blocked_count=int(blocked_count or 0),
                frequency_component=round(frequency, 4),
                margin_component=round(margin, 4),
                quality_component=round(quality, 4),
                combined_score=round(combined, 4),
                example_opportunity_ids=[example for example in examples if example],
            )
        )
    return sorted(result, key=lambda b: (-b.combined_score, -b.blocked_count, b.criterion_name))


def _pipeline_funnel(conn: sqlite3.Connection, where_sql: str, params: list[Any], total: int) -> dict[str, int]:
    """Build stage counts with SQL so large ranges do not materialize rows."""
    row = conn.execute(
        f"""
        SELECT
            SUM(CASE
                WHEN o.decision_reason = 'no_trend'
                  OR o.pipeline_state = 'trend_skipped'
                  OR EXISTS (
                      SELECT 1 FROM json_each(o.all_blockers) blocker
                      WHERE CAST(blocker.value AS TEXT) LIKE 'trend:%'
                  )
                THEN 1 ELSE 0
            END) AS trend_skipped,
            SUM(CASE
                WHEN o.data_complete = 0
                  OR EXISTS (
                      SELECT 1 FROM json_each(o.all_blockers) blocker
                      WHERE CAST(blocker.value AS TEXT) LIKE 'signal_engine_data:%'
                  )
                THEN 1 ELSE 0
            END) AS signal_data_missing,
            SUM(CASE WHEN o.final_decision = 'rejected' THEN 1 ELSE 0 END) AS signal_rejected,
            SUM(CASE WHEN o.final_decision = 'emitted' THEN 1 ELSE 0 END) AS signal_emitted,
            SUM(CASE WHEN o.final_decision = 'indeterminate' THEN 1 ELSE 0 END) AS indeterminate
        FROM evaluated_opportunities o
        WHERE {where_sql}
        """,
        params,
    ).fetchone()
    trend_skipped = int(row["trend_skipped"] or 0) if row else 0
    signal_data_missing = int(row["signal_data_missing"] or 0) if row else 0
    signal_rejected = int(row["signal_rejected"] or 0) if row else 0
    signal_emitted = int(row["signal_emitted"] or 0) if row else 0
    indeterminate = int(row["indeterminate"] or 0) if row else 0
    candle_row = conn.execute(
        f"""
        SELECT
            COUNT(DISTINCT CASE WHEN c.criterion_name = 'candle_close_gate' AND c.passed = 1 THEN o.id END) AS candle_passed,
            COUNT(DISTINCT CASE WHEN c.criterion_name = 'candle_close_gate' AND (c.passed = 0 OR c.passed IS NULL) THEN o.id END) AS candle_waiting_or_failed,
            COUNT(DISTINCT CASE WHEN c.criterion_name IN ('stoch_rsi', 'macd', 'keltner', 'confidence') THEN o.id END) AS signal_rules_evaluated
        FROM evaluated_opportunities o
        JOIN criterion_results c ON c.opportunity_id = o.id
        WHERE {where_sql}
        """,
        params,
    ).fetchone()
    trend_candidate_found = max(0, total - trend_skipped)
    return {
        "total_evaluated": total,
        "trend_skipped": trend_skipped,
        "trend_candidate_found": trend_candidate_found,
        "signal_data_complete": max(0, trend_candidate_found - signal_data_missing),
        "signal_data_missing": signal_data_missing,
        "candle_close_gate_passed": int(candle_row["candle_passed"] or 0) if candle_row else 0,
        "candle_close_gate_waiting_or_failed": int(candle_row["candle_waiting_or_failed"] or 0) if candle_row else 0,
        "signal_rules_evaluated": int(candle_row["signal_rules_evaluated"] or 0) if candle_row else 0,
        "signal_rejected": signal_rejected,
        "signal_emitted": signal_emitted,
        "indeterminate": indeterminate,
    }


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


def _count_by(conn: sqlite3.Connection, column: str, where_sql: str, params: list[Any], *, fallback: str = "unknown") -> dict[str, int]:
    rows = conn.execute(
        f"""
        SELECT COALESCE(NULLIF({column}, ''), ?) AS name, COUNT(*) AS count
        FROM evaluated_opportunities o
        WHERE {where_sql}
        GROUP BY COALESCE(NULLIF({column}, ''), ?)
        """,
        (fallback, *params, fallback),
    ).fetchall()
    return {str(row["name"]): int(row["count"] or 0) for row in rows}


def get_summary(
    start: str,
    end: str,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    signal_type: Optional[str] = None,
    decision: Optional[str] = None,
    first_blocker: Optional[str] = None,
    db_path: Path = DB_FILE,
) -> dict[str, Any]:
    init_schema(db_path)
    where_sql, params, start_iso, end_iso = _opportunity_filter_clauses(
        start,
        end,
        symbol=symbol,
        decision=decision,
        strategy=strategy,
        signal_type=signal_type,
        first_blocker=first_blocker,
        table_alias="o",
    )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        totals = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN o.final_decision = 'emitted' THEN 1 ELSE 0 END) AS emitted,
                SUM(CASE WHEN o.final_decision = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN o.final_decision = 'skipped' THEN 1 ELSE 0 END) AS skipped,
                SUM(CASE WHEN o.final_decision = 'indeterminate' THEN 1 ELSE 0 END) AS indeterminate,
                SUM(CASE WHEN o.near_miss = 1 THEN 1 ELSE 0 END) AS near_miss_count,
                SUM(CASE WHEN o.final_decision = 'emitted' AND o.usable_for_strategy_stats = 1 THEN 1 ELSE 0 END) AS trade_opportunity_count,
                SUM(CASE WHEN o.final_decision = 'emitted' AND o.usable_for_strategy_stats = 0 THEN 1 ELSE 0 END) AS stats_excluded_count,
                SUM(CASE WHEN o.final_decision = 'emitted' AND o.usable_for_strategy_stats IS NULL THEN 1 ELSE 0 END) AS stats_unknown_eligibility_count,
                SUM(CASE WHEN o.data_complete = 0 THEN 1 ELSE 0 END) AS incomplete_count,
                COUNT(DISTINCT o.threshold_version) AS threshold_versions
            FROM evaluated_opportunities o
            WHERE {where_sql}
            """,
            params,
        ).fetchone()
        total = int(totals["total"] or 0)
        emitted = int(totals["emitted"] or 0)
        rejected = int(totals["rejected"] or 0)
        skipped = int(totals["skipped"] or 0)
        indeterminate = int(totals["indeterminate"] or 0)
        near_miss_count = int(totals["near_miss_count"] or 0)
        trade_opportunity_count = int(totals["trade_opportunity_count"] or 0)
        stats_excluded_count = int(totals["stats_excluded_count"] or 0)
        stats_unknown_eligibility_count = int(totals["stats_unknown_eligibility_count"] or 0)
        threshold_version_counts = _count_by(conn, "o.threshold_version", where_sql, params)
        strategy_counts = _count_by(conn, "o.strategy", where_sql, params)
        signal_type_counts = _count_by(conn, "o.signal_type", where_sql, params)
        stats_exclusion_counts = dict(
            conn.execute(
                f"""
                SELECT COALESCE(NULLIF(o.stats_exclusion_reason, ''), 'unknown') AS reason, COUNT(*) AS count
                FROM evaluated_opportunities o
                WHERE {where_sql}
                  AND o.final_decision = 'emitted'
                  AND o.usable_for_strategy_stats = 0
                GROUP BY COALESCE(NULLIF(o.stats_exclusion_reason, ''), 'unknown')
                """,
                params,
            ).fetchall()
        )
        threshold_version_unknown_reasons = dict(
            conn.execute(
                f"""
                SELECT COALESCE(NULLIF(o.threshold_version_unknown_reason, ''), 'legacy_or_missing_threshold_version') AS reason,
                       COUNT(*) AS count
                FROM evaluated_opportunities o
                WHERE {where_sql}
                  AND COALESCE(NULLIF(o.threshold_version, ''), 'unknown') = 'unknown'
                GROUP BY COALESCE(NULLIF(o.threshold_version_unknown_reason, ''), 'legacy_or_missing_threshold_version')
                """,
                params,
            ).fetchall()
        )
        near_miss_reason_counts = dict(
            conn.execute(
                f"""
                SELECT o.near_miss_reason, COUNT(*) AS count
                FROM evaluated_opportunities o
                WHERE {where_sql}
                  AND o.near_miss = 1
                  AND o.near_miss_reason IS NOT NULL
                GROUP BY o.near_miss_reason
                """,
                params,
            ).fetchall()
        )
        blocker_rows = conn.execute(
            f"""
            SELECT DISTINCT CAST(blocker.value AS TEXT) AS blocker
            FROM evaluated_opportunities o
            JOIN json_each(o.all_blockers) blocker
            WHERE {where_sql}
            ORDER BY blocker
            """,
            params,
        ).fetchall()
        all_blockers = [row["blocker"] for row in blocker_rows if row["blocker"]]
        first_blocker_row = conn.execute(
            f"""
            SELECT o.first_blocker, o.blocking_layer
            FROM evaluated_opportunities o
            WHERE {where_sql} AND o.first_blocker IS NOT NULL
            ORDER BY o.evaluated_at ASC
            LIMIT 1
            """,
            params,
        ).fetchone()
        summary_first_blocker = first_blocker_row["first_blocker"] if first_blocker_row else None
        blocking_layer = first_blocker_row["blocking_layer"] if first_blocker_row else None
        blocked_opportunity_count = int(
            conn.execute(
                f"SELECT COUNT(*) FROM evaluated_opportunities o WHERE {where_sql} AND o.all_blockers != '[]'",
                params,
            ).fetchone()[0]
            or 0
        )
        warnings: list[str] = []
        if total == 0:
            warnings.append("No evaluated opportunities in selected period")
        if int(totals["incomplete_count"] or 0):
            warnings.append("Some opportunities have incomplete diagnostics")
        if int(totals["threshold_versions"] or 0) > 1:
            warnings.append("Strategy threshold version changed during selected period")

        prime_summary = _prime_suppression_summary(start_iso, end_iso, symbol)
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
            criterion_summaries=_criterion_summaries(conn, where_sql, params),
            top_blockers=_blocker_summaries(conn, where_sql, params, blocked_opportunity_count),
            first_blocker=summary_first_blocker,
            all_blockers=all_blockers,
            blocking_layer=blocking_layer,
            threshold_version_counts=threshold_version_counts,
            strategy_counts=strategy_counts,
            signal_type_counts=signal_type_counts,
            threshold_version_unknown_reasons=threshold_version_unknown_reasons,
            near_miss_reason_counts=near_miss_reason_counts,
            pipeline_funnel=_pipeline_funnel(conn, where_sql, params, total),
            data_quality_warnings=warnings,
        )
        return summary.to_dict()


def compare_periods(
    base_start: str,
    base_end: str,
    compare_start: str,
    compare_end: str,
    symbol: Optional[str] = None,
    db_path: Path = DB_FILE,
) -> dict[str, Any]:
    baseline = DiagnosticSummary(**_summary_dataclass_kwargs(get_summary(base_start, base_end, symbol=symbol, db_path=db_path)))
    comparison = DiagnosticSummary(**_summary_dataclass_kwargs(get_summary(compare_start, compare_end, symbol=symbol, db_path=db_path)))
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
    db_path: Path = DB_FILE,
) -> dict[str, Any]:
    payload = {
        "summary": get_summary(
            start,
            end,
            symbol=symbol,
            strategy=strategy,
            signal_type=signal_type,
            decision=decision,
            first_blocker=first_blocker,
            db_path=db_path,
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
            db_path=db_path,
        )
    return payload


def write_state_snapshot(summary: dict[str, Any], state_file: Path = STATE_FILE) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": _now_iso(), "summary": summary}
    tmp = state_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(state_file)

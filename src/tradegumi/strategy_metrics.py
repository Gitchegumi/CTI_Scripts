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
    criterion_summaries: list[CriterionSummary] = field(default_factory=list)
    top_blockers: list[BlockerSummary] = field(default_factory=list)
    first_blocker: Optional[str] = None   # criterion_name of the first blocker
    all_blockers: list[str] = field(default_factory=list)  # all blocking criterion_names
    blocking_layer: Optional[str] = None  # layer of the first blocker
    threshold_version_counts: dict[str, int] = field(default_factory=dict)
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
                id, evaluated_at, symbol, timeframe, mode, strategy, direction, trend,
                final_decision, decision_reason, confidence, failed_criteria_count,
                near_miss, data_complete, data_quality_notes, threshold_version, created_at,
                first_blocker, all_blockers, blocking_layer, trend_decision, pipeline_state,
                near_miss_reason, threshold_version_unknown_reason, usable_for_strategy_stats,
                stats_exclusion_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity.id,
                opportunity.evaluated_at,
                opportunity.symbol,
                opportunity.timeframe,
                opportunity.mode,
                opportunity.strategy,
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
            ),
        )
        conn.execute("DELETE FROM criterion_results WHERE opportunity_id = ?", (opportunity.id,))
        for criterion in opportunity.criteria:
            conn.execute(
                """
                INSERT INTO criterion_results (
                    opportunity_id, criterion_name, layer, measured_value, threshold_value,
                    threshold_operator, passed, expected_pass, pass_mismatch, margin,
                    normalized_margin, required, blocked_signal, data_quality, diagnostic_state,
                    reason, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
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
                ),
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
    )


def get_opportunities(
    start: str,
    end: str,
    symbol: Optional[str] = None,
    decision: Optional[str] = None,
    near_miss: Optional[bool] = None,
    limit: int = 100,
    db_path: Path = DB_FILE,
) -> list[dict[str, Any]]:
    init_schema(db_path)
    limit = max(1, min(int(limit), config.STRATEGY_METRICS_MAX_OPPORTUNITIES))
    start_iso, end_iso = _normalize_range_bounds(start, end)
    clauses = ["evaluated_at >= ?", "evaluated_at < ?"]
    params: list[Any] = [start_iso, end_iso]
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol.upper())
    if decision:
        clauses.append("final_decision = ?")
        params.append(decision)
    if near_miss is not None:
        clauses.append("near_miss = ?")
        params.append(int(near_miss))

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM evaluated_opportunities WHERE {' AND '.join(clauses)} ORDER BY evaluated_at DESC LIMIT ?",
            (*params, limit),
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


def _criterion_summaries(conn: sqlite3.Connection, ids: list[str]) -> list[CriterionSummary]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT criterion_name,
               COUNT(*) AS evaluated_count,
               SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS pass_count,
               SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) AS fail_count,
               SUM(CASE WHEN data_quality != 'complete' THEN 1 ELSE 0 END) AS incomplete_count,
               AVG(CASE WHEN passed = 0 THEN ABS(margin) ELSE NULL END) AS average_failure_margin
        FROM criterion_results
        WHERE opportunity_id IN ({placeholders})
        GROUP BY criterion_name
        ORDER BY criterion_name
        """,
        ids,
    ).fetchall()
    near_miss = dict(
        conn.execute(
            f"""
            SELECT c.criterion_name, COUNT(*)
            FROM criterion_results c
            JOIN evaluated_opportunities o ON o.id = c.opportunity_id
            WHERE c.opportunity_id IN ({placeholders}) AND o.near_miss = 1 AND c.blocked_signal = 1
            GROUP BY c.criterion_name
            """,
            ids,
        ).fetchall()
    )
    summaries = []
    for name, evaluated, passed, failed, incomplete, avg_margin in rows:
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
                near_miss_contribution=int(near_miss.get(name, 0)),
                average_failure_margin=None if avg_margin is None else round(float(avg_margin), 6),
                incomplete_count=incomplete or 0,
            )
        )
    return summaries


def _blocker_summaries(conn: sqlite3.Connection, ids: list[str], blocked_opportunity_count: int) -> list[BlockerSummary]:
    """Summarize blockers from opportunity blocker fields, with legacy criterion fallback."""
    if not ids or not blocked_opportunity_count:
        return []
    placeholders = ",".join("?" for _ in ids)
    opportunity_rows = conn.execute(
        f"SELECT id, all_blockers FROM evaluated_opportunities WHERE id IN ({placeholders}) AND all_blockers != '[]'",
        ids,
    ).fetchall()
    blockers_by_name: dict[str, set[str]] = {}
    for opp_id, blockers_json in opportunity_rows:
        blockers = json.loads(blockers_json or "[]")
        if not blockers:
            legacy_rows = conn.execute(
                """
                SELECT criterion_name
                FROM criterion_results
                WHERE opportunity_id = ? AND required = 1 AND passed = 0
                """,
                (opp_id,),
            ).fetchall()
            blockers = [row[0] for row in legacy_rows]
        for blocker in blockers:
            blockers_by_name.setdefault(str(blocker), set()).add(opp_id)

    result = []
    for name, opp_id_set in blockers_by_name.items():
        opp_ids = sorted(opp_id_set)
        blocked_count = len(opp_ids)
        margin_component = conn.execute(
            f"""
            SELECT AVG(CASE WHEN normalized_margin IS NULL THEN NULL ELSE 1.0 - MIN(1.0, ABS(normalized_margin)) END)
            FROM criterion_results
            WHERE opportunity_id IN ({",".join("?" for _ in opp_ids)}) AND criterion_name = ?
            """,
            (*opp_ids, name),
        ).fetchone()[0]
        quality_values = []
        for opp_id in opp_ids:
            total, passed = conn.execute(
                """
                SELECT COUNT(*), SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END)
                FROM criterion_results
                WHERE opportunity_id = ? AND required = 1 AND criterion_name != ?
                """,
                (opp_id, name),
            ).fetchone()
            if total:
                quality_values.append((passed or 0) / total)
        frequency = blocked_count / blocked_opportunity_count
        margin = 0.0 if margin_component is None else max(0.0, min(1.0, float(margin_component)))
        quality = sum(quality_values) / len(quality_values) if quality_values else 0.0
        combined = (frequency * 0.40) + (margin * 0.30) + (quality * 0.30)
        result.append(
            BlockerSummary(
                criterion_name=name,
                blocked_count=blocked_count,
                frequency_component=round(frequency, 4),
                margin_component=round(margin, 4),
                quality_component=round(quality, 4),
                combined_score=round(combined, 4),
                example_opportunity_ids=opp_ids[:5],
            )
        )
    return sorted(result, key=lambda b: (-b.combined_score, -b.blocked_count, b.criterion_name))


def _pipeline_funnel(rows: list[sqlite3.Row], criterion_rows: list[sqlite3.Row]) -> dict[str, int]:
    """Build stage counts that show where candidates fall out of the pipeline."""
    criteria_by_opp: dict[str, list[sqlite3.Row]] = {}
    for criterion in criterion_rows:
        criteria_by_opp.setdefault(criterion["opportunity_id"], []).append(criterion)

    trend_skipped = 0
    signal_data_missing = 0
    candle_gate_passed: set[str] = set()
    candle_gate_waiting_or_failed: set[str] = set()
    signal_rules_evaluated: set[str] = set()

    for row in rows:
        blockers = json.loads(row["all_blockers"] or "[]")
        pipeline_state = row["pipeline_state"] or ""
        if row["decision_reason"] == "no_trend" or pipeline_state == "trend_skipped" or any(b.startswith("trend:") for b in blockers):
            trend_skipped += 1
        if row["data_complete"] == 0 or any(b.startswith("signal_engine_data:") for b in blockers):
            signal_data_missing += 1
        for criterion in criteria_by_opp.get(row["id"], []):
            name = criterion["criterion_name"]
            if name == "candle_close_gate":
                if criterion["passed"] == 1:
                    candle_gate_passed.add(row["id"])
                else:
                    candle_gate_waiting_or_failed.add(row["id"])
            if name in {"stoch_rsi", "macd", "keltner", "confidence"}:
                signal_rules_evaluated.add(row["id"])

    trend_candidate_found = max(0, len(rows) - trend_skipped)
    return {
        "total_evaluated": len(rows),
        "trend_skipped": trend_skipped,
        "trend_candidate_found": trend_candidate_found,
        "signal_data_complete": max(0, trend_candidate_found - signal_data_missing),
        "signal_data_missing": signal_data_missing,
        "candle_close_gate_passed": len(candle_gate_passed),
        "candle_close_gate_waiting_or_failed": len(candle_gate_waiting_or_failed),
        "signal_rules_evaluated": len(signal_rules_evaluated),
        "signal_rejected": sum(1 for row in rows if row["final_decision"] == "rejected"),
        "signal_emitted": sum(1 for row in rows if row["final_decision"] == "emitted"),
        "indeterminate": sum(1 for row in rows if row["final_decision"] == "indeterminate"),
    }


def get_summary(start: str, end: str, symbol: Optional[str] = None, db_path: Path = DB_FILE) -> dict[str, Any]:
    init_schema(db_path)
    start_iso, end_iso = _normalize_range_bounds(start, end)
    clauses = ["evaluated_at >= ?", "evaluated_at < ?"]
    params: list[Any] = [start_iso, end_iso]
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol.upper())

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT id, final_decision, decision_reason, near_miss, near_miss_reason,
                   data_complete, threshold_version, threshold_version_unknown_reason,
                   first_blocker, all_blockers, blocking_layer, pipeline_state,
                   usable_for_strategy_stats, stats_exclusion_reason
            FROM evaluated_opportunities
            WHERE {' AND '.join(clauses)}
            """,
            params,
        ).fetchall()
        ids = [r["id"] for r in rows]
        total = len(rows)
        emitted = sum(1 for r in rows if r["final_decision"] == "emitted")
        rejected = sum(1 for r in rows if r["final_decision"] == "rejected")
        skipped = sum(1 for r in rows if r["final_decision"] == "skipped")
        indeterminate = sum(1 for r in rows if r["final_decision"] == "indeterminate")
        near_miss_count = sum(1 for r in rows if r["near_miss"])
        emitted_rows = [r for r in rows if r["final_decision"] == "emitted"]
        trade_opportunity_count = sum(1 for r in emitted_rows if r["usable_for_strategy_stats"] == 1)
        stats_excluded_count = sum(1 for r in emitted_rows if r["usable_for_strategy_stats"] == 0)
        stats_unknown_eligibility_count = sum(1 for r in emitted_rows if r["usable_for_strategy_stats"] is None)
        stats_exclusion_counts: dict[str, int] = {}
        for row in emitted_rows:
            if row["usable_for_strategy_stats"] == 0:
                reason = row["stats_exclusion_reason"] or "unknown"
                stats_exclusion_counts[reason] = stats_exclusion_counts.get(reason, 0) + 1
        threshold_version_counts: dict[str, int] = {}
        threshold_version_unknown_reasons: dict[str, int] = {}
        near_miss_reason_counts: dict[str, int] = {}
        all_blockers: list[str] = []
        first_blocker = None
        blocking_layer = None
        for row in rows:
            version = row["threshold_version"] or "unknown"
            threshold_version_counts[version] = threshold_version_counts.get(version, 0) + 1
            if version == "unknown":
                unknown_reason = row["threshold_version_unknown_reason"] or "legacy_or_missing_threshold_version"
                threshold_version_unknown_reasons[unknown_reason] = threshold_version_unknown_reasons.get(unknown_reason, 0) + 1
            if row["near_miss"] and row["near_miss_reason"]:
                near_miss_reason_counts[row["near_miss_reason"]] = near_miss_reason_counts.get(row["near_miss_reason"], 0) + 1
            blockers = json.loads(row["all_blockers"] or "[]")
            all_blockers.extend(blockers)
            if first_blocker is None and row["first_blocker"]:
                first_blocker = row["first_blocker"]
                blocking_layer = row["blocking_layer"]
        warnings: list[str] = []
        if total == 0:
            warnings.append("No evaluated opportunities in selected period")
        if any(not r["data_complete"] for r in rows):
            warnings.append("Some opportunities have incomplete diagnostics")
        if len({r["threshold_version"] for r in rows}) > 1:
            warnings.append("Strategy threshold version changed during selected period")
        criterion_rows = []
        if ids:
            placeholders = ",".join("?" for _ in ids)
            criterion_rows = conn.execute(
                f"SELECT opportunity_id, criterion_name, passed FROM criterion_results WHERE opportunity_id IN ({placeholders})",
                ids,
            ).fetchall()

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
            criterion_summaries=_criterion_summaries(conn, ids),
            top_blockers=_blocker_summaries(conn, ids, sum(1 for r in rows if json.loads(r["all_blockers"] or "[]"))),
            first_blocker=first_blocker,
            all_blockers=sorted(set(all_blockers)),
            blocking_layer=blocking_layer,
            threshold_version_counts=threshold_version_counts,
            threshold_version_unknown_reasons=threshold_version_unknown_reasons,
            near_miss_reason_counts=near_miss_reason_counts,
            pipeline_funnel=_pipeline_funnel(rows, criterion_rows),
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
    baseline = DiagnosticSummary(**_summary_dataclass_kwargs(get_summary(base_start, base_end, symbol, db_path)))
    comparison = DiagnosticSummary(**_summary_dataclass_kwargs(get_summary(compare_start, compare_end, symbol, db_path)))
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
    include_opportunities: bool = False,
    db_path: Path = DB_FILE,
) -> dict[str, Any]:
    payload = {"summary": get_summary(start, end, symbol, db_path)}
    if include_opportunities:
        payload["opportunities"] = get_opportunities(start, end, symbol=symbol, limit=config.STRATEGY_METRICS_MAX_OPPORTUNITIES, db_path=db_path)
    return payload


def write_state_snapshot(summary: dict[str, Any], state_file: Path = STATE_FILE) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": _now_iso(), "summary": summary}
    tmp = state_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(state_file)

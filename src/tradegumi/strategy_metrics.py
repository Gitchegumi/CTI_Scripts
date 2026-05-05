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
_lock = threading.Lock()


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
    criterion_summaries: list[CriterionSummary] = field(default_factory=list)
    top_blockers: list[BlockerSummary] = field(default_factory=list)
    first_blocker: Optional[str] = None   # criterion_name of the first blocker
    all_blockers: list[str] = field(default_factory=list)  # all blocking criterion_names
    blocking_layer: Optional[str] = None  # layer of the first blocker
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
                created_at TEXT NOT NULL
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
                margin REAL,
                normalized_margin REAL,
                required INTEGER NOT NULL,
                blocked_signal INTEGER NOT NULL,
                data_quality TEXT NOT NULL,
                FOREIGN KEY(opportunity_id) REFERENCES evaluated_opportunities(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_at ON evaluated_opportunities(evaluated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_symbol ON evaluated_opportunities(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_decision ON evaluated_opportunities(final_decision)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_criteria_opp ON criterion_results(opportunity_id)")


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
    if opportunity.final_decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid final_decision: {opportunity.final_decision}")
    if not opportunity.symbol:
        raise ValueError("symbol is required")
    if not opportunity.evaluated_at:
        raise ValueError("evaluated_at is required")
    if not opportunity.decision_reason:
        raise ValueError("decision_reason is required")

    failed_required = 0
    complete = True
    notes = list(opportunity.data_quality_notes)
    for criterion in opportunity.criteria:
        if criterion.data_quality not in VALID_DATA_QUALITY:
            raise ValueError(f"Invalid data_quality: {criterion.data_quality}")
        if criterion.data_quality in {"missing", "malformed"}:
            complete = False
            notes.append(f"{criterion.criterion_name}:{criterion.data_quality}")
        # Compute expected_pass and pass_mismatch
        criterion.expected_pass = _compute_threshold_pass(
            criterion.measured_value, criterion.threshold_value, criterion.threshold_operator
        )
        if criterion.expected_pass is not None and criterion.passed is not None:
            criterion.pass_mismatch = criterion.expected_pass != criterion.passed
        if criterion.required and criterion.passed is False:
            failed_required += 1
            if opportunity.final_decision == "rejected":
                criterion.blocked_signal = True

    # Populate first_blocker / all_blockers / blocking_layer for rejected opportunitites
    if opportunity.final_decision == "rejected":
        blockers = [c for c in opportunity.criteria if c.blocked_signal]
        blockers.sort(key=lambda c: c.criterion_name)  # stable order
        opportunity.all_blockers = [c.criterion_name for c in blockers]
        if blockers:
            opportunity.first_blocker = blockers[0].criterion_name
            opportunity.blocking_layer = blockers[0].layer

    opportunity.failed_criteria_count = failed_required
    opportunity.near_miss = opportunity.final_decision == "rejected" and failed_required == 1
    opportunity.data_complete = complete and opportunity.data_complete
    opportunity.data_quality_notes = sorted(set(notes))
    return opportunity


def record_opportunity(opportunity: EvaluatedOpportunity, db_path: Path = DB_FILE) -> EvaluatedOpportunity:
    opportunity = validate_opportunity(opportunity)
    init_schema(db_path)
    with _lock, sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO evaluated_opportunities (
                id, evaluated_at, symbol, timeframe, mode, strategy, direction, trend,
                final_decision, decision_reason, confidence, failed_criteria_count,
                near_miss, data_complete, data_quality_notes, threshold_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        conn.execute("DELETE FROM criterion_results WHERE opportunity_id = ?", (opportunity.id,))
        for criterion in opportunity.criteria:
            conn.execute(
                """
                INSERT INTO criterion_results (
                    opportunity_id, criterion_name, layer, measured_value, threshold_value,
                    threshold_operator, passed, margin, normalized_margin, required,
                    blocked_signal, data_quality
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    opportunity.id,
                    criterion.criterion_name,
                    criterion.layer,
                    json.dumps(criterion.measured_value),
                    json.dumps(criterion.threshold_value),
                    criterion.threshold_operator,
                    None if criterion.passed is None else int(criterion.passed),
                    criterion.margin,
                    criterion.normalized_margin,
                    int(criterion.required),
                    int(criterion.blocked_signal),
                    criterion.data_quality,
                ),
            )
    prune_retention(db_path=db_path)
    return opportunity


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
    clauses = ["evaluated_at >= ?", "evaluated_at < ?"]
    params: list[Any] = [_parse_dt(start).isoformat(), _parse_dt(end).isoformat()]
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
        result = []
        for row in rows:
            crit_rows = conn.execute(
                "SELECT * FROM criterion_results WHERE opportunity_id = ? ORDER BY id",
                (row["id"],),
            ).fetchall()
            criteria = [
                CriterionResult(
                    id=c["id"],
                    opportunity_id=c["opportunity_id"],
                    criterion_name=c["criterion_name"],
                    layer=c["layer"],
                    measured_value=json.loads(c["measured_value"]) if c["measured_value"] else None,
                    threshold_value=json.loads(c["threshold_value"]) if c["threshold_value"] else None,
                    threshold_operator=c["threshold_operator"],
                    passed=None if c["passed"] is None else bool(c["passed"]),
                    margin=c["margin"],
                    normalized_margin=c["normalized_margin"],
                    required=bool(c["required"]),
                    blocked_signal=bool(c["blocked_signal"]),
                    data_quality=c["data_quality"],
                )
                for c in crit_rows
            ]
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


def _blocker_summaries(conn: sqlite3.Connection, ids: list[str], rejected_count: int) -> list[BlockerSummary]:
    if not ids or not rejected_count:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT c.criterion_name,
               COUNT(*) AS blocked_count,
               AVG(CASE WHEN c.normalized_margin IS NULL THEN NULL ELSE 1.0 - MIN(1.0, ABS(c.normalized_margin)) END) AS margin_component,
               GROUP_CONCAT(c.opportunity_id) AS examples
        FROM criterion_results c
        JOIN evaluated_opportunities o ON o.id = c.opportunity_id
        WHERE c.opportunity_id IN ({placeholders})
          AND o.final_decision = 'rejected'
          AND c.required = 1 AND c.passed = 0
        GROUP BY c.criterion_name
        """,
        ids,
    ).fetchall()
    result = []
    for name, blocked_count, margin_component, examples in rows:
        opp_ids = (examples or "").split(",")
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
        frequency = blocked_count / rejected_count
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


def get_summary(start: str, end: str, symbol: Optional[str] = None, db_path: Path = DB_FILE) -> dict[str, Any]:
    init_schema(db_path)
    start_iso = _parse_dt(start).isoformat()
    end_iso = _parse_dt(end).isoformat()
    clauses = ["evaluated_at >= ?", "evaluated_at < ?"]
    params: list[Any] = [start_iso, end_iso]
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol.upper())

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT id, final_decision, near_miss, data_complete, threshold_version FROM evaluated_opportunities WHERE {' AND '.join(clauses)}",
            params,
        ).fetchall()
        ids = [r[0] for r in rows]
        total = len(rows)
        emitted = sum(1 for r in rows if r[1] == "emitted")
        rejected = sum(1 for r in rows if r[1] == "rejected")
        skipped = sum(1 for r in rows if r[1] == "skipped")
        indeterminate = sum(1 for r in rows if r[1] == "indeterminate")
        near_miss_count = sum(1 for r in rows if r[2])
        warnings: list[str] = []
        if total == 0:
            warnings.append("No evaluated opportunities in selected period")
        if any(not r[3] for r in rows):
            warnings.append("Some opportunities have incomplete diagnostics")
        if len({r[4] for r in rows}) > 1:
            warnings.append("Strategy threshold version changed during selected period")

        summary = DiagnosticSummary(
            start=start_iso,
            end=end_iso,
            total_evaluated=total,
            emitted_count=emitted,
            rejected_count=rejected,
            skipped_count=skipped,
            indeterminate_count=indeterminate,
            near_miss_count=near_miss_count,
            criterion_summaries=_criterion_summaries(conn, ids),
            top_blockers=_blocker_summaries(conn, ids, rejected),
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

"""Signal journal — graded signals stored in Postgres.

Source of truth
---------------
Postgres ``journal_entries`` is the authoritative store for the signal journal.
Every application read (``read_journal``, exports, the strategy-metrics journal
aggregations, and the append/grade/management logic) goes through
``_read_entries_oldest_first`` → Postgres, and every mutation (append, grade,
purge) is persisted by ``_write_entries`` as a transactional full replace. The
full entry dict lives in the ``data`` JSONB column; the relational columns
(symbol, grade, lifecycle_role, …) are extracted indexes for ad-hoc SQL.

The append-only ``signal_journal.jsonl`` file is **legacy**: it is refreshed as
a best-effort export/backup snapshot on each write and can be imported into a
fresh database with ``backfill_from_jsonl``, but the application never reads it
for queries.

Schema per entry
----------------
signal_id:        "<symbol>:<direction>:<iso-timestamp>"
symbol:           str
direction:        "BUY" | "SELL"
strategy:         str
confidence:       float  0–1
entry_price:      float
stop_loss:        float
take_profit:      float
lot_size:         float
atr:              float
rr:               float | null
signal_timestamp: ISO str
grade:            "PENDING" | "TP_HIT" | "SL_HIT" | "MANUAL_CLOSE" | "EXPIRED"
grade_timestamp:  ISO str | null
notes:            str
discord_msg_id:   str | null   (links button interaction back to this entry)
stochrsi_k:       float | null
stochrsi_d:       float | null
macd_line:        float | null
macd_signal:      float | null
macd_histogram:   float | null
kc_upper:         float | null
kc_mid:           float | null
kc_lower:         float | null
lr_1h:            float | null
lr_15m:           float | null
lr_5m:            float | null
"""
import csv
import io
import json
import logging
import math
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from tradegumi import config
from tradegumi.persistence import get_db
from tradegumi.strategy_loader import (
    MANAGEMENT_ACCEPTED,
    MANAGEMENT_REJECTED_DISABLED,
    MANAGEMENT_REJECTED_DUPLICATE_EVENT,
    MANAGEMENT_REJECTED_EXTENSION_CAP,
    MANAGEMENT_REJECTED_INSUFFICIENT_PROGRESS,
    MANAGEMENT_REJECTED_MISSING_CONTEXT,
    MANAGEMENT_REJECTED_RISK_INCREASE,
    ManagedTradeContext,
    TradeManagementDecision,
    load_strategy,
)

log = logging.getLogger(__name__)

JOURNAL_FILE = Path(__file__).parent / "data" / "signal_journal.jsonl"

PENDING_GRADE = "PENDING"
TRADE_GRADES = {"TP_HIT", "SL_HIT", "BE", "MISSED_ENTRY", "LATE_SIGNAL", "DUPLICATE", "INVALID", PENDING_GRADE}
VALID_GRADES = {"TP_HIT", "SL_HIT", "BE", "INVALID", "MANUAL_CLOSE", "EXPIRED"}
FILTER_GRADES = VALID_GRADES | {PENDING_GRADE}
STATUS_PENDING = "pending"
STATUS_OPEN_SIMULATED = "open_simulated"
STATUS_CLOSED = "closed"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_INVALIDATED = "invalidated"
STATUS_EXPIRED = "expired"
OUTCOME_NONE = "none"
OUTCOME_TP = "tp"
OUTCOME_SL = "sl"
OUTCOME_EXPIRED = "expired"
OUTCOME_MANUALLY_CLOSED = "manually_closed"
OUTCOME_INVALIDATED_BY_PRIME = "invalidated_by_prime"
OUTCOME_INVALIDATED_BY_SYSTEM = "invalidated_by_system"
OUTCOME_SOURCE_MANUAL = "manual"
OUTCOME_SOURCE_SYSTEM_PRIME_FILTER = "system_prime_filter"
LIFECYCLE_ENTRY = "entry"
LIFECYCLE_MANAGEMENT = "management"
LIFECYCLE_OUTCOME = "outcome"
LIFECYCLE_WARNING = "warning"
LIFECYCLE_LEGACY_SIGNAL = "legacy_signal"
# Continuation-management reason codes (MANAGEMENT_ACCEPTED / MANAGEMENT_REJECTED_*)
# and the TradeManagementDecision / ManagedTradeContext types now live in the
# strategy contract (tradegumi.strategy_loader) and are imported above. Only the
# orchestration-specific code below stays in core.
MANAGEMENT_REJECTED_NO_ACTIVE_TRADE = "no_active_trade"
MANAGED_EXIT_TP_HIT = "tp_hit"
MANAGED_EXIT_SL_LOSS = "sl_hit_with_loss"
MANAGED_EXIT_SL_BE = "sl_hit_at_break_even"
MANAGED_EXIT_SL_PROFIT = "sl_hit_with_profit"
MANAGED_EXIT_MANUAL_PROFIT = "manual_close_profit"
MANAGED_EXIT_MANUAL_LOSS = "manual_close_loss"
MANAGED_RESULT_WIN = "win"
MANAGED_RESULT_LOSS = "loss"
MANAGED_RESULT_BREAKEVEN = "breakeven"
PRIME_CLOSE_INFERRED_TP = "inferred_tp"
PRIME_CLOSE_INFERRED_SL = "inferred_sl"
PRIME_CLOSE_MANUAL_GRADE = "manual_grade"
PRIME_CLOSE_MANUAL_INVALIDATED = "manual_invalidated"
PRIME_CLOSE_RESET = "reset"
PRIME_UNRESOLVED_GRADES = {PENDING_GRADE}
EXPORT_FIELDS = [
    "signal_id",
    "symbol",
    "direction",
    "strategy",
    "signal_type",
    "opportunity_id",
    "timeframe",
    "mode",
    "trend",
    "final_decision",
    "decision_reason",
    "confidence",
    "failed_criteria_count",
    "near_miss",
    "near_miss_reason",
    "first_blocker",
    "all_blockers",
    "blocking_layer",
    "evaluated_at",
    "created_at",
    "entry_price",
    "stop_loss",
    "take_profit",
    "lot_size",
    "atr",
    "rr",
    "signal_timestamp",
    "status",
    "outcome",
    "outcome_source",
    "exit_time",
    "exit_price",
    "outcome_checked_at",
    "observations_to_outcome",
    "bars_to_outcome",
    "max_favorable_excursion",
    "max_adverse_excursion",
    "ambiguous_reason",
    "manually_overridden",
    "manual_override_reason",
    "grade",
    "pending_state",
    "grade_timestamp",
    "setup_group_id",
    "is_duplicate_setup",
    "entry_valid_at_signal",
    "entry_miss_distance",
    "signal_age_bars",
    "late_signal",
    "usable_for_strategy_stats",
    "trade_grade",
    "stats_exclusion_reason",
    "prime_active",
    "prime_suppressed_signal_count",
    "prime_suppressed_last_at",
    "prime_closed_reason",
    "prime_closed_at",
    "prime_close_ambiguous",
    "prime_suppressed_same_direction_count",
    "prime_suppressed_opposite_direction_count",
    "prime_suppressed_signal_ids",
    "prime_suppressed_signal_outcomes",
    "lifecycle_role",
    "trade_id",
    "entry_signal_id",
    "entry_signal_type",
    "management_event_id",
    "source_signal_id",
    "source_signal_type",
    "management_accepted",
    "management_reason",
    "management_rejection_reason",
    "price_at_event",
    "old_stop_loss",
    "new_stop_loss",
    "old_take_profit",
    "new_take_profit",
    "current_stop_loss",
    "current_take_profit",
    "initial_stop_loss",
    "initial_take_profit",
    "risk_at_entry",
    "managed_exit_reason",
    "managed_result_category",
    "captured_r",
    "managed_original_tp_result",
    "managed_result_delta",
    "trade_result",
    "outcome_status",
    "pnl",
    "pnl_percent",
    "profit_loss",
    "profit_loss_percent",
    "notes",
    "discord_msg_id",
    "stochrsi_k",
    "stochrsi_d",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "kc_upper",
    "kc_mid",
    "kc_lower",
    "lr_1h",
    "lr_15m",
    "lr_5m",
    # Volatility shock + filtered LR fields
    "volatility_shock_detected",
    "shock_timeframe",
    "shock_candle_time",
    "shock_true_range",
    "shock_atr",
    "shock_atr_multiple",
    "shock_lookback_bars",
    "shock_direction",
    "shock_suppression_until",
    "shock_suppression_candles_remaining",
    "raw_lr_1h",
    "raw_lr_15m",
    "raw_lr_5m",
    "filtered_lr_1h",
    "filtered_lr_15m",
    "filtered_lr_5m",
    "trend_changed_after_filter",
    "market_validity_state",
    "market_validity_reason",
    "pullback_trigger",
    "pullback_bridge_status",
    "pullback_rejection_reason",
    "shock_blocked_signal",
]
OPTIONAL_EXPORT_FILTERS = {
    "symbol": ("symbol",),
    "status": ("status", "grade"),
    "final_decision": ("final_decision",),
    "strategy": ("strategy",),
    "mode": ("mode",),
}

# Protects all reads and writes to JOURNAL_FILE across threads
# (trading loop thread appends; Discord bot thread grades).
_lock = threading.Lock()


@dataclass(frozen=True)
class SignalJournalExportSelection:
    """Operator-selected scope used to filter Signal Journal CSV exports.

    Date/time boundaries are inclusive and apply to `evaluated_at` when present,
    then `created_at`, then legacy `signal_timestamp` without mutating records.
    Optional string filters are reserved for visible dashboard filters and are
    ignored when unset.
    """

    grade: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    symbol: Optional[str] = None
    status: Optional[str] = None
    final_decision: Optional[str] = None
    strategy: Optional[str] = None
    mode: Optional[str] = None
    graded_state: Optional[str] = None


@dataclass(frozen=True)
class SignalJournalExportResult:
    """CSV export payload plus route metadata for browser downloads."""

    csv_text: str
    filename: str
    record_count: int
    content_type: str = "text/csv; charset=utf-8"

    @property
    def content_disposition(self) -> str:
        """Return the attachment header value for the generated CSV file."""
        return f'attachment; filename="{self.filename}"'


@dataclass(frozen=True)
class TradeEntryState:
    """Managed state carried by a pullback-originated journal entry."""

    trade_id: str
    entry_signal_id: str
    entry_signal_type: str
    current_stop_loss: float
    current_take_profit: float
    risk_at_entry: float


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


# ── Journal storage (Postgres-authoritative; JSONL is legacy backup/export) ──

_JOURNAL_COLUMNS = (
    "signal_id", "signal_timestamp", "symbol", "direction", "strategy", "signal_type",
    "lifecycle_role", "grade", "grade_timestamp", "entry_price", "stop_loss", "take_profit",
    "lot_size", "atr", "rr", "confidence", "notes", "discord_msg_id", "data", "created_at",
)
_JOURNAL_INSERT_SQL = (
    "INSERT INTO journal_entries (" + ", ".join(_JOURNAL_COLUMNS) + ") VALUES ("
    + ", ".join("?" for _ in _JOURNAL_COLUMNS) + ")"
)


def _read_entries_oldest_first() -> list[dict[str, Any]]:
    """Read journal entries (oldest first) from the authoritative Postgres store.

    The full entry dict is stored in the ``data`` JSONB column; relational
    columns are extracted indexes only. Rows are ordered by insertion id, which
    preserves append order.
    """
    try:
        rows = get_db().fetchall("SELECT data FROM journal_entries ORDER BY id")
    except Exception as exc:
        log.warning("Failed to read journal entries from Postgres: %s", exc)
        return []
    entries: list[dict[str, Any]] = []
    for row in rows:
        data = row.get("data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (TypeError, ValueError):
                continue
        if isinstance(data, dict):
            entries.append(data)
    return entries


def _nullable_ts(value: Any) -> Any:
    """Coerce empty/blank timestamps to NULL so TIMESTAMPTZ casts don't fail."""
    return value or None


def _journal_row(entry: dict[str, Any], json_adapter) -> tuple:
    """Build the column tuple for one journal entry (data carries the full dict)."""
    return (
        entry.get("signal_id"),
        _nullable_ts(entry.get("signal_timestamp")),
        entry.get("symbol"),
        entry.get("direction"),
        entry.get("strategy"),
        entry.get("signal_type"),
        entry.get("lifecycle_role"),
        entry.get("grade"),
        _nullable_ts(entry.get("grade_timestamp")),
        entry.get("entry_price"),
        entry.get("stop_loss"),
        entry.get("take_profit"),
        entry.get("lot_size"),
        entry.get("atr"),
        entry.get("rr"),
        entry.get("confidence"),
        entry.get("notes"),
        entry.get("discord_msg_id"),
        json_adapter(entry),
        _nullable_ts(entry.get("created_at") or entry.get("signal_timestamp")),
    )


def _write_entries(entries: list[dict[str, Any]]) -> None:
    """Replace journal contents in Postgres (authoritative) and refresh the JSONL backup.

    The journal logic mutates the full entry list in memory (a new signal can
    also update prior entries' prime/management state), so persistence is a
    transactional full replace, mirroring the previous JSONL rewrite semantics.
    """
    from psycopg.types.json import Json  # Postgres-only; imported lazily

    rows = [_journal_row(entry, Json) for entry in entries]
    db = get_db()
    with db.transaction():
        db.execute("DELETE FROM journal_entries")
        if rows:
            db.executemany(_JOURNAL_INSERT_SQL, rows)
    _write_jsonl_backup(entries)


def _write_jsonl_backup(entries: list[dict[str, Any]]) -> None:
    """Best-effort JSONL snapshot for export/audit (not read by the application)."""
    try:
        JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = JOURNAL_FILE.with_suffix(".jsonl.tmp")
        body = "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries)
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(JOURNAL_FILE)
    except Exception as exc:
        log.warning("Failed to write JSONL journal backup: %s", exc)


def _read_jsonl_file(path: Path) -> list[dict[str, Any]]:
    """Parse a legacy JSONL journal file into entry dicts (skips malformed lines)."""
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            log.warning("Skipping malformed journal line: %r", stripped[:80])
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def backfill_from_jsonl(path: Optional[Path] = None) -> int:
    """One-time import of a legacy JSONL journal into Postgres. Returns the count."""
    entries = _read_jsonl_file(path or JOURNAL_FILE)
    if entries:
        _write_entries(entries)
    return len(entries)


def _normalize_filter_grade(grade: Optional[str]) -> Optional[str]:
    """Normalize a grade filter, returning None for an all-record scope."""
    if grade is None or str(grade).strip().upper() in {"", "ALL"}:
        return None
    value = str(grade).strip().upper()
    if value not in FILTER_GRADES:
        raise ValueError(f"Invalid grade filter: {grade}")
    return value


def _parse_export_datetime(value: Optional[str], field_name: str) -> Optional[datetime]:
    """Parse an export date/time boundary into a comparable UTC-naive value."""
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name} timestamp: {value}") from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _entry_analysis_datetime(entry: dict[str, Any]) -> Optional[datetime]:
    """Return the timestamp used to decide whether a record is in export range."""
    for key in ("evaluated_at", "created_at", "signal_timestamp"):
        value = entry.get(key)
        if value:
            try:
                return _parse_export_datetime(str(value), key)
            except ValueError:
                log.warning("Skipping malformed journal timestamp %s=%r", key, value)
                return None
    return None


def _normalize_csv_value(value: Any) -> Any:
    """Convert nested CSV values into deterministic scalar cells."""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if value is None:
        return ""
    return value


def _default_status_for_entry(entry: dict[str, Any]) -> str:
    """Infer a safe outcome status for legacy journal entries."""
    grade = str(entry.get("grade") or PENDING_GRADE).upper()
    trade_grade = str(entry.get("trade_grade") or grade).upper()
    if grade == PENDING_GRADE and trade_grade == PENDING_GRADE:
        return STATUS_OPEN_SIMULATED
    if grade == "EXPIRED":
        return STATUS_EXPIRED
    if trade_grade == "INVALID":
        return STATUS_INVALIDATED
    return STATUS_CLOSED


def _default_outcome_for_entry(entry: dict[str, Any]) -> str:
    """Infer a safe outcome value for legacy grade-only entries."""
    grade = str(entry.get("grade") or PENDING_GRADE).upper()
    trade_grade = str(entry.get("trade_grade") or grade).upper()
    if grade == "TP_HIT" or trade_grade == "TP_HIT":
        return OUTCOME_TP
    if grade == "SL_HIT" or trade_grade == "SL_HIT":
        return OUTCOME_SL
    if grade == "EXPIRED":
        return OUTCOME_EXPIRED
    if grade == "MANUAL_CLOSE":
        return OUTCOME_MANUALLY_CLOSED
    if trade_grade == "INVALID":
        return OUTCOME_INVALIDATED_BY_SYSTEM
    return OUTCOME_NONE


def _apply_outcome_defaults(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a journal entry with additive outcome defaults."""
    normalized = dict(entry)
    normalized.setdefault("status", _default_status_for_entry(normalized))
    normalized.setdefault("outcome", _default_outcome_for_entry(normalized))
    normalized.setdefault("outcome_source", OUTCOME_SOURCE_MANUAL if normalized.get("grade") not in (None, PENDING_GRADE) else None)
    normalized.setdefault("exit_time", normalized.get("grade_timestamp"))
    normalized.setdefault("exit_price", None)
    normalized.setdefault("outcome_checked_at", normalized.get("grade_timestamp"))
    normalized.setdefault("observations_to_outcome", None)
    normalized.setdefault("bars_to_outcome", None)
    normalized.setdefault("max_favorable_excursion", None)
    normalized.setdefault("max_adverse_excursion", None)
    normalized.setdefault("ambiguous_reason", None)
    normalized.setdefault("manually_overridden", False)
    normalized.setdefault("manual_override_reason", None)
    normalized.setdefault("lifecycle_role", LIFECYCLE_LEGACY_SIGNAL)
    for field in (
        "trade_id",
        "entry_signal_id",
        "entry_signal_type",
        "management_event_id",
        "source_signal_id",
        "source_signal_type",
        "management_accepted",
        "management_reason",
        "management_rejection_reason",
        "price_at_event",
        "old_stop_loss",
        "new_stop_loss",
        "old_take_profit",
        "new_take_profit",
        "current_stop_loss",
        "current_take_profit",
        "initial_stop_loss",
        "initial_take_profit",
        "risk_at_entry",
        "managed_exit_reason",
        "managed_result_category",
        "captured_r",
        "managed_original_tp_result",
        "managed_result_delta",
    ):
        normalized.setdefault(field, None)
    return normalized


def _matches_optional_filter(entry: dict[str, Any], name: str, value: Optional[str]) -> bool:
    """Return whether one optional export filter matches the journal entry."""
    if value is None or not str(value).strip():
        return True
    expected = str(value).strip().lower()
    if name == "graded_state":
        grade = str(entry.get("grade") or PENDING_GRADE).upper()
        if expected == "pending":
            return grade == PENDING_GRADE
        if expected == "graded":
            return grade != PENDING_GRADE
        raise ValueError(f"Invalid graded_state filter: {value}")
    fields = OPTIONAL_EXPORT_FILTERS[name]
    return any(str(entry.get(field) or "").strip().lower() == expected for field in fields)


def _validate_export_selection(selection: SignalJournalExportSelection) -> None:
    """Validate export filters even when the journal has no matching entries."""
    _normalize_filter_grade(selection.grade)
    start = _parse_export_datetime(selection.start, "start")
    end = _parse_export_datetime(selection.end, "end")
    if start and end and start > end:
        raise ValueError("start must be before end")
    if selection.graded_state and str(selection.graded_state).strip().lower() not in {"pending", "graded"}:
        raise ValueError(f"Invalid graded_state filter: {selection.graded_state}")


def _entry_matches_selection(entry: dict[str, Any], selection: SignalJournalExportSelection) -> bool:
    """Return whether an entry belongs in the selected export scope."""
    if not _entry_matches_grade(entry, selection.grade):
        return False
    for name in OPTIONAL_EXPORT_FILTERS:
        if not _matches_optional_filter(entry, name, getattr(selection, name)):
            return False
    if not _matches_optional_filter(entry, "graded_state", selection.graded_state):
        return False

    start = _parse_export_datetime(selection.start, "start")
    end = _parse_export_datetime(selection.end, "end")
    if start and end and start > end:
        raise ValueError("start must be before end")
    if not start and not end:
        return True

    timestamp = _entry_analysis_datetime(entry)
    if timestamp is None:
        return False
    if start and timestamp < start:
        return False
    if end and timestamp > end:
        return False
    return True


def _export_filename(selection: SignalJournalExportSelection) -> str:
    """Build a deterministic Signal Journal export filename for the selection."""
    start = _parse_export_datetime(selection.start, "start")
    end = _parse_export_datetime(selection.end, "end")
    if start and end:
        return f"signal-journal-{start.date().isoformat()}-to-{end.date().isoformat()}.csv"
    if start or end:
        return "signal-journal-selected-range.csv"
    grade = _normalize_filter_grade(selection.grade)
    suffix = (grade or "all").lower().replace("_", "-")
    today = datetime.now(timezone.utc).date().isoformat()
    return f"signal-journal-{suffix}-{today}.csv"


def _entry_matches_grade(entry: dict[str, Any], grade: Optional[str]) -> bool:
    """Return whether a journal entry is in the requested grade scope."""
    normalized = _normalize_filter_grade(grade)
    return normalized is None or str(entry.get("trade_grade") or entry.get("grade") or PENDING_GRADE).upper() == normalized


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _parse_journal_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _normal_key(value: Any, default: str = "unknown") -> str:
    raw = str(value or default).strip()
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-") or default


def _setup_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("symbol") or "").upper(),
        str(entry.get("direction") or "").upper(),
        str(entry.get("strategy") or "CTI-v1"),
    )


def _setup_group_id(symbol: Any, direction: Any, strategy: Any, timestamp: datetime) -> str:
    stamp = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parts = (_normal_key(symbol), _normal_key(direction), _normal_key(strategy))
    return ":".join((*parts, stamp))


def _active_setup_group(
    existing_entries: list[dict[str, Any]],
    new_entry: dict[str, Any],
    signal_ts: datetime,
    window_minutes: int,
) -> Optional[str]:
    window = timedelta(minutes=max(0, window_minutes))
    for entry in reversed(existing_entries):
        if _setup_key(entry) != _setup_key(new_entry):
            continue
        existing_ts = _parse_journal_datetime(entry.get("signal_timestamp"))
        if existing_ts is None:
            continue
        delta = signal_ts - existing_ts
        if timedelta(0) <= delta < window:
            return str(entry.get("setup_group_id") or _setup_group_id(entry.get("symbol"), entry.get("direction"), entry.get("strategy"), existing_ts))
    return None


def _signal_attr(signal: Any, names: tuple[str, ...], fallback: Any = None) -> Any:
    for name in names:
        value = getattr(signal, name, None)
        if value is not None:
            return value
    return fallback


def _entry_miss_distance(signal_price: Optional[float], suggested_entry: Optional[float], atr: Optional[float]) -> dict[str, Any]:
    if signal_price is None or suggested_entry is None:
        return {"absolute": None, "atr_normalized": None}
    absolute = abs(signal_price - suggested_entry)
    normalized = absolute / atr if atr and atr > 0 else None
    return {"absolute": absolute, "atr_normalized": normalized}


def _calculate_signal_age_bars(signal_ts: datetime, first_true_at: Any) -> int:
    started = _parse_journal_datetime(first_true_at)
    if started is None:
        return 0
    return max(0, int((signal_ts - started).total_seconds() // 300))


def _grade_for_completion(grade: str) -> str:
    normalized = str(grade or PENDING_GRADE).upper()
    if normalized in {"TP_HIT", "SL_HIT", "BE", "INVALID"}:
        return normalized
    if normalized == "MANUAL_CLOSE":
        return "BE"
    if normalized == "EXPIRED":
        return "MISSED_ENTRY"
    return PENDING_GRADE


def _strategy_usable_for_entry(entry: dict[str, Any]) -> bool:
    return (
        not bool(entry.get("is_duplicate_setup"))
        and entry.get("entry_valid_at_signal") is True
        and not bool(entry.get("late_signal"))
        and int(entry.get("signal_age_bars") or 0) <= int(config.SIGNAL_STALE_BARS)
    )


def _setup_outcome_fields(signal: Any, base_entry: dict[str, Any], existing_entries: list[dict[str, Any]], ts: str) -> dict[str, Any]:
    signal_ts = _parse_journal_datetime(ts) or datetime.now(timezone.utc)
    group_id = _active_setup_group(existing_entries, base_entry, signal_ts, config.SIGNAL_SETUP_GROUP_WINDOW_MINUTES)
    is_duplicate = group_id is not None
    if group_id is None:
        group_id = _setup_group_id(base_entry.get("symbol"), base_entry.get("direction"), base_entry.get("strategy"), signal_ts)

    suggested_entry = _coerce_float(_signal_attr(signal, ("suggested_entry", "recommended_entry", "entry_price"), base_entry.get("entry_price")))
    signal_price = _coerce_float(_signal_attr(signal, ("signal_price", "current_price", "market_price"), suggested_entry))
    atr = _coerce_float(base_entry.get("atr"))
    distance = _entry_miss_distance(signal_price, suggested_entry, atr)
    explicit_tolerance = _coerce_float(_signal_attr(signal, ("entry_tolerance", "valid_entry_tolerance"), None))
    tolerance = explicit_tolerance if explicit_tolerance is not None else ((atr or 0.0) * float(config.SIGNAL_ENTRY_TOLERANCE_ATR))
    signal_age_bars = _calculate_signal_age_bars(signal_ts, _signal_attr(signal, ("setup_condition_first_true_at", "condition_first_true_at"), None))

    if suggested_entry is None or signal_price is None:
        entry_valid: Optional[bool] = None
    else:
        entry_valid = bool(distance["absolute"] is not None and distance["absolute"] <= tolerance)
    late_signal = entry_valid is False
    stale_signal = signal_age_bars > int(config.SIGNAL_STALE_BARS)

    usable = False
    exclusion_reason = None
    trade_grade = PENDING_GRADE
    if is_duplicate:
        exclusion_reason = "duplicate_setup"
        trade_grade = "DUPLICATE"
    elif entry_valid is None:
        exclusion_reason = "missing_entry_context"
        trade_grade = "INVALID"
    elif late_signal:
        exclusion_reason = "late_signal"
        trade_grade = "LATE_SIGNAL"
    elif stale_signal:
        exclusion_reason = "stale_signal"
        trade_grade = "INVALID"
    else:
        usable = True

    return {
        "setup_group_id": group_id,
        "is_duplicate_setup": is_duplicate,
        "entry_valid_at_signal": entry_valid,
        "entry_miss_distance": distance,
        "signal_age_bars": signal_age_bars,
        "late_signal": late_signal,
        "usable_for_strategy_stats": usable,
        "trade_grade": trade_grade,
        "stats_exclusion_reason": exclusion_reason,
    }


def _make_actionable_after_prime_close(entry: dict[str, Any], signal_ts: datetime) -> None:
    """Ensure an inferred prime replacement is treated as a fresh actionable setup."""
    entry["setup_group_id"] = _setup_group_id(entry.get("symbol"), entry.get("direction"), entry.get("strategy"), signal_ts)
    entry["is_duplicate_setup"] = False
    if entry.get("entry_valid_at_signal") is True and not bool(entry.get("late_signal")):
        entry["usable_for_strategy_stats"] = True
        entry["trade_grade"] = PENDING_GRADE
        entry.pop("stats_exclusion_reason", None)


def _prime_initial_fields() -> dict[str, Any]:
    """Return initialized prime-state fields for a new actionable journal entry."""
    return {
        "prime_active": True,
        "prime_suppressed_signal_count": 0,
        "prime_suppressed_last_at": None,
        "prime_closed_reason": None,
        "prime_closed_at": None,
        "prime_close_ambiguous": False,
        "prime_suppressed_same_direction_count": 0,
        "prime_suppressed_opposite_direction_count": 0,
        "prime_suppressed_signal_ids": [],
    }


def _direction_key(value: Any) -> str:
    """Normalize signal direction labels used by alerts and strategy internals."""
    normalized = str(value or "").strip().upper()
    if normalized in {"BUY", "LONG", "UPTREND", "UP"}:
        return "BUY"
    if normalized in {"SELL", "SHORT", "DOWNTREND", "DOWN"}:
        return "SELL"
    return normalized


def _is_pullback_identity(strategy: Any, signal_type: Any) -> bool:
    """Return whether a signal identity can open a managed trade."""
    strategy_name = str(strategy or "").lower()
    signal_type_name = str(signal_type or "").lower()
    return signal_type_name in {"pullback", "high_value_pullback"} or "pullback" in strategy_name


def _is_continuation_identity(signal_type: Any) -> bool:
    """Return whether a signal type should become management evidence."""
    return str(signal_type or "").strip().lower() == "continuation"


def active_trade_for_signal(signal, entries: Optional[list[dict[str, Any]]] = None) -> Optional[dict[str, Any]]:
    """Return the newest active managed trade matching a signal's symbol/direction."""
    if entries is None:
        entries = _read_entries_oldest_first()
    return _active_managed_trade_for_direction(entries, signal.symbol, signal.direction)


def is_orphan_continuation(signal, entries: Optional[list[dict[str, Any]]] = None) -> bool:
    """Return True when a signal is a continuation with no active trade to manage.

    These signals are internal diagnostics only and must not be surfaced as
    user-facing alerts, dashboard cards, or journal entries.
    """
    if not _is_continuation_identity(getattr(signal, "signal_type", None)):
        return False
    return active_trade_for_signal(signal, entries) is None


def _entry_trade_id(entry: dict[str, Any]) -> str:
    """Return a stable lifecycle identifier for a journal entry."""
    existing = str(entry.get("trade_id") or "").strip()
    return existing or str(entry.get("signal_id") or "")


def _risk_at_entry(entry_price: Any, stop_loss: Any) -> Optional[float]:
    """Return the absolute initial risk distance for an entry."""
    entry = _coerce_float(entry_price)
    stop = _coerce_float(stop_loss)
    if entry is None or stop is None:
        return None
    risk = abs(entry - stop)
    return risk if risk > 0 else None


def _managed_entry_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Return initialized managed-trade fields for a pullback entry."""
    return {
        "lifecycle_role": LIFECYCLE_ENTRY,
        "trade_id": _entry_trade_id(entry),
        "entry_signal_id": entry.get("signal_id"),
        "entry_signal_type": entry.get("signal_type"),
        "initial_stop_loss": entry.get("stop_loss"),
        "initial_take_profit": entry.get("take_profit"),
        "current_stop_loss": entry.get("stop_loss"),
        "current_take_profit": entry.get("take_profit"),
        "risk_at_entry": _risk_at_entry(entry.get("entry_price"), entry.get("stop_loss")),
        "management_events": [],
        "tp_extension_count": 0,
        "sl_tighten_count": 0,
        "break_even_move_count": 0,
        "opposite_direction_continuation_warning_count": 0,
    }


def _active_managed_trade_for_direction(
    entries: list[dict[str, Any]],
    symbol: Any,
    direction: Any,
) -> Optional[dict[str, Any]]:
    """Return the newest active pullback-originated trade for symbol and direction."""
    symbol_key = _normal_key(symbol)
    direction_key = _direction_key(direction)
    for entry in reversed(entries):
        if _normal_key(entry.get("symbol")) != symbol_key:
            continue
        if _direction_key(entry.get("direction")) != direction_key:
            continue
        if entry.get("lifecycle_role") != LIFECYCLE_ENTRY:
            continue
        if str(entry.get("status") or "").lower() in {STATUS_CLOSED, STATUS_INVALIDATED, STATUS_EXPIRED}:
            continue
        if entry.get("prime_active") is False:
            continue
        return entry
    return None


def _active_managed_trade_for_symbol(entries: list[dict[str, Any]], symbol: Any) -> Optional[dict[str, Any]]:
    """Return the newest active pullback-originated trade for a symbol."""
    symbol_key = _normal_key(symbol)
    for entry in reversed(entries):
        if _normal_key(entry.get("symbol")) != symbol_key:
            continue
        if entry.get("lifecycle_role") != LIFECYCLE_ENTRY:
            continue
        if str(entry.get("status") or "").lower() in {STATUS_CLOSED, STATUS_INVALIDATED, STATUS_EXPIRED}:
            continue
        if entry.get("prime_active") is False:
            continue
        return entry
    return None


def _price_at_management_event(signal: Any, entry: dict[str, Any]) -> Optional[float]:
    """Choose the price used for continuation management progress calculations."""
    return _coerce_float(_signal_attr(signal, ("signal_price", "current_price", "market_price", "entry_price"), entry.get("entry_price")))


def _management_event_seen(trade: dict[str, Any], source_signal_id: str) -> bool:
    """Return whether a continuation signal already affected this managed trade."""
    events = trade.get("management_events")
    if not isinstance(events, list):
        return False
    return any(isinstance(event, dict) and event.get("source_signal_id") == source_signal_id for event in events)


_active_strategy = None


def _get_active_strategy():
    """Return (and cache) the active strategy plugin for trade management.

    The runtime uses a single configured strategy; load it once and reuse it so
    every continuation event is managed by the same plugin instance.
    """
    global _active_strategy
    if _active_strategy is None:
        _active_strategy = load_strategy()
    return _active_strategy


def _evaluate_management_event(trade: dict[str, Any], signal: Any, source_signal_id: str) -> TradeManagementDecision:
    """Delegate continuation management of an active trade to the active strategy.

    Core owns detection and persistence; the *decision* (SL/TP changes) belongs to
    the strategy. We build a journal-free ``ManagedTradeContext`` from the trade
    row + signal and hand it to ``strategy.manage_open_trade``.
    """
    entry_price = _coerce_float(trade.get("entry_price"))
    ctx = ManagedTradeContext(
        direction=_direction_key(trade.get("direction")),
        entry_price=entry_price,
        current_stop_loss=_coerce_float(trade.get("current_stop_loss", trade.get("stop_loss"))),
        current_take_profit=_coerce_float(trade.get("current_take_profit", trade.get("take_profit"))),
        risk_at_entry=_coerce_float(trade.get("risk_at_entry")) or _risk_at_entry(entry_price, trade.get("initial_stop_loss", trade.get("stop_loss"))),
        price_at_event=_price_at_management_event(signal, trade),
        tp_extension_count=int(trade.get("tp_extension_count") or 0),
        already_seen=_management_event_seen(trade, source_signal_id),
    )
    return _get_active_strategy().manage_open_trade(ctx)


def _append_management_evidence(
    entries: list[dict[str, Any]],
    trade: Optional[dict[str, Any]],
    signal: Any,
    source_signal_id: str,
    ts: str,
    decision: TradeManagementDecision,
    role: str = LIFECYCLE_MANAGEMENT,
) -> None:
    """Append a non-entry management evidence row and update linked trade state."""
    management_event_id = f"mgmt:{source_signal_id}"
    if trade is not None and decision.accepted:
        trade["current_stop_loss"] = decision.new_stop_loss
        trade["current_take_profit"] = decision.new_take_profit
        if decision.sl_tightened:
            trade["sl_tighten_count"] = int(trade.get("sl_tighten_count") or 0) + 1
        if decision.break_even_moved:
            trade["break_even_move_count"] = int(trade.get("break_even_move_count") or 0) + 1
        if decision.tp_extended:
            trade["tp_extension_count"] = int(trade.get("tp_extension_count") or 0) + 1
        events = trade.get("management_events")
        if not isinstance(events, list):
            events = []
        events.append(
            {
                "management_event_id": management_event_id,
                "source_signal_id": source_signal_id,
                "source_signal_type": "continuation",
                "event_time": ts,
                "accepted": decision.accepted,
                "reason": decision.reason,
                "rejection_reason": decision.rejection_reason,
                "old_stop_loss": decision.old_stop_loss,
                "new_stop_loss": decision.new_stop_loss,
                "old_take_profit": decision.old_take_profit,
                "new_take_profit": decision.new_take_profit,
                "price_at_event": decision.price_at_event,
            }
        )
        trade["management_events"] = events[-50:]
    if trade is not None and role == LIFECYCLE_WARNING:
        trade["opposite_direction_continuation_warning_count"] = int(trade.get("opposite_direction_continuation_warning_count") or 0) + 1

    evidence = {
        "signal_id": source_signal_id,
        "symbol": signal.symbol,
        "direction": signal.direction,
        "strategy": getattr(signal, "strategy", "CTI-v1"),
        "signal_type": getattr(signal, "signal_type", "continuation"),
        "confidence": round(float(getattr(signal, "confidence", 0.0) or 0.0), 3),
        "entry_price": getattr(signal, "entry_price", None),
        "stop_loss": getattr(signal, "stop_loss", None),
        "take_profit": getattr(signal, "take_profit", None),
        "lot_size": getattr(signal, "lot_size", None),
        "atr": getattr(signal, "atr", None),
        "signal_timestamp": ts,
        "created_at": ts,
        "grade": PENDING_GRADE,
        "trade_grade": "INVALID",
        "status": STATUS_INVALIDATED,
        "outcome": OUTCOME_NONE,
        "outcome_source": None,
        "usable_for_strategy_stats": False,
        "stats_exclusion_reason": "continuation_management_event",
        "lifecycle_role": role,
        "trade_id": trade.get("trade_id") if trade else None,
        "entry_signal_id": trade.get("entry_signal_id") if trade else None,
        "entry_signal_type": trade.get("entry_signal_type") if trade else None,
        "management_event_id": management_event_id,
        "source_signal_id": source_signal_id,
        "source_signal_type": "continuation",
        "management_accepted": decision.accepted,
        "management_reason": decision.reason,
        "management_rejection_reason": decision.rejection_reason,
        "price_at_event": decision.price_at_event,
        "old_stop_loss": decision.old_stop_loss,
        "new_stop_loss": decision.new_stop_loss,
        "old_take_profit": decision.old_take_profit,
        "new_take_profit": decision.new_take_profit,
        "current_stop_loss": decision.new_stop_loss,
        "current_take_profit": decision.new_take_profit,
        "prime_active": False,
        "prime_suppressed_signal_count": 0,
    }
    entries.append(evidence)


def classify_managed_exit(entry: dict[str, Any], exit_price: Any, exit_kind: str) -> dict[str, Any]:
    """Classify a managed trade exit relative to entry direction and 1R risk."""
    direction = _direction_key(entry.get("direction"))
    entry_price = _coerce_float(entry.get("entry_price"))
    close_price = _coerce_float(exit_price)
    risk = _coerce_float(entry.get("risk_at_entry")) or _risk_at_entry(entry_price, entry.get("initial_stop_loss", entry.get("stop_loss")))
    if direction not in {"BUY", "SELL"} or entry_price is None or close_price is None:
        return {"managed_exit_reason": None, "managed_result_category": None, "captured_r": None}
    movement = close_price - entry_price if direction == "BUY" else entry_price - close_price
    captured_r = None if risk in (None, 0) else movement / risk
    if exit_kind == OUTCOME_TP:
        reason = MANAGED_EXIT_TP_HIT
        category = MANAGED_RESULT_WIN
    elif exit_kind == OUTCOME_SL:
        if movement > 0:
            reason = MANAGED_EXIT_SL_PROFIT
            category = MANAGED_RESULT_WIN
        elif movement == 0:
            reason = MANAGED_EXIT_SL_BE
            category = MANAGED_RESULT_BREAKEVEN
        else:
            reason = MANAGED_EXIT_SL_LOSS
            category = MANAGED_RESULT_LOSS
    elif movement >= 0:
        reason = MANAGED_EXIT_MANUAL_PROFIT
        category = MANAGED_RESULT_WIN if movement > 0 else MANAGED_RESULT_BREAKEVEN
    else:
        reason = MANAGED_EXIT_MANUAL_LOSS
        category = MANAGED_RESULT_LOSS
    return {
        "managed_exit_reason": reason,
        "managed_result_category": category,
        "captured_r": captured_r,
    }


def _is_unresolved_prime(entry: dict[str, Any]) -> bool:
    """Return whether a persisted journal entry can suppress same-symbol signals."""
    if entry.get("prime_active") is not True:
        return False
    status = str(entry.get("status") or "").lower()
    outcome = str(entry.get("outcome") or "").lower()
    if status == STATUS_CLOSED and outcome in {OUTCOME_TP, OUTCOME_SL}:
        return False
    trade_grade = str(entry.get("trade_grade") or entry.get("grade") or PENDING_GRADE).upper()
    if trade_grade not in PRIME_UNRESOLVED_GRADES:
        return False
    if entry.get("usable_for_strategy_stats") is False:
        return False
    return True


def _active_prime_for_symbol(entries: list[dict[str, Any]], symbol: Any) -> Optional[dict[str, Any]]:
    """Return the newest active unresolved prime for the supplied symbol."""
    target = _normal_key(symbol)
    for entry in reversed(entries):
        if _normal_key(entry.get("symbol")) == target and _is_unresolved_prime(entry):
            return entry
    return None


def _candle_time(candle: Any) -> Optional[datetime]:
    """Extract a timezone-aware candle timestamp from supported candle shapes."""
    if isinstance(candle, dict):
        raw = candle.get("time", candle.get("t"))
    else:
        raw = getattr(candle, "time", None)
        if raw is None:
            raw = getattr(candle, "t", None)
    return _parse_journal_datetime(raw)


def _candle_high_low(candle: Any) -> tuple[Optional[float], Optional[float]]:
    """Extract high and low values from an execution candle or dict-like candle."""
    if isinstance(candle, dict):
        high = candle.get("h", candle.get("high"))
        low = candle.get("l", candle.get("low"))
    else:
        high = getattr(candle, "h", getattr(candle, "high", None))
        low = getattr(candle, "l", getattr(candle, "low", None))
    return _coerce_float(high), _coerce_float(low)


def _signal_prime_candles(signal: Any) -> list[Any]:
    """Return candidate candles carried by a signal for prime outcome inference."""
    value = _signal_attr(signal, ("prime_outcome_candles", "recent_candles", "candles"), None)
    if value is None:
        return []
    return list(value)


def _candles_between(candles: list[Any], start: Optional[datetime], end: Optional[datetime]) -> list[Any]:
    """Filter candles to the inclusive prime-to-follow-on evaluation window."""
    if start is None or end is None:
        return []
    selected: list[Any] = []
    for candle in candles:
        candle_ts = _candle_time(candle)
        if candle_ts is None:
            continue
        if start <= candle_ts <= end:
            selected.append(candle)
    return selected


def _infer_prime_close(prime: dict[str, Any], candles: list[Any], new_signal_ts: datetime) -> Optional[dict[str, Any]]:
    """Infer whether a prime signal reached target or stop before a later signal."""
    direction = _direction_key(prime.get("direction"))
    stop_loss = _coerce_float(prime.get("stop_loss"))
    take_profit = _coerce_float(prime.get("take_profit"))
    prime_ts = _parse_journal_datetime(prime.get("signal_timestamp"))
    if direction not in {"BUY", "SELL"} or stop_loss is None or take_profit is None or prime_ts is None:
        return None

    for candle in _candles_between(candles, prime_ts, new_signal_ts):
        high, low = _candle_high_low(candle)
        if high is None or low is None:
            continue
        if direction == "BUY":
            hit_tp = high >= take_profit
            hit_sl = low <= stop_loss
        else:
            hit_tp = low <= take_profit
            hit_sl = high >= stop_loss
        if hit_tp and hit_sl:
            return {"reason": PRIME_CLOSE_INFERRED_SL, "ambiguous": True}
        if hit_sl:
            return {"reason": PRIME_CLOSE_INFERRED_SL, "ambiguous": False}
        if hit_tp:
            return {"reason": PRIME_CLOSE_INFERRED_TP, "ambiguous": False}
    return None


def _deactivate_prime(entry: dict[str, Any], reason: str, closed_at: Optional[str] = None, ambiguous: bool = False) -> None:
    """Mark a prime entry inactive while preserving its suppression evidence."""
    if entry.get("prime_active") is True:
        entry["prime_active"] = False
        entry["prime_closed_reason"] = reason
        entry["prime_closed_at"] = closed_at or _now_iso()
        entry["prime_close_ambiguous"] = bool(ambiguous)


def _record_prime_suppression(prime: dict[str, Any], new_entry: dict[str, Any], suppressed_at: str) -> None:
    """Update suppression counters on an unresolved active prime."""
    count = int(prime.get("prime_suppressed_signal_count") or 0) + 1
    prime["prime_suppressed_signal_count"] = count
    prime["prime_suppressed_last_at"] = suppressed_at
    if _direction_key(prime.get("direction")) == _direction_key(new_entry.get("direction")):
        prime["prime_suppressed_same_direction_count"] = int(prime.get("prime_suppressed_same_direction_count") or 0) + 1
    else:
        prime["prime_suppressed_opposite_direction_count"] = int(prime.get("prime_suppressed_opposite_direction_count") or 0) + 1
    suppressed_ids = prime.get("prime_suppressed_signal_ids")
    if not isinstance(suppressed_ids, list):
        suppressed_ids = []
    suppressed_ids.append(str(new_entry.get("signal_id")))
    prime["prime_suppressed_signal_ids"] = suppressed_ids[-25:]
    suppressed_outcomes = prime.get("prime_suppressed_signal_outcomes")
    if not isinstance(suppressed_outcomes, list):
        suppressed_outcomes = []
    suppressed_outcomes.append(
        {
            "signal_id": str(new_entry.get("signal_id")),
            "symbol": new_entry.get("symbol"),
            "direction": _direction_key(new_entry.get("direction")),
            "strategy": new_entry.get("strategy"),
            "signal_type": new_entry.get("signal_type"),
            "pullback_trigger": new_entry.get("pullback_trigger"),
            "pullback_bridge_status": new_entry.get("pullback_bridge_status"),
            "pullback_rejection_reason": new_entry.get("pullback_rejection_reason"),
            "status": STATUS_INVALIDATED,
            "outcome": OUTCOME_INVALIDATED_BY_PRIME,
            "outcome_source": OUTCOME_SOURCE_SYSTEM_PRIME_FILTER,
            "suppressed_at": suppressed_at,
        }
    )
    prime["prime_suppressed_signal_outcomes"] = suppressed_outcomes[-25:]


def append_signal(signal, rr: Optional[float] = None, discord_msg_id: Optional[str] = None, notes: str = "") -> Optional[str]:
    """Append a new PENDING entry to the journal. Returns the signal_id.

    Continuation signals without a matching active trade are not user-facing
    signals; they are suppressed and ``None`` is returned so callers can skip
    alerts, dashboard cards, and the rolling signals log.
    """
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)

    ts = _now_iso()
    signal_id = f"{signal.symbol}:{signal.direction}:{ts}"

    entry = {
        "signal_id": signal_id,
        "symbol": signal.symbol,
        "direction": signal.direction,
        "strategy": getattr(signal, "strategy", "CTI-v1"),
        "signal_type": getattr(signal, "signal_type", "pullback"),
        "confidence": round(signal.confidence, 3),
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "lot_size": signal.lot_size,
        "atr": signal.atr,
        "rr": rr,
        "signal_timestamp": ts,
        "grade": "PENDING",
        "status": STATUS_OPEN_SIMULATED,
        "outcome": OUTCOME_NONE,
        "outcome_source": None,
        "exit_time": None,
        "exit_price": None,
        "outcome_checked_at": None,
        "observations_to_outcome": 0,
        "bars_to_outcome": None,
        "max_favorable_excursion": 0.0,
        "max_adverse_excursion": 0.0,
        "ambiguous_reason": None,
        "manually_overridden": False,
        "manual_override_reason": None,
        "grade_timestamp": None,
        "notes": notes,
        "discord_msg_id": discord_msg_id,
        # Indicator snapshot
        "stochrsi_k": getattr(signal, "stochrsi_k", 0.0),
        "stochrsi_d": getattr(signal, "stochrsi_d", 0.0),
        "macd_line": getattr(signal, "macd_line", 0.0),
        "macd_signal": getattr(signal, "macd_signal", 0.0),
        "macd_histogram": getattr(signal, "macd_histogram", 0.0),
        "kc_upper": getattr(signal, "kc_upper", 0.0),
        "kc_mid": getattr(signal, "kc_mid", 0.0),
        "kc_lower": getattr(signal, "kc_lower", 0.0),
        "lr_1h": getattr(signal, "lr_1h", 0.0),
        "lr_15m": getattr(signal, "lr_15m", 0.0),
        "lr_5m": getattr(signal, "lr_5m", 0.0),
        "pullback_trigger": getattr(signal, "pullback_trigger", None),
        "pullback_bridge_status": getattr(signal, "pullback_bridge_status", None),
        "pullback_rejection_reason": getattr(signal, "pullback_rejection_reason", None),
        "shock_blocked_signal": getattr(signal, "shock_blocked_signal", False),
    }

    with _lock:
        existing_entries = _read_entries_oldest_first()
        if _is_continuation_identity(entry.get("signal_type")):
            active_same_direction = _active_managed_trade_for_direction(existing_entries, entry.get("symbol"), entry.get("direction"))
            active_same_symbol = _active_managed_trade_for_symbol(existing_entries, entry.get("symbol"))
            if active_same_direction is not None:
                decision = _evaluate_management_event(active_same_direction, signal, signal_id)
                active_recheck = _active_managed_trade_for_direction(existing_entries, entry.get("symbol"), entry.get("direction"))
                if active_recheck is None or active_recheck is not active_same_direction:
                    decision = TradeManagementDecision(
                        False,
                        "trade_closed_before_management",
                        "trade_closed_before_management",
                        decision.old_stop_loss,
                        decision.old_stop_loss,
                        decision.old_take_profit,
                        decision.old_take_profit,
                        decision.price_at_event,
                    )
                    active_same_direction = active_recheck
                _append_management_evidence(existing_entries, active_same_direction, signal, signal_id, ts, decision)
            elif active_same_symbol is not None:
                warning = TradeManagementDecision(
                    False,
                    "opposite_direction_continuation_warning",
                    "opposite_direction_continuation_warning",
                    _coerce_float(active_same_symbol.get("current_stop_loss", active_same_symbol.get("stop_loss"))),
                    _coerce_float(active_same_symbol.get("current_stop_loss", active_same_symbol.get("stop_loss"))),
                    _coerce_float(active_same_symbol.get("current_take_profit", active_same_symbol.get("take_profit"))),
                    _coerce_float(active_same_symbol.get("current_take_profit", active_same_symbol.get("take_profit"))),
                    _price_at_management_event(signal, active_same_symbol),
                )
                _append_management_evidence(existing_entries, active_same_symbol, signal, signal_id, ts, warning, LIFECYCLE_WARNING)
            else:
                # No active trade to manage — suppress user-facing output. Still
                # write nothing; the caller (alerts.post_signal) skips Discord,
                # signals.json, and callback delivery. Diagnostic intent is
                # preserved via the persisted EvaluatedOpportunity upstream.
                log.debug("Suppressing orphan continuation signal %s: no active %s trade", signal_id, signal.direction)
                return None
            _write_entries(existing_entries)
            return signal_id

        active_prime = _active_prime_for_symbol(existing_entries, entry.get("symbol"))
        signal_ts = _parse_journal_datetime(ts) or datetime.now(timezone.utc)
        inferred_close = _infer_prime_close(active_prime, _signal_prime_candles(signal), signal_ts) if active_prime else None
        if active_prime and not inferred_close:
            _record_prime_suppression(active_prime, entry, ts)
            _write_entries(existing_entries)
            return signal_id
        if active_prime and inferred_close:
            _deactivate_prime(active_prime, inferred_close["reason"], ts, bool(inferred_close["ambiguous"]))

        entry.update(_setup_outcome_fields(signal, entry, existing_entries, ts))
        if active_prime and inferred_close:
            _make_actionable_after_prime_close(entry, signal_ts)
        if entry.get("usable_for_strategy_stats") is True:
            entry.update(_prime_initial_fields())
            if _is_pullback_identity(entry.get("strategy"), entry.get("signal_type")):
                entry.update(_managed_entry_fields(entry))
            else:
                entry.setdefault("lifecycle_role", LIFECYCLE_LEGACY_SIGNAL)
        else:
            entry.update({"prime_active": False, "prime_suppressed_signal_count": 0, "lifecycle_role": LIFECYCLE_LEGACY_SIGNAL})
        existing_entries.append(entry)
        _write_entries(existing_entries)

    return signal_id


def _apply_grade(lookup_key: str, lookup_field: str, grade: str, notes: str) -> bool:
    """Shared rewrite helper — finds the first entry where entry[lookup_field] == lookup_key,
    updates grade/grade_timestamp/notes, and persists the change to Postgres.
    Must be called with _lock already held.
    """
    entries = _read_entries_oldest_first()
    updated = False

    for entry in entries:
        if not updated and entry.get(lookup_field) == lookup_key:
            entry["grade"] = grade
            entry["trade_grade"] = _grade_for_completion(grade)
            close_reason = PRIME_CLOSE_MANUAL_INVALIDATED if entry["trade_grade"] == "INVALID" else PRIME_CLOSE_MANUAL_GRADE
            _deactivate_prime(entry, close_reason)
            if entry["trade_grade"] == "INVALID":
                entry["usable_for_strategy_stats"] = False
                entry["stats_exclusion_reason"] = "manual_invalidated"
                entry["status"] = STATUS_INVALIDATED
                entry["outcome"] = OUTCOME_INVALIDATED_BY_SYSTEM
            elif grade == "EXPIRED":
                entry["status"] = STATUS_EXPIRED
                entry["outcome"] = OUTCOME_EXPIRED
            else:
                entry["status"] = STATUS_CLOSED
                entry["outcome"] = OUTCOME_MANUALLY_CLOSED if grade == "MANUAL_CLOSE" else _default_outcome_for_entry(entry)
            entry["grade_timestamp"] = _now_iso()
            entry["outcome_source"] = OUTCOME_SOURCE_MANUAL
            entry["exit_time"] = entry["grade_timestamp"]
            if entry.get("exit_price") is not None or grade == "MANUAL_CLOSE":
                manual_exit_price = entry.get("exit_price") if entry.get("exit_price") is not None else entry.get("entry_price")
                managed_exit = classify_managed_exit(entry, manual_exit_price, entry["outcome"])
                entry.update({key: value for key, value in managed_exit.items() if value is not None})
                if entry.get("managed_result_category") == MANAGED_RESULT_WIN:
                    entry["trade_grade"] = "TP_HIT"
                elif entry.get("managed_result_category") == MANAGED_RESULT_BREAKEVEN:
                    entry["trade_grade"] = "BE"
                elif entry.get("managed_result_category") == MANAGED_RESULT_LOSS:
                    entry["trade_grade"] = "SL_HIT"
            entry["outcome_checked_at"] = entry["grade_timestamp"]
            entry["manually_overridden"] = True
            entry["manual_override_reason"] = notes or None
            entry["notes"] = notes
            updated = True

    if updated:
        _write_entries(entries)

    return updated


def _apply_notes(lookup_key: str, lookup_field: str, notes: str) -> bool:
    """Update notes only — finds the first entry where entry[lookup_field] == lookup_key,
    updates notes, and persists the change to Postgres. Must be called with _lock held.
    """
    entries = _read_entries_oldest_first()
    updated = False

    for entry in entries:
        if not updated and entry.get(lookup_field) == lookup_key:
            entry["notes"] = notes
            updated = True

    if updated:
        _write_entries(entries)

    return updated


def set_notes_by_signal_id(signal_id: str, notes: str) -> bool:
    """Set notes by signal_id (called from the dashboard UI)."""
    with _lock:
        return _apply_notes(signal_id, "signal_id", notes)


def grade_signal(discord_msg_id: str, grade: str, notes: str = "") -> bool:
    """Grade by Discord message ID (called from bot button interactions)."""
    grade = str(grade or "").upper()
    if grade not in VALID_GRADES:
        log.warning("Invalid grade %r — must be one of %s", grade, VALID_GRADES)
        return False
    with _lock:
        return _apply_grade(discord_msg_id, "discord_msg_id", grade, notes)


def grade_by_signal_id(signal_id: str, grade: str, notes: str = "") -> bool:
    """Grade by signal_id (called from the dashboard UI).

    Works for all signals including migrated ones that have no discord_msg_id.
    """
    grade = str(grade or "").upper()
    if grade not in VALID_GRADES:
        log.warning("Invalid grade %r — must be one of %s", grade, VALID_GRADES)
        return False
    with _lock:
        return _apply_grade(signal_id, "signal_id", grade, notes)


def read_journal() -> list:
    """Return all journal entries as a list of dicts, newest first."""
    with _lock:
        entries = _read_entries_oldest_first()

    return [_apply_outcome_defaults(entry) for entry in reversed(entries)]


def build_journal_export(selection: Optional[SignalJournalExportSelection] = None) -> SignalJournalExportResult:
    """Build a deterministic Signal Journal CSV export for a selected scope."""
    selection = selection or SignalJournalExportSelection()
    _validate_export_selection(selection)
    with _lock:
        entries = [entry for entry in _read_entries_oldest_first() if _entry_matches_selection(entry, selection)]

    extras = sorted({key for entry in entries for key in entry.keys()} - set(EXPORT_FIELDS))
    fields = EXPORT_FIELDS + extras
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for entry in entries:
        normalized = _apply_outcome_defaults(entry)
        writer.writerow({key: _normalize_csv_value(normalized.get(key)) for key in fields})
    return SignalJournalExportResult(out.getvalue(), _export_filename(selection), len(entries))


def export_journal_csv(grade: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None) -> str:
    """Export journal entries as optimization-ready CSV, scoped by grade/range."""
    selection = SignalJournalExportSelection(grade=grade, start=start, end=end)
    return build_journal_export(selection).csv_text


def purge_journal_entries(grade: Optional[str] = None) -> dict[str, int]:
    """Remove journal entries in the requested scope and return removal counts."""
    with _lock:
        entries = _read_entries_oldest_first()
        remaining = [entry for entry in entries if not _entry_matches_grade(entry, grade)]
        removed = len(entries) - len(remaining)
        # _write_entries does a transactional full replace of the Postgres
        # journal, so the purged entries are removed from the source of truth.
        _write_entries(remaining)
    return {"removed_count": removed, "remaining_count": len(remaining)}


def invalidate_signal(signal_id: str, notes: str = "") -> bool:
    """Manually invalidate one signal for strategy stats without deleting evidence."""
    if not signal_id:
        return False
    with _lock:
        return _apply_grade(signal_id, "signal_id", "INVALID", notes)


def reset_signal_to_pending(signal_id: str) -> bool:
    """Reset one signal to PENDING while preserving signal evidence and notes."""
    if not signal_id:
        return False
    reset_fields = (
        "outcome_status",
        "score",
        "reviewed_at",
        "resolved_at",
        "exit_time",
        "exit_price",
        "outcome_checked_at",
        "observations_to_outcome",
        "bars_to_outcome",
        "max_favorable_excursion",
        "max_adverse_excursion",
        "ambiguous_reason",
        "outcome_source",
        "manual_override_reason",
    )
    with _lock:
        entries = _read_entries_oldest_first()
        updated = False
        for entry in entries:
            if not updated and entry.get("signal_id") == signal_id:
                entry["grade"] = PENDING_GRADE
                entry["trade_grade"] = PENDING_GRADE
                entry["status"] = STATUS_OPEN_SIMULATED
                entry["outcome"] = OUTCOME_NONE
                entry["manually_overridden"] = False
                usable = _strategy_usable_for_entry(entry)
                entry["usable_for_strategy_stats"] = usable
                if usable:
                    entry.pop("stats_exclusion_reason", None)
                elif entry.get("stats_exclusion_reason") == "manual_invalidated":
                    entry["stats_exclusion_reason"] = "invalidated_reset_requires_review"
                entry["grade_timestamp"] = None
                if entry.get("prime_active") is True:
                    _deactivate_prime(entry, PRIME_CLOSE_RESET)
                for field in reset_fields:
                    entry.pop(field, None)
                updated = True
        if updated:
            _write_entries(entries)
    return updated

"""Signal journal — append-only JSONL of graded signals.

Each line is a self-contained JSON object. The file is never trimmed;
it is the permanent record an AI agent uses to assess signal quality
and inform trade discretion over time.

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
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

JOURNAL_FILE = Path(__file__).parent / "data" / "signal_journal.jsonl"

PENDING_GRADE = "PENDING"
VALID_GRADES = {"TP_HIT", "SL_HIT", "MANUAL_CLOSE", "EXPIRED"}
FILTER_GRADES = VALID_GRADES | {PENDING_GRADE}
EXPORT_FIELDS = [
    "signal_id",
    "symbol",
    "direction",
    "strategy",
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
    "grade",
    "pending_state",
    "grade_timestamp",
    "trade_result",
    "outcome",
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


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _read_entries_oldest_first() -> list[dict[str, Any]]:
    """Read valid journal entries in storage order while skipping malformed lines."""
    if not JOURNAL_FILE.exists():
        return []

    entries: list[dict[str, Any]] = []
    for line in JOURNAL_FILE.read_text(encoding="utf-8").splitlines():
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


def _write_entries(entries: list[dict[str, Any]]) -> None:
    """Atomically replace the journal with the supplied valid entries."""
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = JOURNAL_FILE.with_suffix(".jsonl.tmp")
    body = "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries)
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(JOURNAL_FILE)


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
    return normalized is None or str(entry.get("grade") or PENDING_GRADE).upper() == normalized


def append_signal(signal, rr: Optional[float] = None, discord_msg_id: Optional[str] = None, notes: str = "") -> str:
    """Append a new PENDING entry to the journal. Returns the signal_id."""
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)

    ts = _now_iso()
    signal_id = f"{signal.symbol}:{signal.direction}:{ts}"

    entry = {
        "signal_id": signal_id,
        "symbol": signal.symbol,
        "direction": signal.direction,
        "strategy": getattr(signal, "strategy", "CTI-v1"),
        "confidence": round(signal.confidence, 3),
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "lot_size": signal.lot_size,
        "atr": signal.atr,
        "rr": rr,
        "signal_timestamp": ts,
        "grade": "PENDING",
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
    }

    with _lock:
        with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    return signal_id


def _apply_grade(lookup_key: str, lookup_field: str, grade: str, notes: str) -> bool:
    """Shared rewrite helper — finds the first entry where entry[lookup_field] == lookup_key,
    updates grade/grade_timestamp/notes, and atomically replaces the file.
    Must be called with _lock already held.
    """
    if not JOURNAL_FILE.exists():
        return False

    lines = JOURNAL_FILE.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
            if not updated and entry.get(lookup_field) == lookup_key:
                entry["grade"] = grade
                entry["grade_timestamp"] = _now_iso()
                entry["notes"] = notes
                stripped = json.dumps(entry)
                updated = True
        except json.JSONDecodeError:
            pass
        new_lines.append(stripped)

    if updated:
        tmp = JOURNAL_FILE.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        tmp.replace(JOURNAL_FILE)

    return updated


def _apply_notes(lookup_key: str, lookup_field: str, notes: str) -> bool:
    """Update notes only — finds first entry where entry[lookup_field] == lookup_key,
    updates notes, and atomically replaces the file. Must be called with _lock held.
    """
    if not JOURNAL_FILE.exists():
        return False

    lines = JOURNAL_FILE.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
            if not updated and entry.get(lookup_field) == lookup_key:
                entry["notes"] = notes
                stripped = json.dumps(entry)
                updated = True
        except json.JSONDecodeError:
            pass
        new_lines.append(stripped)

    if updated:
        tmp = JOURNAL_FILE.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        tmp.replace(JOURNAL_FILE)

    return updated


def set_notes_by_signal_id(signal_id: str, notes: str) -> bool:
    """Set notes by signal_id (called from the dashboard UI)."""
    with _lock:
        return _apply_notes(signal_id, "signal_id", notes)


def grade_signal(discord_msg_id: str, grade: str, notes: str = "") -> bool:
    """Grade by Discord message ID (called from bot button interactions)."""
    if grade not in VALID_GRADES:
        log.warning("Invalid grade %r — must be one of %s", grade, VALID_GRADES)
        return False
    with _lock:
        return _apply_grade(discord_msg_id, "discord_msg_id", grade, notes)


def grade_by_signal_id(signal_id: str, grade: str, notes: str = "") -> bool:
    """Grade by signal_id (called from the dashboard UI).

    Works for all signals including migrated ones that have no discord_msg_id.
    """
    if grade not in VALID_GRADES:
        log.warning("Invalid grade %r — must be one of %s", grade, VALID_GRADES)
        return False
    with _lock:
        return _apply_grade(signal_id, "signal_id", grade, notes)


def read_journal() -> list:
    """Return all journal entries as a list of dicts, newest first."""
    with _lock:
        entries = _read_entries_oldest_first()

    return list(reversed(entries))


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
        writer.writerow({key: _normalize_csv_value(entry.get(key)) for key in fields})
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
        _write_entries(remaining)
    return {"removed_count": removed, "remaining_count": len(remaining)}


def reset_signal_to_pending(signal_id: str) -> bool:
    """Reset one signal to PENDING while preserving signal evidence and notes."""
    if not signal_id:
        return False
    reset_fields = ("outcome", "outcome_status", "score", "reviewed_at", "resolved_at")
    with _lock:
        entries = _read_entries_oldest_first()
        updated = False
        for entry in entries:
            if not updated and entry.get("signal_id") == signal_id:
                entry["grade"] = PENDING_GRADE
                entry["grade_timestamp"] = None
                for field in reset_fields:
                    entry.pop(field, None)
                updated = True
        if updated:
            _write_entries(entries)
    return updated

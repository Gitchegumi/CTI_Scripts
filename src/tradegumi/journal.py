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
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

JOURNAL_FILE = Path(__file__).parent / "data" / "signal_journal.jsonl"

VALID_GRADES = {"TP_HIT", "SL_HIT", "MANUAL_CLOSE", "EXPIRED"}

# Protects all reads and writes to JOURNAL_FILE across threads
# (trading loop thread appends; Discord bot thread grades).
_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


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
        if not JOURNAL_FILE.exists():
            return []

        entries = []
        for line in JOURNAL_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError:
                log.warning("Skipping malformed journal line: %r", stripped[:80])

    return list(reversed(entries))

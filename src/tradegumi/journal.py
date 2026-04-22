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


def append_signal(signal, rr: Optional[float] = None, discord_msg_id: Optional[str] = None) -> str:
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
        "notes": "",
        "discord_msg_id": discord_msg_id,
    }

    with _lock:
        with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    return signal_id


def grade_signal(discord_msg_id: str, grade: str, notes: str = "") -> bool:
    """Find the entry matching discord_msg_id and apply the grade.

    Rewrites the matching line in-place; all other lines are preserved.
    Returns True if an entry was found and updated.
    """
    if grade not in VALID_GRADES:
        log.warning("Invalid grade %r — must be one of %s", grade, VALID_GRADES)
        return False

    with _lock:
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
                if entry.get("discord_msg_id") == discord_msg_id:
                    entry["grade"] = grade
                    entry["grade_timestamp"] = _now_iso()
                    entry["notes"] = notes
                    stripped = json.dumps(entry)
                    updated = True
            except json.JSONDecodeError:
                pass
            new_lines.append(stripped)

        if updated:
            # Write to a temp file then replace atomically to avoid partial writes
            tmp = JOURNAL_FILE.with_suffix(".jsonl.tmp")
            tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            tmp.replace(JOURNAL_FILE)

    return updated


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

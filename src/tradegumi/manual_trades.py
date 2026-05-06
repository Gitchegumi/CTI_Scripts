"""Mode-isolated manual and unified trade-history storage.

This module owns local trade-history data used by the dashboard and manual trades
page. It stores user-created manual trades, mode-scoped annotations, and local
overrides for source-owned historical trades. Source trades are never overwritten;
they are normalized, merged with local mode data, and returned as unified history
records for UI and Agent Export workflows.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

log = logging.getLogger(__name__)

DB_FILE = Path(__file__).parent / "data" / "manual_trades.db"
VALID_MODES = {"alert_only", "demo", "live"}
ALERT_ONLY = "alert_only"
AGENT_EXPORT_SCHEMA_NAME = "Agent Export"
AGENT_EXPORT_SCHEMA_VERSION = "manual-trade-agent-export.v1"

PROTECTED_FIELDS = {
    "symbol",
    "direction",
    "side",
    "entry_price",
    "exit_price",
    "entry_time",
    "exit_time",
    "open_price",
    "close_price",
    "open_time",
    "close_time",
    "volume",
    "status",
    "fees",
    "financing",
    "pnl",
    "pnl_percent",
    "realized_pl",
}

ANNOTATION_FIELDS = {"notes", "tags"}


class ManualTradeError(ValueError):
    """Base exception for invalid manual-trade operations."""


class TradePermissionError(PermissionError):
    """Raised when the current mode does not allow a requested mutation."""


class TradeNotFoundError(LookupError):
    """Raised when a trade identity cannot be found in the current mode."""


def _get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Return a SQLite connection for the manual trade store.

    Args:
        db_path: Optional database path used by tests or callers that need an
            isolated store.

    Returns:
        SQLite connection with row access by column name.
    """
    path = Path(db_path) if db_path is not None else DB_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    """Return the current local timestamp in ISO 8601 format."""
    return datetime.now().astimezone().isoformat()


def _normal_mode(mode: str | None) -> str:
    """Normalize a bot mode, defaulting legacy missing values to alert_only."""
    value = (mode or ALERT_ONLY).strip().lower()
    return value if value in VALID_MODES else ALERT_ONLY


def _json_loads(value: Any, default: Any) -> Any:
    """Decode JSON text while tolerating legacy empty or malformed values."""
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _json_dumps(value: Any) -> str:
    """Encode local structured values deterministically for SQLite storage."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def init_schema(db_path: Path | str | None = None) -> None:
    """Initialize and migrate local trade-history tables.

    Existing records are preserved. Missing bot-mode values are left nullable in
    storage but interpreted as alert_only by all read paths.
    """
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS manual_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('long', 'short')),
                entry_price REAL NOT NULL,
                exit_price REAL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                volume REAL,
                fees REAL DEFAULT 0.0,
                pnl REAL DEFAULT 0.0,
                pnl_percent REAL DEFAULT 0.0,
                status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed')),
                notes TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                bot_mode TEXT DEFAULT 'alert_only',
                source TEXT DEFAULT 'manual',
                source_trade_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(cursor, "manual_trades", "volume", "REAL")
        _ensure_column(cursor, "manual_trades", "fees", "REAL DEFAULT 0.0")
        _ensure_column(cursor, "manual_trades", "tags", "TEXT DEFAULT '[]'")
        _ensure_column(cursor, "manual_trades", "bot_mode", "TEXT DEFAULT 'alert_only'")
        _ensure_column(cursor, "manual_trades", "source", "TEXT DEFAULT 'manual'")
        _ensure_column(cursor, "manual_trades", "source_trade_id", "TEXT")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_identity TEXT NOT NULL,
                source TEXT NOT NULL,
                source_trade_id TEXT NOT NULL,
                bot_mode TEXT DEFAULT 'alert_only',
                notes TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(trade_identity, bot_mode)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_identity TEXT NOT NULL,
                source TEXT NOT NULL,
                source_trade_id TEXT NOT NULL,
                bot_mode TEXT DEFAULT 'alert_only',
                values_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(trade_identity, bot_mode)
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_trades_symbol ON manual_trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_trades_status ON manual_trades(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_trades_entry_time ON manual_trades(entry_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_trades_mode ON manual_trades(bot_mode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_annotations_identity_mode ON trade_annotations(trade_identity, bot_mode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_overrides_identity_mode ON trade_overrides(trade_identity, bot_mode)")
        conn.commit()
    finally:
        conn.close()


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    """Add a column to an existing SQLite table when it is missing."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row["name"] for row in cursor.fetchall()}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _calculate_pnl(direction: str, entry_price: float, exit_price: float | None) -> tuple[float, float, str]:
    """Calculate simplified P/L fields for local manual trade records."""
    if exit_price is None:
        return 0.0, 0.0, "open"
    pnl = (exit_price - entry_price) if direction == "long" else (entry_price - exit_price)
    pnl_percent = (pnl / entry_price) * 100 if entry_price else 0.0
    return pnl, pnl_percent, "closed"


def canonical_identity(source: str, source_trade_id: str | int) -> str:
    """Build a canonical identity for de-duplicating and mutating trades."""
    normalized_source = (source or "source").strip().lower()
    return f"{normalized_source}:{source_trade_id}"


def _manual_identity(trade_id: int | str) -> str:
    """Build the canonical identity for a manual trade id."""
    return canonical_identity("manual", trade_id)


def create_trade(
    symbol: str,
    direction: str,
    entry_price: float,
    entry_time: str,
    exit_price: Optional[float] = None,
    exit_time: Optional[str] = None,
    notes: str = "",
    tags: Optional[list[str]] = None,
    bot_mode: str = ALERT_ONLY,
    volume: Optional[float] = None,
    fees: float = 0.0,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Create a new manually entered trade for alert_only mode.

    Args:
        symbol: Trading symbol.
        direction: Trade direction, long or short.
        entry_price: Entry price.
        entry_time: ISO-8601 entry timestamp.
        exit_price: Optional exit price.
        exit_time: Optional ISO-8601 exit timestamp.
        notes: Optional local notes.
        tags: Optional local tags.
        bot_mode: Current bot mode. Only alert_only may create manual trades.
        volume: Optional trade size.
        fees: Optional fee value.
        db_path: Optional SQLite path.

    Returns:
        Created unified historical trade record.

    Raises:
        TradePermissionError: If current mode is not alert_only.
        ManualTradeError: If required fields are invalid.
    """
    mode = _normal_mode(bot_mode)
    if mode != ALERT_ONLY:
        raise TradePermissionError("Manual trade creation is allowed only in alert_only mode")
    direction = (direction or "").lower()
    if not symbol or direction not in {"long", "short"}:
        raise ManualTradeError("symbol and direction (long/short) are required")

    init_schema(db_path)
    pnl, pnl_percent, status = _calculate_pnl(direction, float(entry_price), exit_price)
    now = _now_iso()
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO manual_trades
            (symbol, direction, entry_price, exit_price, entry_time, exit_time,
             volume, fees, pnl, pnl_percent, status, notes, tags, bot_mode,
             source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
            """,
            (
                symbol.strip().upper(),
                direction,
                float(entry_price),
                exit_price,
                entry_time,
                exit_time,
                volume,
                fees,
                pnl,
                pnl_percent,
                status,
                notes or "",
                _json_dumps(_normalize_tags(tags)),
                mode,
                now,
                now,
            ),
        )
        trade_id = cursor.lastrowid
        cursor.execute("UPDATE manual_trades SET source_trade_id = ? WHERE id = ?", (str(trade_id), trade_id))
        conn.commit()
        record = _get_manual_trade_by_id(trade_id, db_path)
        return _manual_row_to_unified(record, mode)
    finally:
        conn.close()


def _normalize_tags(tags: Any) -> list[str]:
    """Normalize free-form tag values for storage and filtering."""
    if isinstance(tags, str) and tags.strip() and not tags.strip().startswith("["):
        raw_tags = [tag.strip() for tag in tags.split(",")]
    else:
        raw_tags = tags if isinstance(tags, list) else _json_loads(tags, [])
    normalized: list[str] = []
    for tag in raw_tags or []:
        value = str(tag).strip().lower()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _get_manual_trade_by_id(trade_id: int | str, db_path: Path | str | None = None) -> dict[str, Any]:
    """Fetch a manual trade row by numeric id."""
    init_schema(db_path)
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM manual_trades WHERE id = ?", (int(trade_id),))
        row = cursor.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def get_trade_by_id(trade_id: int, db_path: Path | str | None = None) -> dict[str, Any]:
    """Get a single manual trade by id for legacy callers."""
    row = _get_manual_trade_by_id(trade_id, db_path)
    if not row:
        return {}
    return _legacy_manual_record(row)


def _legacy_manual_record(row: dict[str, Any]) -> dict[str, Any]:
    """Return a manual trade in the legacy shape used by earlier callers."""
    record = dict(row)
    record["tags"] = _normalize_tags(record.get("tags"))
    record["bot_mode"] = _normal_mode(record.get("bot_mode"))
    return record


def _manual_row_to_unified(row: dict[str, Any], current_mode: str) -> dict[str, Any]:
    """Convert a manual SQLite row into the unified history shape."""
    mode = _normal_mode(row.get("bot_mode"))
    trade_id = row["id"]
    identity = _manual_identity(trade_id)
    direction = (row.get("direction") or "long").lower()
    entry_price = float(row.get("entry_price") or 0)
    exit_price = row.get("exit_price")
    return {
        "id": identity,
        "source": "manual",
        "source_trade_id": str(row.get("source_trade_id") or trade_id),
        "bot_mode": mode,
        "is_manual": True,
        "symbol": row.get("symbol"),
        "direction": direction,
        "side": "BUY" if direction == "long" else "SELL",
        "entry_price": entry_price,
        "exit_price": exit_price,
        "entry_time": row.get("entry_time"),
        "exit_time": row.get("exit_time"),
        "open_price": entry_price,
        "close_price": exit_price,
        "open_time": row.get("entry_time"),
        "close_time": row.get("exit_time") or row.get("entry_time"),
        "volume": row.get("volume"),
        "status": row.get("status") or ("closed" if exit_price is not None else "open"),
        "fees": float(row.get("fees") or 0),
        "financing": float(row.get("fees") or 0),
        "pnl": float(row.get("pnl") or 0),
        "pnl_percent": float(row.get("pnl_percent") or 0),
        "realized_pl": float(row.get("pnl") or 0),
        "notes": row.get("notes") or "",
        "tags": _normalize_tags(row.get("tags")),
        "has_overrides": False,
        "overridden_fields": [],
        "source_values": {},
        "displayed_values": {},
        "permissions": permission_snapshot(mode, is_manual=True, current_mode=current_mode),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def permission_snapshot(bot_mode: str, *, is_manual: bool, current_mode: str | None = None) -> dict[str, bool]:
    """Return edit permissions for a trade under the current bot mode."""
    mode = _normal_mode(current_mode or bot_mode)
    return {
        "can_edit_all_fields": mode == ALERT_ONLY,
        "can_edit_notes_tags": True,
        "can_delete": mode == ALERT_ONLY and is_manual,
    }


def _source_trade_to_unified(trade: Any, current_mode: str) -> dict[str, Any]:
    """Normalize a source-owned history record into the unified history shape."""
    raw = trade if isinstance(trade, dict) else _object_to_dict(trade)
    source = str(raw.get("source") or raw.get("provider") or "execution_history").lower()
    source_trade_id = str(raw.get("source_trade_id") or raw.get("id") or raw.get("trade_id"))
    identity = canonical_identity(source, source_trade_id)
    side = (raw.get("side") or raw.get("direction") or "").upper()
    direction = (raw.get("direction") or ("long" if side == "BUY" else "short")).lower()
    open_price = raw.get("open_price", raw.get("entry_price"))
    close_price = raw.get("close_price", raw.get("exit_price"))
    open_time = raw.get("open_time", raw.get("entry_time"))
    close_time = raw.get("close_time", raw.get("exit_time") or open_time)
    pnl = raw.get("pnl", raw.get("realized_pl", 0))
    financing = raw.get("financing", raw.get("fees", 0))
    return {
        "id": identity,
        "source": source,
        "source_trade_id": source_trade_id,
        "bot_mode": current_mode,
        "is_manual": False,
        "symbol": raw.get("symbol"),
        "direction": direction if direction in {"long", "short"} else "long",
        "side": side if side in {"BUY", "SELL"} else ("BUY" if direction == "long" else "SELL"),
        "entry_price": open_price,
        "exit_price": close_price,
        "entry_time": open_time,
        "exit_time": close_time,
        "open_price": open_price,
        "close_price": close_price,
        "open_time": open_time,
        "close_time": close_time,
        "volume": raw.get("volume"),
        "status": raw.get("status") or "closed",
        "fees": financing,
        "financing": financing,
        "pnl": pnl,
        "pnl_percent": raw.get("pnl_percent", 0),
        "realized_pl": raw.get("realized_pl", pnl),
        "notes": raw.get("notes") or "",
        "tags": _normalize_tags(raw.get("tags")),
        "has_overrides": False,
        "overridden_fields": [],
        "source_values": dict(raw),
        "displayed_values": {},
        "permissions": permission_snapshot(current_mode, is_manual=False),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "strategy": raw.get("strategy"),
        "signal_id": raw.get("signal_id"),
        "confidence": raw.get("confidence"),
        "setup_label": raw.get("setup_label"),
        "source_context": raw.get("source_context"),
    }


def _object_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a simple trade object or dataclass-like value to a dictionary."""
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    return {name: getattr(obj, name) for name in dir(obj) if not name.startswith("_") and not callable(getattr(obj, name))}


def get_unified_trade_history(
    *,
    bot_mode: str = ALERT_ONLY,
    source_trades: Optional[Iterable[Any]] = None,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Return de-duplicated current-mode trade history.

    Args:
        bot_mode: Current bot mode used for isolation.
        source_trades: Source-owned trade history records to merge.
        symbol: Optional symbol filter.
        status: Optional open/closed filter.
        tag: Optional tag filter.
        start_date: Optional lower date bound based on entry/open time.
        end_date: Optional upper date bound based on entry/open time.
        limit: Maximum records.
        db_path: Optional SQLite path.

    Returns:
        Unified trade records sorted by close/entry time descending.
    """
    init_schema(db_path)
    mode = _normal_mode(bot_mode)
    records: dict[str, dict[str, Any]] = {}
    for source_trade in source_trades or []:
        record = _source_trade_to_unified(source_trade, mode)
        records[record["id"]] = record
    for row in _get_manual_rows(mode, db_path):
        record = _manual_row_to_unified(row, mode)
        records[record["id"]] = record
    annotations = _get_annotations(mode, db_path)
    overrides = _get_overrides(mode, db_path)
    merged = [_apply_local_layers(record, annotations, overrides, mode) for record in records.values()]
    filtered = [
        record for record in merged
        if _matches_filters(record, symbol=symbol, status=status, tag=tag, start_date=start_date, end_date=end_date)
    ]
    filtered.sort(key=lambda item: str(item.get("close_time") or item.get("entry_time") or ""), reverse=True)
    return filtered[: max(0, int(limit))]


def _get_manual_rows(bot_mode: str, db_path: Path | str | None) -> list[dict[str, Any]]:
    """Fetch manual rows that belong to the requested mode."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        if bot_mode == ALERT_ONLY:
            cursor.execute("SELECT * FROM manual_trades WHERE bot_mode = ? OR bot_mode IS NULL OR bot_mode = ''", (ALERT_ONLY,))
        else:
            cursor.execute("SELECT * FROM manual_trades WHERE bot_mode = ?", (bot_mode,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def _get_annotations(bot_mode: str, db_path: Path | str | None) -> dict[str, dict[str, Any]]:
    """Fetch mode-scoped annotations keyed by canonical trade identity."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        if bot_mode == ALERT_ONLY:
            cursor.execute("SELECT * FROM trade_annotations WHERE bot_mode = ? OR bot_mode IS NULL OR bot_mode = ''", (ALERT_ONLY,))
        else:
            cursor.execute("SELECT * FROM trade_annotations WHERE bot_mode = ?", (bot_mode,))
        return {row["trade_identity"]: dict(row) for row in cursor.fetchall()}
    finally:
        conn.close()


def _get_overrides(bot_mode: str, db_path: Path | str | None) -> dict[str, dict[str, Any]]:
    """Fetch mode-scoped overrides keyed by canonical trade identity."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        if bot_mode == ALERT_ONLY:
            cursor.execute("SELECT * FROM trade_overrides WHERE bot_mode = ? OR bot_mode IS NULL OR bot_mode = ''", (ALERT_ONLY,))
        else:
            cursor.execute("SELECT * FROM trade_overrides WHERE bot_mode = ?", (bot_mode,))
        return {row["trade_identity"]: dict(row) for row in cursor.fetchall()}
    finally:
        conn.close()


def _apply_local_layers(
    record: dict[str, Any],
    annotations: dict[str, dict[str, Any]],
    overrides: dict[str, dict[str, Any]],
    current_mode: str,
) -> dict[str, Any]:
    """Merge annotations and overrides onto a unified trade record."""
    identity = record["id"]
    source_values = dict(record)
    if identity in overrides:
        values = _json_loads(overrides[identity].get("values_json"), {})
        for field, value in values.items():
            record[field] = value
        record["has_overrides"] = bool(values)
        record["overridden_fields"] = sorted(values)
        record["displayed_values"] = dict(values)
        record["source_values"] = source_values
        _sync_alias_fields(record)
    if identity in annotations:
        annotation = annotations[identity]
        record["notes"] = annotation.get("notes") or ""
        record["tags"] = _normalize_tags(annotation.get("tags"))
        record["updated_at"] = annotation.get("updated_at") or record.get("updated_at")
    record["permissions"] = permission_snapshot(record.get("bot_mode") or current_mode, is_manual=bool(record.get("is_manual")), current_mode=current_mode)
    return record


def _sync_alias_fields(record: dict[str, Any]) -> None:
    """Keep dashboard and manual field aliases consistent after overrides."""
    alias_pairs = {
        "entry_price": "open_price",
        "exit_price": "close_price",
        "entry_time": "open_time",
        "exit_time": "close_time",
        "fees": "financing",
        "pnl": "realized_pl",
    }
    for left, right in alias_pairs.items():
        if left in record and record[left] is not None:
            record[right] = record[left]
        elif right in record and record[right] is not None:
            record[left] = record[right]
    if "direction" in record:
        record["side"] = "BUY" if record["direction"] == "long" else "SELL"
    elif "side" in record:
        record["direction"] = "long" if record["side"] == "BUY" else "short"


def _matches_filters(
    record: dict[str, Any],
    *,
    symbol: Optional[str],
    status: Optional[str],
    tag: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> bool:
    """Return whether a unified trade record matches list filters."""
    if symbol and str(record.get("symbol", "")).upper() != symbol.upper():
        return False
    if status and record.get("status") != status:
        return False
    if tag and tag.strip().lower() not in _normalize_tags(record.get("tags")):
        return False
    timestamp = str(record.get("entry_time") or record.get("open_time") or "")
    if start_date and timestamp < start_date:
        return False
    if end_date and timestamp > end_date:
        return False
    return True


def get_all_trades(
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    bot_mode: str = ALERT_ONLY,
    source_trades: Optional[Iterable[Any]] = None,
    tag: Optional[str] = None,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Get unified trade history for legacy manual-trade list callers."""
    return get_unified_trade_history(
        bot_mode=bot_mode,
        source_trades=source_trades,
        symbol=symbol,
        status=status,
        tag=tag,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        db_path=db_path,
    )


def get_dashboard_trade_history(
    *,
    count: int = 50,
    bot_mode: str = ALERT_ONLY,
    source_trades: Optional[Iterable[Any]] = None,
    symbol: Optional[str] = None,
    tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Return unified history records in the dashboard Trade History shape."""
    records = get_unified_trade_history(
        bot_mode=bot_mode,
        source_trades=source_trades,
        symbol=symbol,
        tag=tag,
        start_date=start_date,
        end_date=end_date,
        limit=count,
        db_path=db_path,
    )
    return [_dashboard_record(record) for record in records]


def _dashboard_record(record: dict[str, Any]) -> dict[str, Any]:
    """Serialize a unified trade record for the main dashboard table."""
    return {
        "id": record["id"],
        "source": record.get("source"),
        "source_trade_id": record.get("source_trade_id"),
        "bot_mode": record.get("bot_mode"),
        "is_manual": record.get("is_manual"),
        "symbol": record.get("symbol"),
        "side": record.get("side"),
        "volume": record.get("volume") or 0,
        "open_price": record.get("open_price") or 0,
        "close_price": record.get("close_price") or record.get("open_price") or 0,
        "open_time": record.get("open_time") or record.get("entry_time"),
        "close_time": record.get("close_time") or record.get("exit_time") or record.get("entry_time"),
        "realized_pl": record.get("realized_pl", record.get("pnl", 0)) or 0,
        "financing": record.get("financing", record.get("fees", 0)) or 0,
        "pnl": record.get("pnl", 0) or 0,
        "notes": record.get("notes") or "",
        "tags": _normalize_tags(record.get("tags")),
        "has_overrides": bool(record.get("has_overrides")),
        "permissions": record.get("permissions") or {},
    }


def update_trade(
    trade_id: int,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    entry_time: Optional[str] = None,
    exit_time: Optional[str] = None,
    notes: Optional[str] = None,
    tags: Optional[list[str]] = None,
    bot_mode: str = ALERT_ONLY,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Update a manual trade by numeric id for legacy callers."""
    payload = {
        key: value for key, value in {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "notes": notes,
            "tags": tags,
        }.items() if value is not None
    }
    return update_trade_record(_manual_identity(trade_id), payload, bot_mode=bot_mode, db_path=db_path)


def update_trade_record(
    identity: str,
    updates: dict[str, Any],
    *,
    bot_mode: str,
    source_trades: Optional[Iterable[Any]] = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Update a unified trade according to current-mode permissions.

    Args:
        identity: Canonical trade identity, such as manual:1.
        updates: Fields requested by the client.
        bot_mode: Current bot mode.
        source_trades: Source trades used to resolve non-manual identities.
        db_path: Optional SQLite path.

    Returns:
        Updated unified trade record.

    Raises:
        TradeNotFoundError: If the identity is not in current-mode history.
        TradePermissionError: If the update attempts a disallowed mutation.
    """
    init_schema(db_path)
    mode = _normal_mode(bot_mode)
    records = {record["id"]: record for record in get_unified_trade_history(bot_mode=mode, source_trades=source_trades, limit=10_000, db_path=db_path)}
    if identity not in records:
        raise TradeNotFoundError("Trade not found")
    record = records[identity]
    normalized_updates = _normalize_update_payload(updates)
    protected_updates = {key: value for key, value in normalized_updates.items() if key in PROTECTED_FIELDS}
    annotation_updates = {key: value for key, value in normalized_updates.items() if key in ANNOTATION_FIELDS}

    if mode != ALERT_ONLY and protected_updates:
        raise TradePermissionError("Only notes and tags are editable outside alert_only mode")

    if record.get("is_manual") and mode == ALERT_ONLY:
        _update_manual_record(identity, normalized_updates, db_path)
    elif protected_updates:
        _upsert_override(record, protected_updates, mode, db_path)
    if annotation_updates or (not protected_updates and mode != ALERT_ONLY):
        _upsert_annotation(record, annotation_updates, mode, db_path)
    return _find_updated_record(identity, bot_mode=mode, source_trades=source_trades, db_path=db_path)


def _normalize_update_payload(updates: dict[str, Any]) -> dict[str, Any]:
    """Normalize UI/API aliases into the unified storage field names."""
    result = dict(updates or {})
    alias_map = {
        "side": lambda value: "long" if str(value).upper() == "BUY" else "short",
        "open_price": float,
        "close_price": lambda value: None if value in ("", None) else float(value),
        "open_time": str,
        "close_time": str,
        "financing": float,
        "realized_pl": float,
    }
    if "side" in result and "direction" not in result:
        result["direction"] = alias_map["side"](result.pop("side"))
    if "open_price" in result and "entry_price" not in result:
        result["entry_price"] = alias_map["open_price"](result.pop("open_price"))
    if "close_price" in result and "exit_price" not in result:
        result["exit_price"] = alias_map["close_price"](result.pop("close_price"))
    if "open_time" in result and "entry_time" not in result:
        result["entry_time"] = alias_map["open_time"](result.pop("open_time"))
    if "close_time" in result and "exit_time" not in result:
        result["exit_time"] = alias_map["close_time"](result.pop("close_time"))
    if "financing" in result and "fees" not in result:
        result["fees"] = alias_map["financing"](result.pop("financing"))
    if "realized_pl" in result and "pnl" not in result:
        result["pnl"] = alias_map["realized_pl"](result.pop("realized_pl"))
    if "tags" in result:
        result["tags"] = _normalize_tags(result["tags"])
    if "direction" in result and result["direction"]:
        result["direction"] = str(result["direction"]).lower()
    for price_field in ("entry_price", "exit_price", "volume", "fees", "pnl", "pnl_percent"):
        if price_field in result and result[price_field] not in (None, ""):
            result[price_field] = float(result[price_field])
    return result


def _update_manual_record(identity: str, updates: dict[str, Any], db_path: Path | str | None) -> None:
    """Apply full-field updates to a manual trade row."""
    trade_id = identity.split(":", 1)[1]
    current = _get_manual_trade_by_id(trade_id, db_path)
    if not current:
        raise TradeNotFoundError("Trade not found")
    effective = dict(current)
    effective.update({key: value for key, value in updates.items() if key != "tags"})
    direction = str(effective.get("direction") or "long").lower()
    entry_price = float(effective.get("entry_price") or 0)
    exit_price = effective.get("exit_price")
    calculated_pnl, calculated_pnl_percent, status = _calculate_pnl(direction, entry_price, exit_price)
    allowed = {
        "symbol",
        "direction",
        "entry_price",
        "exit_price",
        "entry_time",
        "exit_time",
        "volume",
        "fees",
        "pnl",
        "pnl_percent",
        "notes",
        "tags",
    }
    set_values = {key: updates[key] for key in allowed if key in updates}
    set_values["pnl"] = updates.get("pnl", calculated_pnl)
    set_values["pnl_percent"] = updates.get("pnl_percent", calculated_pnl_percent)
    set_values["status"] = updates.get("status") or status
    set_values["updated_at"] = _now_iso()
    if "tags" in set_values:
        set_values["tags"] = _json_dumps(_normalize_tags(set_values["tags"]))
    if "symbol" in set_values:
        set_values["symbol"] = str(set_values["symbol"]).upper()
    _execute_update("manual_trades", set_values, "id = ?", [trade_id], db_path)


def _execute_update(table: str, values: dict[str, Any], where_sql: str, where_params: list[Any], db_path: Path | str | None) -> None:
    """Execute a simple SQLite UPDATE with named values."""
    if not values:
        return
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        assignments = ", ".join(f"{key} = ?" for key in values)
        cursor.execute(f"UPDATE {table} SET {assignments} WHERE {where_sql}", list(values.values()) + where_params)
        conn.commit()
    finally:
        conn.close()


def _upsert_annotation(record: dict[str, Any], updates: dict[str, Any], bot_mode: str, db_path: Path | str | None) -> None:
    """Insert or update notes/tags for a trade identity and mode."""
    now = _now_iso()
    existing = _get_annotations(bot_mode, db_path).get(record["id"], {})
    notes = updates.get("notes", existing.get("notes", record.get("notes", "")))
    tags = _normalize_tags(updates.get("tags", existing.get("tags", record.get("tags", []))))
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO trade_annotations
            (trade_identity, source, source_trade_id, bot_mode, notes, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_identity, bot_mode) DO UPDATE SET
                notes = excluded.notes,
                tags = excluded.tags,
                updated_at = excluded.updated_at
            """,
            (
                record["id"],
                record["source"],
                str(record["source_trade_id"]),
                bot_mode,
                notes or "",
                _json_dumps(tags),
                existing.get("created_at") or now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _upsert_override(record: dict[str, Any], updates: dict[str, Any], bot_mode: str, db_path: Path | str | None) -> None:
    """Insert or update local override values for a non-manual source trade."""
    if bot_mode != ALERT_ONLY:
        raise TradePermissionError("Full-field overrides are allowed only in alert_only mode")
    now = _now_iso()
    existing = _get_overrides(bot_mode, db_path).get(record["id"], {})
    values = _json_loads(existing.get("values_json"), {})
    values.update({key: value for key, value in updates.items() if key in PROTECTED_FIELDS})
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO trade_overrides
            (trade_identity, source, source_trade_id, bot_mode, values_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_identity, bot_mode) DO UPDATE SET
                values_json = excluded.values_json,
                updated_at = excluded.updated_at
            """,
            (
                record["id"],
                record["source"],
                str(record["source_trade_id"]),
                bot_mode,
                _json_dumps(values),
                existing.get("created_at") or now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _find_updated_record(
    identity: str,
    *,
    bot_mode: str,
    source_trades: Optional[Iterable[Any]],
    db_path: Path | str | None,
) -> dict[str, Any]:
    """Find a trade after mutation in the unified current-mode list."""
    for record in get_unified_trade_history(bot_mode=bot_mode, source_trades=source_trades, limit=10_000, db_path=db_path):
        if record["id"] == identity:
            return record
    raise TradeNotFoundError("Trade not found after update")


def delete_trade(trade_id: int, bot_mode: str = ALERT_ONLY, db_path: Path | str | None = None) -> bool:
    """Delete a manual trade by numeric id when alert_only permissions allow it."""
    return delete_trade_record(_manual_identity(trade_id), bot_mode=bot_mode, db_path=db_path)


def delete_trade_record(
    identity: str,
    *,
    bot_mode: str,
    db_path: Path | str | None = None,
) -> bool:
    """Delete a manually created trade from alert_only mode.

    Raises:
        TradePermissionError: If mode or origin does not allow deletion.
    """
    init_schema(db_path)
    mode = _normal_mode(bot_mode)
    if mode != ALERT_ONLY:
        raise TradePermissionError("Trade deletion is allowed only in alert_only mode")
    if not identity.startswith("manual:"):
        raise TradePermissionError("Only manually created trades can be deleted")
    trade_id = identity.split(":", 1)[1]
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM manual_trades WHERE id = ? AND (bot_mode = ? OR bot_mode IS NULL OR bot_mode = '')", (trade_id, ALERT_ONLY))
        deleted = cursor.rowcount > 0
        if deleted:
            cursor.execute("DELETE FROM trade_annotations WHERE trade_identity = ?", (identity,))
            cursor.execute("DELETE FROM trade_overrides WHERE trade_identity = ?", (identity,))
        conn.commit()
        return deleted
    finally:
        conn.close()


def get_summary_stats(
    bot_mode: str = ALERT_ONLY,
    source_trades: Optional[Iterable[Any]] = None,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Get summary statistics for the current mode's unified trade history."""
    records = get_unified_trade_history(bot_mode=bot_mode, source_trades=source_trades, limit=10_000, db_path=db_path)
    closed = [record for record in records if record.get("status") == "closed"]
    wins = [record for record in closed if float(record.get("pnl") or 0) >= 0]
    losses = [record for record in closed if float(record.get("pnl") or 0) < 0]
    total_pnl = sum(float(record.get("pnl") or 0) for record in closed)
    total_pct = sum(float(record.get("pnl_percent") or 0) for record in closed)
    closed_count = len(closed)
    return {
        "bot_mode": _normal_mode(bot_mode),
        "total_trades": len(records),
        "closed_trades": closed_count,
        "open_trades": len(records) - closed_count,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round((len(wins) / closed_count * 100) if closed_count else 0.0, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl": round((total_pnl / closed_count) if closed_count else 0.0, 2),
        "avg_pnl_percent": round((total_pct / closed_count) if closed_count else 0.0, 2),
    }


def export_agent_data(
    *,
    bot_mode: str = ALERT_ONLY,
    source_trades: Optional[Iterable[Any]] = None,
    symbol: Optional[str] = None,
    tag: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Build a mode-isolated Agent Export package for LLM workflows."""
    mode = _normal_mode(bot_mode)
    records = get_unified_trade_history(
        bot_mode=mode,
        source_trades=source_trades,
        symbol=symbol,
        tag=tag,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        db_path=db_path,
    )
    return {
        "schema_version": AGENT_EXPORT_SCHEMA_VERSION,
        "schema_name": AGENT_EXPORT_SCHEMA_NAME,
        "generated_at": _now_iso(),
        "bot_mode": mode,
        "scope": {
            "symbol": symbol,
            "tag": tag,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        },
        "chunking": {
            "chunk_index": 1,
            "chunk_count": 1,
            "record_offset": 0,
            "record_limit": limit,
        },
        "summary": {
            "record_count": len(records),
            "manual_count": sum(1 for record in records if record.get("is_manual")),
            "non_manual_count": sum(1 for record in records if not record.get("is_manual")),
            "override_count": sum(1 for record in records if record.get("has_overrides")),
            "tag_count": len({tag for record in records for tag in _normalize_tags(record.get("tags"))}),
        },
        "field_metadata": {
            "displayed_values": "Values shown after local overrides are applied.",
            "source_values": "Original source-owned values when available.",
            "overridden_fields": "Fields corrected locally for AI-assisted strategy review.",
            "strategy_context": "Optional linked strategy or signal fields when already available.",
        },
        "analysis_context": {
            "purpose": "Evaluate trading strategy outcomes and support AI-assisted adjustments.",
            "mode_isolation": "Records belong only to the exported bot mode.",
            "legacy_default": "Records without historical mode metadata are classified as alert_only.",
            "override_semantics": "Source records are not overwritten; local corrections are layered for display and export.",
        },
        "records": [_agent_record(record) for record in records],
    }


def _agent_record(record: dict[str, Any]) -> dict[str, Any]:
    """Serialize a unified trade for Agent Export."""
    keys = [
        "id",
        "source",
        "source_trade_id",
        "bot_mode",
        "is_manual",
        "symbol",
        "direction",
        "side",
        "entry_price",
        "exit_price",
        "entry_time",
        "exit_time",
        "volume",
        "status",
        "fees",
        "pnl",
        "pnl_percent",
        "notes",
        "tags",
        "has_overrides",
        "overridden_fields",
        "source_values",
        "displayed_values",
        "permissions",
        "strategy",
        "signal_id",
        "confidence",
        "setup_label",
        "source_context",
    ]
    return {key: record.get(key) for key in keys if key in record}


try:
    init_schema()
except sqlite3.Error as exc:
    log.warning("Manual trade database initialization deferred: %s", exc)

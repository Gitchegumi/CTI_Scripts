"""Manual trade history — CRUD operations for manually logged trades.

This module provides functionality to manually log trades for strategy validation
when the bot is in "alert-only" mode. Trades are stored in a separate SQLite table
to keep them distinct from auto-executed trades.

Schema per manual trade entry
-----------------------------
id:               INTEGER PRIMARY KEY
symbol:           TEXT NOT NULL
direction:        TEXT NOT NULL ('long' or 'short')
entry_price:      REAL NOT NULL
exit_price:       REAL
entry_time:       TEXT NOT NULL (ISO 8601)
exit_time:        TEXT (ISO 8601)
pnl:              REAL DEFAULT 0.0
pnl_percent:      REAL DEFAULT 0.0
status:           TEXT DEFAULT 'open' ('open' or 'closed')
notes:            TEXT DEFAULT ''
created_at:       TEXT NOT NULL (ISO 8601)
updated_at:       TEXT NOT NULL (ISO 8601)
"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

log = logging.getLogger(__name__)

DB_FILE = Path(__file__).parent / "data" / "manual_trades.db"


def _get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    """Initialize the manual trades table if it doesn't exist."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manual_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('long', 'short')),
                entry_price REAL NOT NULL,
                exit_price REAL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                pnl REAL DEFAULT 0.0,
                pnl_percent REAL DEFAULT 0.0,
                status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed')),
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_trades_symbol ON manual_trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_trades_status ON manual_trades(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_trades_entry_time ON manual_trades(entry_time)")
        conn.commit()
    finally:
        conn.close()


def _now_iso() -> str:
    """Return current timestamp in ISO 8601 format."""
    return datetime.now().astimezone().isoformat()


def create_trade(
    symbol: str,
    direction: str,
    entry_price: float,
    entry_time: str,
    exit_price: Optional[float] = None,
    exit_time: Optional[str] = None,
    notes: str = ""
) -> Dict[str, Any]:
    """Create a new manual trade entry.
    
    Returns the created trade as a dict.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Calculate P&L if exit price provided
        pnl = 0.0
        pnl_percent = 0.0
        status = "open"
        
        if exit_price is not None:
            if direction == "long":
                pnl = (exit_price - entry_price)
            else:
                pnl = (entry_price - exit_price)
            pnl_percent = (pnl / entry_price) * 100 if entry_price != 0 else 0.0
            status = "closed"
        
        now = _now_iso()
        cursor.execute("""
            INSERT INTO manual_trades 
            (symbol, direction, entry_price, exit_price, entry_time, exit_time, 
             pnl, pnl_percent, status, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol, direction, entry_price, exit_price, entry_time, exit_time,
            pnl, pnl_percent, status, notes, now, now
        ))
        conn.commit()
        
        # Fetch and return the created trade
        trade_id = cursor.lastrowid
        return get_trade_by_id(trade_id)
    finally:
        conn.close()


def get_trade_by_id(trade_id: int) -> Dict[str, Any]:
    """Get a single trade by ID."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM manual_trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {}
    finally:
        conn.close()


def get_all_trades(
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get all manual trades with optional filters.
    
    Args:
        symbol: Filter by symbol (e.g., 'EURUSD')
        status: Filter by status ('open' or 'closed')
        start_date: Filter trades on or after this date (ISO 8601)
        end_date: Filter trades on or before this date (ISO 8601)
        limit: Maximum number of trades to return
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        query = "SELECT * FROM manual_trades WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND entry_time <= ?"
            params.append(end_date)
        
        query += " ORDER BY entry_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_trade(
    trade_id: int,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    entry_time: Optional[str] = None,
    exit_time: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Update an existing trade.
    
    Only provided fields will be updated. If exit_price is provided/updated,
    P&L and status will be recalculated.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # First, get the current trade
        current = get_trade_by_id(trade_id)
        if not current:
            return {}
        
        # Build update fields
        updates = []
        params = []
        
        if symbol is not None:
            updates.append("symbol = ?")
            params.append(symbol)
        
        if direction is not None:
            updates.append("direction = ?")
            params.append(direction)
        
        if entry_price is not None:
            updates.append("entry_price = ?")
            params.append(entry_price)
        
        if exit_price is not None:
            updates.append("exit_price = ?")
            params.append(exit_price)
        
        if entry_time is not None:
            updates.append("entry_time = ?")
            params.append(entry_time)
        
        if exit_time is not None:
            updates.append("exit_time = ?")
            params.append(exit_time)
        
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        
        # Always update timestamp
        updates.append("updated_at = ?")
        params.append(_now_iso())
        
        # Recalculate P&L if we have both entry and exit prices
        eff_entry = entry_price if entry_price is not None else current['entry_price']
        eff_exit = exit_price if exit_price is not None else current['exit_price']
        eff_direction = direction if direction is not None else current['direction']
        
        if eff_exit is not None:
            if eff_direction == "long":
                pnl = (eff_exit - eff_entry)
            else:
                pnl = (eff_entry - eff_exit)
            pnl_percent = (pnl / eff_entry) * 100 if eff_entry != 0 else 0.0
            updates.append("pnl = ?")
            params.append(pnl)
            updates.append("pnl_percent = ?")
            params.append(pnl_percent)
            updates.append("status = ?")
            params.append("closed")
        
        if not updates:
            return current
        
        query = f"UPDATE manual_trades SET {', '.join(updates)} WHERE id = ?"
        params.append(trade_id)
        
        cursor.execute(query, params)
        conn.commit()
        
        return get_trade_by_id(trade_id)
    finally:
        conn.close()


def delete_trade(trade_id: int) -> bool:
    """Delete a trade by ID. Returns True if deleted, False if not found."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM manual_trades WHERE id = ?", (trade_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_summary_stats() -> Dict[str, Any]:
    """Get summary statistics for all manual trades."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Total trades
        cursor.execute("SELECT COUNT(*) as count FROM manual_trades")
        total = cursor.fetchone()['count']
        
        # Closed trades
        cursor.execute("SELECT COUNT(*) as count FROM manual_trades WHERE status = 'closed'")
        closed = cursor.fetchone()['count']
        
        # Open trades
        cursor.execute("SELECT COUNT(*) as count FROM manual_trades WHERE status = 'open'")
        open_count = cursor.fetchone()['count']
        
        # Win/loss stats (closed trades only)
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN pnl >= 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                AVG(pnl_percent) as avg_pnl_percent
            FROM manual_trades 
            WHERE status = 'closed'
        """)
        row = cursor.fetchone()
        
        wins = row['wins'] or 0
        losses = row['losses'] or 0
        total_pnl = row['total_pnl'] or 0.0
        avg_pnl = row['avg_pnl'] or 0.0
        avg_pnl_percent = row['avg_pnl_percent'] or 0.0
        
        win_rate = (wins / closed * 100) if closed > 0 else 0.0
        
        return {
            "total_trades": total,
            "closed_trades": closed,
            "open_trades": open_count,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(avg_pnl, 2),
            "avg_pnl_percent": round(avg_pnl_percent, 2)
        }
    finally:
        conn.close()


# Initialize schema on module load
init_schema()

"""
TradeGumi Database Module

SQLite schema and ORM for AI-augmented trading infrastructure.
Enforces temporal firewall: all context captured at entry timestamp.

LEGACY / DORMANT: This is the last SQLite code in the project. The subsystem
(``TradeGumiDB`` + ``pattern_analyzer`` + ``context_snapshot`` + ``decision_engine``)
is scaffolding that is never instantiated at runtime, so its SQLite usage is
inert today. Postgres is the single source of truth (no SQLite fallback). Before
this subsystem is wired into any runtime path it MUST be migrated to the shared
``tradegumi.persistence`` Postgres backend — otherwise it reintroduces SQLite
writes and would fail in the read-only API container. Tracked in issue #115.
"""

import sqlite3
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path


@dataclass
class Trade:
    """Represents a completed or open trade."""
    id: Optional[int] = None
    signal_id: str = ""
    entry_timestamp: datetime = field(default_factory=datetime.utcnow)
    exit_timestamp: Optional[datetime] = None
    symbol: str = ""
    side: str = ""  # 'long' or 'short'
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    outcome: str = "open"  # 'win', 'loss', 'breakeven', 'open'
    pnl: float = 0.0
    r_multiple: float = 0.0


@dataclass
class EntryContext:
    """Frozen market context at trade entry."""
    id: Optional[int] = None
    signal_id: str = ""
    stochrsi: float = 0.0
    macd: float = 0.0
    macd_signal: float = 0.0
    atr: float = 0.0
    keltner_upper: float = 0.0
    keltner_lower: float = 0.0
    price: float = 0.0
    session: str = ""  # 'am', 'pm', 'overnight'
    spread: float = 0.0
    news_sentiment_at_entry: float = 0.0  # FROZEN - never updated
    captured_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExitContext:
    """Post-hoc exit context for analysis only."""
    id: Optional[int] = None
    signal_id: str = ""
    exit_trigger: str = ""
    news_sentiment_at_exit: float = 0.0  # For analysis only
    recorded_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PatternPerformance:
    """Aggregated performance metrics for a pattern hash."""
    pattern_hash: str = ""
    description: str = ""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    expectancy: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)


class TradeGumiDB:
    """Database manager with temporal firewall enforcement."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._init_schema()

    def _connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def _init_schema(self):
        """Initialize database schema if not exists."""
        cursor = self.conn.cursor()

        # Check if schema exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trades'
        """)
        if cursor.fetchone():
            return  # Schema already exists

        # Create trades table
        cursor.execute("""
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT UNIQUE NOT NULL,
                entry_timestamp TEXT NOT NULL,
                exit_timestamp TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                outcome TEXT DEFAULT 'open',
                pnl REAL DEFAULT 0.0,
                r_multiple REAL DEFAULT 0.0
            )
        """)

        # Create entry_context table (frozen at entry)
        cursor.execute("""
            CREATE TABLE entry_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT NOT NULL,
                stochrsi REAL NOT NULL,
                macd REAL NOT NULL,
                macd_signal REAL NOT NULL,
                atr REAL NOT NULL,
                keltner_upper REAL NOT NULL,
                keltner_lower REAL NOT NULL,
                price REAL NOT NULL,
                session TEXT NOT NULL,
                spread REAL NOT NULL,
                news_sentiment_at_entry REAL NOT NULL,
                captured_at TEXT NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES trades(signal_id)
            )
        """)

        # Create exit_context table (post-hoc analysis)
        cursor.execute("""
            CREATE TABLE exit_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT NOT NULL,
                exit_trigger TEXT NOT NULL,
                news_sentiment_at_exit REAL NOT NULL,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES trades(signal_id)
            )
        """)

        # Create pattern_performance table
        cursor.execute("""
            CREATE TABLE pattern_performance (
                pattern_hash TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                expectancy REAL DEFAULT 0.0,
                last_updated TEXT NOT NULL
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX idx_trades_signal ON trades(signal_id)")
        cursor.execute("CREATE INDEX idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX idx_entry_context_signal ON entry_context(signal_id)")
        cursor.execute("CREATE INDEX idx_exit_context_signal ON exit_context(signal_id)")

        self.conn.commit()

    def insert_trade(self, trade: Trade) -> int:
        """Insert a new trade record."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO trades 
            (signal_id, entry_timestamp, exit_timestamp, symbol, side, 
             entry_price, exit_price, outcome, pnl, r_multiple)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.signal_id,
            trade.entry_timestamp.isoformat(),
            trade.exit_timestamp.isoformat() if trade.exit_timestamp else None,
            trade.symbol,
            trade.side,
            trade.entry_price,
            trade.exit_price,
            trade.outcome,
            trade.pnl,
            trade.r_multiple
        ))
        self.conn.commit()
        return cursor.lastrowid

    def insert_entry_context(self, context: EntryContext) -> int:
        """
        Insert frozen entry context.
        
        TEMPORAL FIREWALL: This data is immutable after insertion.
        news_sentiment_at_entry is frozen and never updated.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO entry_context 
            (signal_id, stochrsi, macd, macd_signal, atr, 
             keltner_upper, keltner_lower, price, session, spread,
             news_sentiment_at_entry, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            context.signal_id,
            context.stochrsi,
            context.macd,
            context.macd_signal,
            context.atr,
            context.keltner_upper,
            context.keltner_lower,
            context.price,
            context.session,
            context.spread,
            context.news_sentiment_at_entry,
            context.captured_at.isoformat()
        ))
        self.conn.commit()
        return cursor.lastrowid

    def insert_exit_context(self, context: ExitContext) -> int:
        """
        Insert exit context for post-hoc analysis.
        
        Note: news_sentiment_at_exit is for analysis only and does not
        affect the frozen entry context.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO exit_context 
            (signal_id, exit_trigger, news_sentiment_at_exit, recorded_at)
            VALUES (?, ?, ?, ?)
        """, (
            context.signal_id,
            context.exit_trigger,
            context.news_sentiment_at_exit,
            context.recorded_at.isoformat()
        ))
        self.conn.commit()
        return cursor.lastrowid

    def update_trade_exit(self, signal_id: str, exit_timestamp: datetime,
                          exit_price: float, outcome: str, 
                          pnl: float, r_multiple: float):
        """Update trade with exit information."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE trades 
            SET exit_timestamp = ?, exit_price = ?, outcome = ?, 
                pnl = ?, r_multiple = ?
            WHERE signal_id = ?
        """, (
            exit_timestamp.isoformat(),
            exit_price,
            outcome,
            pnl,
            r_multiple,
            signal_id
        ))
        self.conn.commit()

    def get_pattern_performance(self, pattern_hash: str) -> Optional[PatternPerformance]:
        """
        Retrieve pattern performance by hash.
        
        Query: SELECT * FROM pattern_performance WHERE pattern_hash = ?
        Returns: win_rate, expectancy, trade count
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM pattern_performance 
            WHERE pattern_hash = ?
        """, (pattern_hash,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return PatternPerformance(
            pattern_hash=row['pattern_hash'],
            description=row['description'],
            total_trades=row['total_trades'],
            wins=row['wins'],
            losses=row['losses'],
            win_rate=row['win_rate'],
            expectancy=row['expectancy'],
            last_updated=datetime.fromisoformat(row['last_updated'])
        )

    def upsert_pattern_performance(self, pattern: PatternPerformance):
        """Insert or update pattern performance statistics."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO pattern_performance 
            (pattern_hash, description, total_trades, wins, losses,
             win_rate, expectancy, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern.pattern_hash,
            pattern.description,
            pattern.total_trades,
            pattern.wins,
            pattern.losses,
            pattern.win_rate,
            pattern.expectancy,
            datetime.utcnow().isoformat()
        ))
        self.conn.commit()

    def get_entry_context(self, signal_id: str) -> Optional[EntryContext]:
        """Retrieve frozen entry context by signal ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM entry_context WHERE signal_id = ?
        """, (signal_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return EntryContext(
            id=row['id'],
            signal_id=row['signal_id'],
            stochrsi=row['stochrsi'],
            macd=row['macd'],
            macd_signal=row['macd_signal'],
            atr=row['atr'],
            keltner_upper=row['keltner_upper'],
            keltner_lower=row['keltner_lower'],
            price=row['price'],
            session=row['session'],
            spread=row['spread'],
            news_sentiment_at_entry=row['news_sentiment_at_entry'],
            captured_at=datetime.fromisoformat(row['captured_at'])
        )

    def get_trade(self, signal_id: str) -> Optional[Trade]:
        """Retrieve trade by signal ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trades WHERE signal_id = ?
        """, (signal_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return Trade(
            id=row['id'],
            signal_id=row['signal_id'],
            entry_timestamp=datetime.fromisoformat(row['entry_timestamp']),
            exit_timestamp=datetime.fromisoformat(row['exit_timestamp']) if row['exit_timestamp'] else None,
            symbol=row['symbol'],
            side=row['side'],
            entry_price=row['entry_price'],
            exit_price=row['exit_price'],
            outcome=row['outcome'],
            pnl=row['pnl'],
            r_multiple=row['r_multiple']
        )

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

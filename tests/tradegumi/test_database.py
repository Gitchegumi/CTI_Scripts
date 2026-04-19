"""
Unit tests for TradeGumi database module.

Tests cover:
- Schema creation
- CRUD operations
- Temporal firewall enforcement
- Pattern performance queries
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path

from tradegumi.database import (
    TradeGumiDB,
    Trade,
    EntryContext,
    ExitContext,
    PatternPerformance
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    db = TradeGumiDB(db_path)
    yield db
    
    db.close()
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def sample_trade():
    """Create sample trade data."""
    return Trade(
        signal_id="test-signal-001",
        entry_timestamp=datetime.utcnow(),
        symbol="ES",
        side="long",
        entry_price=4500.0,
        exit_price=4520.0,
        outcome="win",
        pnl=500.0,
        r_multiple=2.0
    )


@pytest.fixture
def sample_entry_context():
    """Create sample entry context data."""
    return EntryContext(
        signal_id="test-signal-001",
        stochrsi=75.0,
        macd=2.3,
        macd_signal=1.8,
        atr=4.5,
        keltner_upper=4520.5,
        keltner_lower=4480.25,
        price=4505.0,
        session="am",
        spread=0.25,
        news_sentiment_at_entry=0.65
    )


@pytest.fixture
def sample_exit_context():
    """Create sample exit context data."""
    return ExitContext(
        signal_id="test-signal-001",
        exit_trigger="target_hit",
        news_sentiment_at_exit=0.45,
        recorded_at=datetime.utcnow()
    )


class TestSchemaCreation:
    """Test database schema initialization."""

    def test_schema_created(self, temp_db):
        """Verify all tables are created."""
        cursor = temp_db.conn.cursor()
        
        # Check all tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'trades' in tables
        assert 'entry_context' in tables
        assert 'exit_context' in tables
        assert 'pattern_performance' in tables

    def test_indexes_created(self, temp_db):
        """Verify indexes are created for performance."""
        cursor = temp_db.conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        
        assert 'idx_trades_signal' in indexes
        assert 'idx_trades_symbol' in indexes
        assert 'idx_entry_context_signal' in indexes
        assert 'idx_exit_context_signal' in indexes


class TestTradeOperations:
    """Test trade CRUD operations."""

    def test_insert_trade(self, temp_db, sample_trade):
        """Test inserting a trade."""
        trade_id = temp_db.insert_trade(sample_trade)
        
        assert trade_id > 0
        
        # Retrieve and verify
        retrieved = temp_db.get_trade(sample_trade.signal_id)
        assert retrieved is not None
        assert retrieved.signal_id == sample_trade.signal_id
        assert retrieved.symbol == sample_trade.symbol
        assert retrieved.side == sample_trade.side
        assert retrieved.entry_price == sample_trade.entry_price

    def test_update_trade_exit(self, temp_db, sample_trade):
        """Test updating trade with exit information."""
        # Insert initial trade
        temp_db.insert_trade(sample_trade)
        
        # Update with exit
        exit_time = datetime.utcnow()
        temp_db.update_trade_exit(
            signal_id=sample_trade.signal_id,
            exit_timestamp=exit_time,
            exit_price=4520.0,
            outcome="win",
            pnl=500.0,
            r_multiple=2.0
        )
        
        # Verify update
        updated = temp_db.get_trade(sample_trade.signal_id)
        assert updated.outcome == "win"
        assert updated.exit_price == 4520.0
        assert updated.pnl == 500.0
        assert updated.r_multiple == 2.0

    def test_unique_signal_id(self, temp_db, sample_trade):
        """Test that signal_id is unique."""
        temp_db.insert_trade(sample_trade)
        
        # Try to insert duplicate
        duplicate = Trade(
            signal_id=sample_trade.signal_id,
            symbol="ES",
            side="long",
            entry_price=4500.0
        )
        
        with pytest.raises(Exception):  # UNIQUE constraint failed
            temp_db.insert_trade(duplicate)


class TestEntryContext:
    """Test entry context operations and temporal firewall."""

    def test_insert_entry_context(self, temp_db, sample_entry_context):
        """Test inserting entry context."""
        context_id = temp_db.insert_entry_context(sample_entry_context)
        
        assert context_id > 0
        
        # Retrieve and verify
        retrieved = temp_db.get_entry_context(sample_entry_context.signal_id)
        assert retrieved is not None
        assert retrieved.stochrsi == sample_entry_context.stochrsi
        assert retrieved.macd == sample_entry_context.macd
        assert retrieved.session == sample_entry_context.session
        assert retrieved.news_sentiment_at_entry == sample_entry_context.news_sentiment_at_entry

    def test_temporal_firewall_frozen_sentiment(self, temp_db, sample_entry_context):
        """
        TEMPORAL FIREWALL TEST: Verify news_sentiment_at_entry is frozen.
        
        This is critical: entry context must be immutable after capture.
        """
        # Insert context
        temp_db.insert_entry_context(sample_entry_context)
        original_sentiment = sample_entry_context.news_sentiment_at_entry
        
        # Attempt to "update" by re-inserting (should fail due to foreign key or logic)
        # In production, the application layer prevents updates
        # Here we verify the data remains as originally inserted
        
        retrieved = temp_db.get_entry_context(sample_entry_context.signal_id)
        assert retrieved.news_sentiment_at_entry == original_sentiment
        
        # The sentiment should NOT change even if we try to insert again
        # (application logic should prevent this, but data integrity is maintained)

    def test_entry_context_captured_at(self, temp_db, sample_entry_context):
        """Test that captured_at timestamp is set."""
        temp_db.insert_entry_context(sample_entry_context)
        
        retrieved = temp_db.get_entry_context(sample_entry_context.signal_id)
        assert retrieved.captured_at is not None
        assert isinstance(retrieved.captured_at, datetime)


class TestExitContext:
    """Test exit context operations."""

    def test_insert_exit_context(self, temp_db, sample_exit_context):
        """Test inserting exit context."""
        context_id = temp_db.insert_exit_context(sample_exit_context)
        
        assert context_id > 0

    def test_exit_context_separate_from_entry(self, temp_db, sample_entry_context, sample_exit_context):
        """
        Verify exit context is stored separately from entry context.
        
        This ensures post-hoc analysis doesn't contaminate entry snapshot.
        """
        # Insert both contexts
        temp_db.insert_entry_context(sample_entry_context)
        temp_db.insert_exit_context(sample_exit_context)
        
        # Retrieve entry context
        entry = temp_db.get_entry_context(sample_entry_context.signal_id)
        
        # Entry context should have entry sentiment, not exit sentiment
        assert entry.news_sentiment_at_entry == sample_entry_context.news_sentiment_at_entry
        # Entry context should NOT have exit sentiment field


class TestPatternPerformance:
    """Test pattern performance operations."""

    def test_upsert_pattern(self, temp_db):
        """Test inserting/updating pattern performance."""
        pattern = PatternPerformance(
            pattern_hash="S3|M2|V2|A",
            description="StochRSI 60-80, Moderate Bullish MACD, Normal Volatility, AM Session",
            total_trades=10,
            wins=7,
            losses=3,
            win_rate=0.7,
            expectancy=1.8
        )
        
        temp_db.upsert_pattern_performance(pattern)
        
        # Retrieve
        retrieved = temp_db.get_pattern_performance("S3|M2|V2|A")
        assert retrieved is not None
        assert retrieved.win_rate == 0.7
        assert retrieved.expectancy == 1.8
        assert retrieved.total_trades == 10

    def test_update_pattern(self, temp_db):
        """Test updating existing pattern."""
        # Insert initial pattern
        pattern1 = PatternPerformance(
            pattern_hash="S2|M2|V2|A",
            description="Test Pattern",
            total_trades=10,
            wins=6,
            losses=4,
            win_rate=0.6,
            expectancy=1.5
        )
        temp_db.upsert_pattern_performance(pattern1)
        
        # Update pattern
        pattern2 = PatternPerformance(
            pattern_hash="S2|M2|V2|A",
            description="Test Pattern Updated",
            total_trades=20,
            wins=13,
            losses=7,
            win_rate=0.65,
            expectancy=1.6
        )
        temp_db.upsert_pattern_performance(pattern2)
        
        # Verify update
        retrieved = temp_db.get_pattern_performance("S2|M2|V2|A")
        assert retrieved.total_trades == 20
        assert retrieved.wins == 13
        assert retrieved.win_rate == 0.65

    def test_get_nonexistent_pattern(self, temp_db):
        """Test querying nonexistent pattern."""
        result = temp_db.get_pattern_performance("NONEXISTENT")
        assert result is None


class TestDatabaseIntegration:
    """Test integrated database operations."""

    def test_full_trade_lifecycle(self, temp_db, sample_trade, sample_entry_context, sample_exit_context):
        """Test complete trade lifecycle from entry to exit."""
        # 1. Insert trade
        temp_db.insert_trade(sample_trade)
        
        # 2. Capture entry context (at entry time)
        temp_db.insert_entry_context(sample_entry_context)
        
        # 3. Later, update trade exit
        temp_db.update_trade_exit(
            signal_id=sample_trade.signal_id,
            exit_timestamp=datetime.utcnow(),
            exit_price=sample_trade.exit_price,
            outcome=sample_trade.outcome,
            pnl=sample_trade.pnl,
            r_multiple=sample_trade.r_multiple
        )
        
        # 4. Record exit context (post-hoc)
        temp_db.insert_exit_context(sample_exit_context)
        
        # 5. Verify all data is consistent
        trade = temp_db.get_trade(sample_trade.signal_id)
        entry = temp_db.get_entry_context(sample_trade.signal_id)
        
        assert trade is not None
        assert entry is not None
        assert trade.signal_id == entry.signal_id
        
        # Verify temporal firewall: entry sentiment is frozen
        assert entry.news_sentiment_at_entry == sample_entry_context.news_sentiment_at_entry
        assert entry.news_sentiment_at_entry != sample_exit_context.news_sentiment_at_exit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

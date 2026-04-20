"""
TradeGumi Context Snapshot

Captures frozen market context at trade entry.
Enforces temporal firewall: no data after entry timestamp.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .signal_processor import TradingSignal
from .database import EntryContext, TradeGumiDB


@dataclass
class MarketSnapshot:
    """Frozen snapshot of market conditions at entry."""
    signal_id: str
    captured_at: datetime
    
    # Indicator values (frozen)
    stochrsi: float
    macd: float
    macd_signal: float
    atr: float
    keltner_upper: float
    keltner_lower: float
    price: float
    
    # Market conditions (frozen)
    session: str
    spread: float
    
    # Sentiment (FROZEN at entry - never updated)
    news_sentiment_at_entry: float
    
    def to_entry_context(self) -> EntryContext:
        """Convert snapshot to database EntryContext."""
        return EntryContext(
            signal_id=self.signal_id,
            stochrsi=self.stochrsi,
            macd=self.macd,
            macd_signal=self.macd_signal,
            atr=self.atr,
            keltner_upper=self.keltner_upper,
            keltner_lower=self.keltner_lower,
            price=self.price,
            session=self.session,
            spread=self.spread,
            news_sentiment_at_entry=self.news_sentiment_at_entry,
            captured_at=self.captured_at
        )


class ContextSnapshot:
    """
    Captures and stores frozen market context at trade entry.
    
    TEMPORAL FIREWALL ENFORCEMENT:
    - All context is captured at entry timestamp
    - news_sentiment_at_entry is frozen and immutable
    - No queries allowed using data after entry
    - Exit context is stored separately for post-hoc analysis only
    """

    def __init__(self, db: TradeGumiDB, sentiment_provider=None):
        """
        Initialize context snapshot manager.
        
        Args:
            db: TradeGumiDB instance for storage
            sentiment_provider: Optional callable that returns current 
                               news sentiment score (-1.0 to 1.0)
        """
        self.db = db
        self.sentiment_provider = sentiment_provider
        self.snapshots_captured = 0

    def capture(self, signal: TradingSignal, 
                override_timestamp: Optional[datetime] = None) -> MarketSnapshot:
        """
        Capture frozen market context at entry.
        
        This is the CRITICAL temporal firewall boundary. All data captured
        here is immutable and represents the state at decision time.
        
        Args:
            signal: Validated TradingSignal
            override_timestamp: Optional timestamp override (for backtesting)
            
        Returns:
            MarketSnapshot with all frozen context
            
        Raises:
            ValueError: If signal_id already has captured context
        """
        # Check if context already exists (prevent duplicate captures)
        existing = self.db.get_entry_context(signal.signal_id)
        if existing:
            raise ValueError(
                f"Context already captured for signal {signal.signal_id}. "
                "Temporal firewall violation prevented."
            )
        
        # Capture timestamp
        captured_at = override_timestamp or datetime.utcnow()
        
        # Get news sentiment (FROZEN at entry)
        news_sentiment = 0.0
        if self.sentiment_provider:
            news_sentiment = self.sentiment_provider()
        
        # Create frozen snapshot
        snapshot = MarketSnapshot(
            signal_id=signal.signal_id,
            captured_at=captured_at,
            stochrsi=signal.stochrsi,
            macd=signal.macd,
            macd_signal=signal.macd_signal,
            atr=signal.atr,
            keltner_upper=signal.keltner_upper,
            keltner_lower=signal.keltner_lower,
            price=signal.price,
            session=signal.session,
            spread=signal.spread,
            news_sentiment_at_entry=news_sentiment
        )
        
        # Store in database (immutable after this point)
        entry_context = snapshot.to_entry_context()
        self.db.insert_entry_context(entry_context)
        
        self.snapshots_captured += 1
        
        return snapshot

    def get_context(self, signal_id: str) -> Optional[MarketSnapshot]:
        """
        Retrieve previously captured context.
        
        Args:
            signal_id: Signal identifier
            
        Returns:
            MarketSnapshot if found, None otherwise
        """
        entry_context = self.db.get_entry_context(signal_id)
        if not entry_context:
            return None
        
        return MarketSnapshot(
            signal_id=entry_context.signal_id,
            captured_at=entry_context.captured_at,
            stochrsi=entry_context.stochrsi,
            macd=entry_context.macd,
            macd_signal=entry_context.macd_signal,
            atr=entry_context.atr,
            keltner_upper=entry_context.keltner_upper,
            keltner_lower=entry_context.keltner_lower,
            price=entry_context.price,
            session=entry_context.session,
            spread=entry_context.spread,
            news_sentiment_at_entry=entry_context.news_sentiment_at_entry
        )

    def set_sentiment_provider(self, provider):
        """
        Set news sentiment provider.
        
        Args:
            provider: Callable that returns sentiment score (-1.0 to 1.0)
        """
        self.sentiment_provider = provider

    def clear_sentiment_provider(self):
        """Remove sentiment provider."""
        self.sentiment_provider = None

    def get_stats(self) -> Dict[str, int]:
        """Get snapshot statistics."""
        return {
            'snapshots_captured': self.snapshots_captured
        }

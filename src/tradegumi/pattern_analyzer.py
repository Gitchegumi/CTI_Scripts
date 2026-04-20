"""
TradeGumi Pattern Analyzer

Historical pattern matching using normalized indicator buckets.
"""

import hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from .database import TradeGumiDB, PatternPerformance


@dataclass
class PatternMatch:
    """Result of pattern matching query."""
    pattern_hash: str
    description: str
    win_rate: float
    expectancy: float
    trade_count: int
    
    def is_valid(self, min_matches: int = 5) -> bool:
        """Check if pattern has sufficient historical data."""
        return self.trade_count >= min_matches


class PatternAnalyzer:
    """
    Matches current market conditions against historical patterns.
    
    Pattern Hash Algorithm:
    - Normalize indicators to buckets: 0-20, 20-40, 40-60, 60-80, 80-100
    - Create hash from bucketized indicator states
    - Format: stochrsi_bucket|macd_bucket|atr_bucket|session
    
    Query Pattern:
        SELECT * FROM pattern_performance WHERE pattern_hash = ?
    
    Returns:
        win_rate, expectancy, similar trade count
    """

    BUCKET_SIZE = 20  # 0-20, 20-40, 40-60, 60-80, 80-100

    def __init__(self, db: TradeGumiDB, min_pattern_matches: int = 5):
        """
        Initialize pattern analyzer.
        
        Args:
            db: TradeGumiDB instance
            min_pattern_matches: Minimum historical matches required
        """
        self.db = db
        self.min_pattern_matches = min_pattern_matches
        self.queries_executed = 0

    def _normalize_to_bucket(self, value: float, min_val: float = 0.0, 
                             max_val: float = 100.0) -> int:
        """
        Normalize value to bucket index (0-4).
        
        Args:
            value: Raw indicator value
            min_val: Minimum expected value
            max_val: Maximum expected value
            
        Returns:
            Bucket index (0-4)
        """
        # Clamp to range
        clamped = max(min_val, min(max_val, value))
        
        # Calculate bucket
        normalized = (clamped - min_val) / (max_val - min_val)
        bucket = int(normalized * (100 / self.BUCKET_SIZE))
        
        # Ensure bucket is in valid range
        return max(0, min(4, bucket))

    def _normalize_macd(self, macd: float, macd_signal: float) -> int:
        """
        Normalize MACD relationship to bucket.
        
        Uses MACD histogram (MACD - signal) for directional bias.
        """
        histogram = macd - macd_signal
        
        # Bucket based on histogram strength
        if histogram > 2.0:
            return 4  # Strong bullish
        elif histogram > 0.5:
            return 3  # Moderate bullish
        elif histogram > -0.5:
            return 2  # Neutral
        elif histogram > -2.0:
            return 1  # Moderate bearish
        else:
            return 0  # Strong bearish

    def _normalize_atr(self, atr: float, symbol: str = "ES") -> int:
        """
        Normalize ATR to volatility bucket.
        
        ATR ranges are symbol-specific. Default assumes ES futures.
        """
        # ES-specific ATR buckets (adjust per symbol)
        if symbol == "ES":
            if atr < 3.0:
                return 0  # Very low vol
            elif atr < 5.0:
                return 1  # Low vol
            elif atr < 8.0:
                return 2  # Normal vol
            elif atr < 12.0:
                return 3  # High vol
            else:
                return 4  # Very high vol
        
        # Generic fallback
        return self._normalize_to_bucket(atr, 0.0, 15.0)

    def compute_pattern_hash(self, stochrsi: float, macd: float, 
                            macd_signal: float, atr: float,
                            session: str, symbol: str = "ES") -> str:
        """
        Compute pattern hash from indicator values.
        
        Args:
            stochrsi: Stochastic RSI value (0-100)
            macd: MACD line value
            macd_signal: MACD signal line value
            atr: Average True Range
            session: Trading session ('am', 'pm', 'overnight')
            symbol: Instrument symbol for ATR normalization
            
        Returns:
            Pattern hash string
        """
        # Normalize each indicator to bucket
        stoch_bucket = self._normalize_to_bucket(stochrsi, 0.0, 100.0)
        macd_bucket = self._normalize_macd(macd, macd_signal)
        atr_bucket = self._normalize_atr(atr, symbol)
        
        # Session encoding
        session_map = {'am': 'A', 'pm': 'P', 'overnight': 'O'}
        session_code = session_map.get(session.lower(), 'U')  # U = unknown
        
        # Create hash components
        components = [
            f"S{stoch_bucket}",  # StochRSI
            f"M{macd_bucket}",   # MACD
            f"V{atr_bucket}",    # Volatility (ATR)
            session_code
        ]
        
        # Join into hash string
        pattern_hash = "|".join(components)
        
        return pattern_hash

    def describe_pattern(self, pattern_hash: str) -> str:
        """
        Generate human-readable pattern description.
        
        Args:
            pattern_hash: Pattern hash string
            
        Returns:
            Human-readable description
        """
        parts = pattern_hash.split("|")
        descriptions = []
        
        for part in parts:
            if part.startswith("S"):
                bucket = int(part[1:])
                ranges = ["0-20", "20-40", "40-60", "60-80", "80-100"]
                descriptions.append(f"StochRSI {ranges[bucket]}")
            elif part.startswith("M"):
                bucket = int(part[1:])
                labels = [
                    "Strong Bearish MACD",
                    "Moderate Bearish MACD",
                    "Neutral MACD",
                    "Moderate Bullish MACD",
                    "Strong Bullish MACD"
                ]
                descriptions.append(labels[bucket])
            elif part.startswith("V"):
                bucket = int(part[1:])
                labels = [
                    "Very Low Volatility",
                    "Low Volatility",
                    "Normal Volatility",
                    "High Volatility",
                    "Very High Volatility"
                ]
                descriptions.append(labels[bucket])
            elif part in ['A', 'P', 'O']:
                session_names = {'A': 'AM Session', 'P': 'PM Session', 'O': 'Overnight'}
                descriptions.append(session_names.get(part, 'Unknown Session'))
        
        return ", ".join(descriptions)

    def find_pattern(self, pattern_hash: str) -> Optional[PatternMatch]:
        """
        Find historical pattern performance.
        
        Query: SELECT * FROM pattern_performance WHERE pattern_hash = ?
        
        Args:
            pattern_hash: Pattern hash to search for
            
        Returns:
            PatternMatch if found, None otherwise
        """
        self.queries_executed += 1
        
        pattern_perf = self.db.get_pattern_performance(pattern_hash)
        if not pattern_perf:
            return None
        
        return PatternMatch(
            pattern_hash=pattern_perf.pattern_hash,
            description=pattern_perf.description,
            win_rate=pattern_perf.win_rate,
            expectancy=pattern_perf.expectancy,
            trade_count=pattern_perf.total_trades
        )

    def match_signal(self, stochrsi: float, macd: float, macd_signal: float,
                    atr: float, session: str, symbol: str = "ES") -> Optional[PatternMatch]:
        """
        Match signal indicators against historical patterns.
        
        Args:
            stochrsi: Stochastic RSI
            macd: MACD line
            macd_signal: MACD signal line
            atr: Average True Range
            session: Trading session
            symbol: Instrument symbol
            
        Returns:
            PatternMatch if found with sufficient data, None otherwise
        """
        # Compute pattern hash
        pattern_hash = self.compute_pattern_hash(
            stochrsi, macd, macd_signal, atr, session, symbol
        )
        
        # Find historical pattern
        match = self.find_pattern(pattern_hash)
        
        # Validate minimum matches
        if match and not match.is_valid(self.min_pattern_matches):
            return None  # Insufficient historical data
        
        return match

    def update_pattern_stats(self, pattern_hash: str, won: bool, 
                            r_multiple: float):
        """
        Update pattern performance after trade closes.
        
        Args:
            pattern_hash: Pattern hash
            won: Whether trade was a win
            r_multiple: R-multiple outcome
        """
        # Get existing stats
        existing = self.db.get_pattern_performance(pattern_hash)
        
        if existing:
            # Update existing pattern
            new_wins = existing.wins + (1 if won else 0)
            new_losses = existing.losses + (0 if won else 1)
            new_total = existing.total_trades + 1
            
            # Recalculate win rate
            new_win_rate = new_wins / new_total if new_total > 0 else 0.0
            
            # Update expectancy (simple moving average of R-multiples)
            total_expectancy = (existing.expectancy * existing.total_trades) + r_multiple
            new_expectancy = total_expectancy / new_total
            
            updated = PatternPerformance(
                pattern_hash=pattern_hash,
                description=existing.description,
                total_trades=new_total,
                wins=new_wins,
                losses=new_losses,
                win_rate=new_win_rate,
                expectancy=new_expectancy
            )
        else:
            # Create new pattern entry
            description = self.describe_pattern(pattern_hash)
            updated = PatternPerformance(
                pattern_hash=pattern_hash,
                description=description,
                total_trades=1,
                wins=1 if won else 0,
                losses=0 if won else 1,
                win_rate=1.0 if won else 0.0,
                expectancy=r_multiple
            )
        
        # Store updated stats
        self.db.upsert_pattern_performance(updated)

    def get_stats(self) -> Dict[str, int]:
        """Get analyzer statistics."""
        return {
            'queries_executed': self.queries_executed,
            'min_pattern_matches': self.min_pattern_matches
        }

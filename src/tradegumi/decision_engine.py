"""
TradeGumi Decision Engine

AI analysis and confidence scoring for trading signals.
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from .signal_processor import TradingSignal
from .context_snapshot import ContextSnapshot, MarketSnapshot
from .pattern_analyzer import PatternAnalyzer, PatternMatch


@dataclass
class HistoricalContext:
    """Historical pattern context for decision."""
    win_rate: float
    expectancy: float
    trade_count: int


@dataclass
class DecisionOutput:
    """AI decision output for a trading signal."""
    signal_id: str
    decision: str  # 'approve', 'reject', 'modify'
    confidence: float
    size_adjustment: float
    historical_context: HistoricalContext
    notes: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'signal_id': self.signal_id,
            'decision': self.decision,
            'confidence': round(self.confidence, 3),
            'size_adjustment': round(self.size_adjustment, 3),
            'historical_context': {
                'win_rate': round(self.historical_context.win_rate, 3),
                'expectancy': round(self.historical_context.expectancy, 2),
                'trade_count': self.historical_context.trade_count
            },
            'notes': self.notes
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class DecisionEngine:
    """
    AI analysis and confidence scoring for trading decisions.
    
    Decision Logic:
    - Confidence based on pattern match strength and sample size
    - size_adjustment scales position based on confidence
    - Reject if insufficient historical data (<5 similar trades)
    - Confidence capped at 0.95 without 50+ sample size
    """

    # Configuration
    MIN_PATTERN_MATCHES = 5
    HIGH_CONFIDENCE_THRESHOLD = 50
    MAX_CONFIDENCE_CAP = 0.95
    BASE_SIZE_ADJUSTMENT = 1.0

    def __init__(self, snapshot_manager: ContextSnapshot, 
                 pattern_analyzer: PatternAnalyzer):
        """
        Initialize decision engine.
        
        Args:
            snapshot_manager: ContextSnapshot instance
            pattern_analyzer: PatternAnalyzer instance
        """
        self.snapshot_manager = snapshot_manager
        self.pattern_analyzer = pattern_analyzer
        self.decisions_made = 0
        self.approvals = 0
        self.rejections = 0
        self.modifications = 0

    def _compute_confidence(self, pattern_match: PatternMatch) -> float:
        """
        Compute confidence score from pattern match.
        
        Factors:
        - Win rate stability (higher = more confident)
        - Sample size (more trades = more confident)
        - Expectancy magnitude (higher absolute = more confident)
        
        Args:
            pattern_match: PatternMatch from analyzer
            
        Returns:
            Confidence score (0.0-1.0)
        """
        # Base confidence from win rate
        base_confidence = pattern_match.win_rate
        
        # Sample size bonus
        trade_count = pattern_match.trade_count
        if trade_count >= self.HIGH_CONFIDENCE_THRESHOLD:
            sample_bonus = 0.15
        elif trade_count >= self.MIN_PATTERN_MATCHES:
            sample_bonus = 0.05 + (0.10 * (trade_count - self.MIN_PATTERN_MATCHES) / 
                                   (self.HIGH_CONFIDENCE_THRESHOLD - self.MIN_PATTERN_MATCHES))
        else:
            sample_bonus = 0.0
        
        # Expectancy bonus (for strong positive expectancy)
        expectancy_bonus = 0.0
        if pattern_match.expectancy > 1.5:
            expectancy_bonus = min(0.10, (pattern_match.expectancy - 1.5) * 0.05)
        
        # Calculate raw confidence
        raw_confidence = base_confidence + sample_bonus + expectancy_bonus
        
        # Apply cap for small sample sizes
        if trade_count < self.HIGH_CONFIDENCE_THRESHOLD:
            raw_confidence = min(raw_confidence, self.MAX_CONFIDENCE_CAP)
        
        # Clamp to valid range
        return max(0.0, min(1.0, raw_confidence))

    def _compute_size_adjustment(self, confidence: float) -> float:
        """
        Compute position size adjustment based on confidence.
        
        Higher confidence = larger position (up to 1.5x base size)
        Lower confidence = smaller position (down to 0.5x base size)
        
        Args:
            confidence: Confidence score (0.0-1.0)
            
        Returns:
            Size adjustment multiplier
        """
        # Linear scaling: 0.5x at 0.0 confidence, 1.5x at 1.0 confidence
        adjustment = 0.5 + (confidence * 1.0)
        
        # Clamp to reasonable bounds
        return max(0.5, min(1.5, adjustment))

    def _generate_notes(self, pattern_match: PatternMatch, 
                       confidence: float, decision: str) -> str:
        """
        Generate human-readable decision notes.
        
        Args:
            pattern_match: PatternMatch from analyzer
            confidence: Computed confidence score
            decision: Decision outcome
            
        Returns:
            Notes string
        """
        notes_parts = []
        
        if decision == 'reject':
            if pattern_match.trade_count < self.MIN_PATTERN_MATCHES:
                notes_parts.append(
                    f"Insufficient historical data ({pattern_match.trade_count} trades, "
                    f"need {self.MIN_PATTERN_MATCHES})"
                )
            else:
                notes_parts.append("Pattern does not meet approval criteria")
        else:
            # Approval or modification
            if pattern_match.win_rate >= 0.65:
                notes_parts.append("Strong historical win rate")
            elif pattern_match.win_rate >= 0.55:
                notes_parts.append("Moderate historical win rate")
            
            if pattern_match.expectancy >= 2.0:
                notes_parts.append("excellent expectancy")
            elif pattern_match.expectancy >= 1.5:
                notes_parts.append("favorable expectancy")
            
            if confidence >= 0.80:
                notes_parts.append("high confidence")
            elif confidence >= 0.65:
                notes_parts.append("moderate confidence")
            
            # Session context
            if pattern_match.trade_count >= self.HIGH_CONFIDENCE_THRESHOLD:
                notes_parts.append(f"robust sample size ({pattern_match.trade_count} trades)")
        
        return ". ".join(notes_parts).capitalize() + "."

    def analyze(self, signal: TradingSignal) -> DecisionOutput:
        """
        Analyze trading signal and produce decision.
        
        Workflow:
        1. Capture frozen context (temporal firewall)
        2. Match against historical patterns
        3. Compute confidence and size adjustment
        4. Generate decision
        
        Args:
            signal: Validated TradingSignal
            
        Returns:
            DecisionOutput with recommendation
        """
        # Step 1: Capture frozen context
        snapshot = self.snapshot_manager.capture(signal)
        
        # Step 2: Match historical patterns
        pattern_match = self.pattern_analyzer.match_signal(
            stochrsi=signal.stochrsi,
            macd=signal.macd,
            macd_signal=signal.macd_signal,
            atr=signal.atr,
            session=signal.session,
            symbol=signal.symbol
        )
        
        # Step 3: Determine decision
        if not pattern_match:
            # No pattern found or insufficient matches
            decision = 'reject'
            confidence = 0.0
            size_adjustment = 0.0
            
            historical_context = HistoricalContext(
                win_rate=0.0,
                expectancy=0.0,
                trade_count=0
            )
        else:
            # Pattern found
            confidence = self._compute_confidence(pattern_match)
            size_adjustment = self._compute_size_adjustment(confidence)
            
            # Determine approval threshold
            if confidence >= 0.60 and pattern_match.trade_count >= self.MIN_PATTERN_MATCHES:
                if confidence >= 0.85:
                    decision = 'approve'
                else:
                    decision = 'modify'  # Approve with reduced size
            else:
                decision = 'reject'
            
            historical_context = HistoricalContext(
                win_rate=pattern_match.win_rate,
                expectancy=pattern_match.expectancy,
                trade_count=pattern_match.trade_count
            )
        
        # Step 4: Generate notes
        notes = self._generate_notes(
            pattern_match if pattern_match else PatternMatch(
                pattern_hash="",
                description="",
                win_rate=0.0,
                expectancy=0.0,
                trade_count=0
            ),
            confidence,
            decision
        )
        
        # Create decision output
        output = DecisionOutput(
            signal_id=signal.signal_id,
            decision=decision,
            confidence=confidence,
            size_adjustment=size_adjustment,
            historical_context=historical_context,
            notes=notes
        )
        
        # Update statistics
        self.decisions_made += 1
        if decision == 'approve':
            self.approvals += 1
        elif decision == 'reject':
            self.rejections += 1
        else:
            self.modifications += 1
        
        return output

    def get_stats(self) -> Dict[str, Any]:
        """Get decision engine statistics."""
        return {
            'decisions_made': self.decisions_made,
            'approvals': self.approvals,
            'rejections': self.rejections,
            'modifications': self.modifications,
            'approval_rate': self.approvals / self.decisions_made if self.decisions_made > 0 else 0.0
        }

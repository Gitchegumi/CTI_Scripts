"""TradeGumi - AI-Augmented Trading Infrastructure."""

__version__ = "0.2.0"

from .database import (
    TradeGumiDB,
    Trade,
    EntryContext,
    ExitContext,
    PatternPerformance
)
from .signal_processor import TradingSignal, SignalProcessor
from .context_snapshot import ContextSnapshot, MarketSnapshot
from .pattern_analyzer import PatternAnalyzer, PatternMatch
from .decision_engine import DecisionEngine, DecisionOutput
from .messaging import MessageHandler, DiscordConfig, WebhookReceiver

__all__ = [
    # Database
    'TradeGumiDB',
    'Trade',
    'EntryContext',
    'ExitContext',
    'PatternPerformance',
    
    # Signal Processing
    'TradingSignal',
    'SignalProcessor',
    
    # Context Capture
    'ContextSnapshot',
    'MarketSnapshot',
    
    # Pattern Analysis
    'PatternAnalyzer',
    'PatternMatch',
    
    # Decision Engine
    'DecisionEngine',
    'DecisionOutput',
    
    # Messaging
    'MessageHandler',
    'DiscordConfig',
    'WebhookReceiver',
]
"""
TradeGumi Signal Processor

Handles intake and validation of inbound trading signals.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import uuid


def lifecycle_state_for_signal(signal: Any) -> Dict[str, Any]:
    """Return dashboard JSON lifecycle fields for an emitted signal object.

    The rolling `signals.json` file is intentionally lightweight, so this helper
    mirrors the lifecycle role and managed price fields without performing
    journal mutation or broker-specific work.
    """
    signal_type = str(getattr(signal, "signal_type", "pullback") or "pullback")
    if signal_type == "continuation":
        lifecycle_role = "management"
    elif signal_type in {"pullback", "high_value_pullback"}:
        lifecycle_role = "entry"
    else:
        lifecycle_role = "legacy_signal"
    return {
        "lifecycle_role": lifecycle_role,
        "current_stop_loss": getattr(signal, "stop_loss", None),
        "current_take_profit": getattr(signal, "take_profit", None),
        "entry_signal_type": None if lifecycle_role == "management" else signal_type,
        "source_signal_type": "continuation" if lifecycle_role == "management" else None,
    }


@dataclass
class TradingSignal:
    """Validated trading signal from alert system."""
    signal_id: str
    timestamp: datetime
    symbol: str
    side: str  # 'long' or 'short'
    stochrsi: float
    macd: float
    macd_signal: float
    atr: float
    keltner_upper: float
    keltner_lower: float
    price: float
    session: str  # 'am', 'pm', 'overnight'
    spread: float
    
    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> 'TradingSignal':
        """
        Parse and validate signal from JSON.
        
        Args:
            json_data: Raw signal JSON from webhook/alert
            
        Returns:
            Validated TradingSignal instance
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        required_fields = [
            'symbol', 'side', 'indicators', 'session'
        ]
        for field_name in required_fields:
            if field_name not in json_data:
                raise ValueError(f"Missing required field: {field_name}")
        
        # Validate side
        side = json_data['side'].lower()
        if side not in ('long', 'short'):
            raise ValueError(f"Invalid side: {json_data['side']}. Must be 'long' or 'short'")
        
        # Validate session
        session = json_data['session'].lower()
        if session not in ('am', 'pm', 'overnight'):
            raise ValueError(f"Invalid session: {json_data['session']}")
        
        # Extract indicators
        indicators = json_data.get('indicators', {})
        
        # Generate signal ID if not provided
        signal_id = json_data.get('signal_id', str(uuid.uuid4()))
        
        # Parse timestamp
        timestamp_str = json_data.get('timestamp', datetime.utcnow().isoformat())
        if isinstance(timestamp_str, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()
        
        return cls(
            signal_id=signal_id,
            timestamp=timestamp,
            symbol=json_data['symbol'],
            side=side,
            stochrsi=float(indicators.get('stochrsi', 0.0)),
            macd=float(indicators.get('macd', 0.0)),
            macd_signal=float(indicators.get('macd_signal', 0.0)),
            atr=float(indicators.get('atr', 0.0)),
            keltner_upper=float(indicators.get('keltner_upper', 0.0)),
            keltner_lower=float(indicators.get('keltner_lower', 0.0)),
            price=float(indicators.get('price', 0.0)),
            session=session,
            spread=float(json_data.get('spread', 0.0))
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary format."""
        return {
            'signal_id': self.signal_id,
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'side': self.side,
            'indicators': {
                'stochrsi': self.stochrsi,
                'macd': self.macd,
                'macd_signal': self.macd_signal,
                'atr': self.atr,
                'keltner_upper': self.keltner_upper,
                'keltner_lower': self.keltner_lower,
                'price': self.price
            },
            'session': self.session,
            'spread': self.spread
        }

    def to_json(self) -> str:
        """Convert signal to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class SignalProcessor:
    """
    Processes inbound trading signals.
    
    Responsibilities:
    - Parse and validate incoming signal JSON
    - Normalize indicator values
    - Route signals to context capture
    """

    def __init__(self):
        self.processed_count = 0
        self.error_count = 0

    def process(self, raw_json: str) -> TradingSignal:
        """
        Process raw JSON signal into validated TradingSignal.
        
        Args:
            raw_json: Raw JSON string from webhook/alert
            
        Returns:
            Validated TradingSignal instance
            
        Raises:
            ValueError: If JSON is invalid or signal fails validation
            json.JSONDecodeError: If JSON parsing fails
        """
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            self.error_count += 1
            raise ValueError(f"Invalid JSON: {e}")
        
        try:
            signal = TradingSignal.from_json(data)
            self.processed_count += 1
            return signal
        except (ValueError, KeyError) as e:
            self.error_count += 1
            raise ValueError(f"Signal validation failed: {e}")

    def process_dict(self, data: Dict[str, Any]) -> TradingSignal:
        """
        Process signal from dictionary (already parsed JSON).
        
        Args:
            data: Parsed JSON as dictionary
            
        Returns:
            Validated TradingSignal instance
        """
        signal = TradingSignal.from_json(data)
        self.processed_count += 1
        return signal

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return {
            'processed': self.processed_count,
            'errors': self.error_count
        }

    def reset_stats(self):
        """Reset processing statistics."""
        self.processed_count = 0
        self.error_count = 0

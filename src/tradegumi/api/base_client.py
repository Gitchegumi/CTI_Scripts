"""Abstract execution client interface.

Swap Oanda for MatchTrader without touching signal logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Candle:
    """OHLCV candle."""
    t: str          # ISO timestamp (Oanda returns strings)
    o: float
    h: float
    l: float
    c: float
    s: Optional[int] = None   # volume


@dataclass
class PriceTick:
    """Current bid/ask price for an instrument."""
    symbol: str
    bid: float
    ask: float
    spread: float      # ask - bid
    timestamp: str      # ISO timestamp


@dataclass
class Position:
    """Open position representation."""
    id: str
    symbol: str
    side: str       # "BUY" or "SELL"
    volume: float
    open_price: float
    current_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    unrealized_pl: float
    net_profit: float


@dataclass
class OrderRequest:
    """Order to be placed."""
    symbol: str
    side: str       # "BUY" or "SELL"
    volume: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class ExecutionClient(ABC):
    """Abstract interface for execution providers."""

    # ── Market Data ──────────────────────────────────────────────────────────

    @abstractmethod
    def get_candles(self, instrument: str, granularity: str, count: int):
        """Return list of Candle for instrument.

        Args:
            instrument: Generic symbol e.g. "EURUSD"
            granularity: Oanda-style "M5", "M15", "H1", etc.
            count: Number of candles to fetch

        Returns:
            list[Candle]
        """
        raise NotImplementedError

    @abstractmethod
    def get_pricing(self, instruments: list[str]) -> list[PriceTick]:
        """Get current bid/ask for multiple instruments in one call.

        Args:
            instruments: List of generic symbols e.g. ["EURUSD", "GBPJPY"]

        Returns:
            list[PriceTick]
        """
        raise NotImplementedError

    @abstractmethod
    def get_account_balance(self) -> float:
        """Return current account balance."""
        raise NotImplementedError

    @abstractmethod
    def get_open_positions(self) -> list[Position]:
        """Return current open positions."""
        raise NotImplementedError

    # ── Execution ───────────────────────────────────────────────────────────

    @abstractmethod
    def place_order(self, order: OrderRequest) -> str:
        """Place an order. Returns order/position id."""
        raise NotImplementedError

    @abstractmethod
    def close_position(self, position_id: str, units: Optional[float] = None):
        """Close a position (full or partial)."""
        raise NotImplementedError

    @abstractmethod
    def modify_sl_tp(self, position_id: str, stop_loss: Optional[float], take_profit: Optional[float]):
        """Update SL and TP on an open position."""
        raise NotImplementedError

    @abstractmethod
    def get_position(self, position_id: str) -> Position:
        """Fetch a single position by id."""
        raise NotImplementedError
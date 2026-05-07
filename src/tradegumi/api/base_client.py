"""Abstract execution client interface.

Swap Oanda for MatchTrader without touching signal logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
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
    complete: bool = True     # provider marks whether the candle is closed

    @property
    def time(self) -> datetime:
        """Return the candle timestamp as a timezone-aware datetime."""
        normalized = self.t[:-1] + "+00:00" if self.t.endswith("Z") else self.t
        parsed = datetime.fromisoformat(normalized)
        return parsed


class ProviderRequestError(RuntimeError):
    """Provider request failure with safe diagnostic context for signal metrics."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        method: str,
        path: str,
        operation: str,
        status_code: Optional[int] = None,
        instrument: Optional[str] = None,
        granularity: Optional[str] = None,
        attempts: int = 1,
        max_attempts: int = 1,
        retryable: bool = False,
        error_type: str = "provider_request_failed",
    ):
        super().__init__(message)
        self.provider = provider
        self.method = method
        self.path = path
        self.operation = operation
        self.status_code = status_code
        self.instrument = instrument
        self.granularity = granularity
        self.attempts = attempts
        self.max_attempts = max_attempts
        self.retryable = retryable
        self.error_type = error_type

    def to_diagnostic_context(self, *, stage: str) -> dict:
        """Return a non-secret diagnostic payload for metrics and logs."""
        return {
            "stage": stage,
            "provider": self.provider,
            "error_type": self.error_type,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "instrument": self.instrument,
            "granularity": self.granularity,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "retryable": self.retryable,
            "message": str(self),
        }


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
class TradeHistory:
    """Closed trade representation."""
    id: str
    symbol: str
    side: str           # "BUY" or "SELL"
    volume: float
    open_price: float
    close_price: float
    open_time: str      # ISO timestamp
    close_time: str     # ISO timestamp
    realized_pl: float
    financing: float
    pnl: float          # realized_pl + financing


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
    def get_trade_history(self, count: int = 50) -> list[TradeHistory]:
        """Return recent closed trades."""
        raise NotImplementedError

    @abstractmethod
    def modify_sl_tp(self, position_id: str, stop_loss: Optional[float], take_profit: Optional[float]):
        """Update SL and TP on an open position."""
        raise NotImplementedError

    @abstractmethod
    def get_position(self, position_id: str) -> Position:
        """Fetch a single position by id."""
        raise NotImplementedError

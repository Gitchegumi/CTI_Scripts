"""Shared live price observations for dashboard display and signal grading.

The module keeps a bounded in-memory history of broker-neutral price facts.
Publishers feed observations from supported market-data sources, while readers
and evaluators consume the same objects without triggering provider calls.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Iterable, Optional

DASHBOARD_POLL = "dashboard_poll"
OANDA_PRICING_STREAM = "oanda_pricing_stream"
HISTORICAL_CANDLE = "historical_candle"
MANUAL_BACKFILL = "manual_backfill"

SUPPORTED_SOURCES = {
    DASHBOARD_POLL,
    OANDA_PRICING_STREAM,
    HISTORICAL_CANDLE,
    MANUAL_BACKFILL,
}


def _now_utc() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


def parse_observation_time(value: Any, fallback: Optional[datetime] = None) -> datetime:
    """Parse an observation timestamp, falling back to a safe UTC datetime.

    Args:
        value: Provider timestamp, ISO string, datetime, or empty value.
        fallback: Optional fallback used when parsing fails.

    Returns:
        A timezone-aware datetime suitable for deterministic ordering.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if value not in (None, ""):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return fallback or _now_utc()


def _coerce_price(value: Any) -> Optional[float]:
    """Return a finite float price or None for missing/unusable values."""
    if value in (None, ""):
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price != price or price in (float("inf"), float("-inf")):
        return None
    return price


@dataclass(frozen=True)
class PriceObservation:
    """Provider-neutral price fact for one symbol at one point in time."""

    symbol: str
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    source: str = DASHBOARD_POLL
    observed_at: Optional[datetime] = None
    received_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Normalize symbol, source, timestamps, and derived midpoint."""
        symbol = str(self.symbol or "").strip().upper()
        if not symbol:
            raise ValueError("PriceObservation requires a symbol")
        source = self.source if self.source in SUPPORTED_SOURCES else str(self.source or DASHBOARD_POLL)
        timestamp = parse_observation_time(self.timestamp)
        observed_at = parse_observation_time(self.observed_at, timestamp) if self.observed_at else timestamp
        received_at = parse_observation_time(self.received_at) if self.received_at else _now_utc()
        bid = _coerce_price(self.bid)
        ask = _coerce_price(self.ask)
        mid = _coerce_price(self.mid)
        if mid is None and bid is not None and ask is not None:
            mid = (bid + ask) / 2
        if bid is None and ask is None and mid is None:
            raise ValueError("PriceObservation requires bid, ask, or mid")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "received_at", received_at)
        object.__setattr__(self, "bid", bid)
        object.__setattr__(self, "ask", ask)
        object.__setattr__(self, "mid", mid)

    @classmethod
    def from_tick(cls, tick: Any, *, source: str = DASHBOARD_POLL, received_at: Optional[datetime] = None) -> "PriceObservation":
        """Build an observation from an execution-client price tick."""
        return cls(
            symbol=getattr(tick, "symbol", ""),
            timestamp=getattr(tick, "timestamp", None),
            bid=getattr(tick, "bid", None),
            ask=getattr(tick, "ask", None),
            source=source,
            received_at=received_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the observation for API responses or diagnostics."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "source": self.source,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "received_at": self.received_at.isoformat() if self.received_at else None,
        }


class RollingPriceHistory:
    """Thread-safe bounded per-symbol price observation history."""

    def __init__(self, max_observations_per_symbol: int = 900, max_age_seconds: int = 900):
        """Create an in-memory history with count and age retention bounds."""
        self.max_observations_per_symbol = max(1, int(max_observations_per_symbol))
        self.max_age_seconds = max(1, int(max_age_seconds))
        self._observations: dict[str, deque[PriceObservation]] = defaultdict(deque)
        self._lock = Lock()

    def publish(self, observation: PriceObservation) -> PriceObservation:
        """Store one observation and prune bounded history for its symbol."""
        with self._lock:
            bucket = self._observations[observation.symbol]
            bucket.append(observation)
            self._prune_symbol(bucket, observation.received_at or _now_utc())
        return observation

    def publish_many(self, observations: Iterable[PriceObservation]) -> list[PriceObservation]:
        """Store many observations and return the accepted records."""
        accepted: list[PriceObservation] = []
        for observation in observations:
            accepted.append(self.publish(observation))
        return accepted

    def latest(self, symbol: str) -> Optional[PriceObservation]:
        """Return the newest retained observation for a symbol, if any."""
        key = str(symbol or "").strip().upper()
        with self._lock:
            bucket = self._observations.get(key)
            return bucket[-1] if bucket else None

    def recent(self, symbol: str, limit: Optional[int] = None) -> list[PriceObservation]:
        """Return recent observations for a symbol in oldest-to-newest order."""
        key = str(symbol or "").strip().upper()
        with self._lock:
            bucket = list(self._observations.get(key, ()))
        if limit is not None:
            return bucket[-max(0, int(limit)) :]
        return bucket

    def latest_many(self, symbols: Iterable[str]) -> dict[str, PriceObservation]:
        """Return latest observations for all requested symbols."""
        return {symbol.upper(): observation for symbol in symbols if (observation := self.latest(symbol))}

    def _prune_symbol(self, bucket: deque[PriceObservation], now: datetime) -> None:
        """Apply age and count bounds to one symbol bucket."""
        cutoff = now - timedelta(seconds=self.max_age_seconds)
        while bucket and len(bucket) > self.max_observations_per_symbol:
            bucket.popleft()
        while bucket and (bucket[0].received_at or bucket[0].timestamp) < cutoff:
            bucket.popleft()


DEFAULT_PRICE_HISTORY = RollingPriceHistory()


def publish_tick_observations(
    ticks: Iterable[Any],
    *,
    source: str = DASHBOARD_POLL,
    history: RollingPriceHistory = DEFAULT_PRICE_HISTORY,
) -> list[PriceObservation]:
    """Publish execution-client price ticks into the shared rolling history."""
    received_at = _now_utc()
    observations = [PriceObservation.from_tick(tick, source=source, received_at=received_at) for tick in ticks]
    return history.publish_many(observations)


def latest_observation(symbol: str, *, history: RollingPriceHistory = DEFAULT_PRICE_HISTORY) -> Optional[PriceObservation]:
    """Return the latest shared observation for one symbol."""
    return history.latest(symbol)

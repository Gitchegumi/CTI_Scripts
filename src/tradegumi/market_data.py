"""Provider-neutral market data lifecycle and Oanda streaming support."""

from __future__ import annotations

import json
import logging as log
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

import requests

from tradegumi import config
from tradegumi.api.base_client import ExecutionClient
from tradegumi.price_observations import (
    DASHBOARD_POLL,
    DEFAULT_PRICE_HISTORY,
    OANDA_PRICING_STREAM,
    PriceObservation,
    RollingPriceHistory,
    parse_observation_time,
)
from tradegumi.signal_outcomes import evaluate_price_observation

logger = log.getLogger(__name__)

MODE_STREAMING = "streaming"
MODE_POLLING = "polling"

STATUS_STOPPED = "stopped"
STATUS_STARTING = "starting"
STATUS_RUNNING = "running"
STATUS_RECONNECTING = "reconnecting"
STATUS_FALLBACK = "fallback"



class StreamEndedError(requests.ConnectionError):
    """Raised when a pricing stream ends cleanly (server close, not network error)."""
    pass


def _now_utc() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _seconds_since(value: Optional[datetime]) -> Optional[float]:
    """Return seconds since a timestamp or None when no timestamp exists."""
    if value is None:
        return None
    return max(0.0, (_now_utc() - value).total_seconds())


@dataclass(frozen=True)
class MarketDataSubscription:
    """Current provider subscription symbol set and generation."""

    symbols: tuple[str, ...] = ()
    generation: int = 0
    updated_at: datetime = field(default_factory=_now_utc)
    reason: str = "startup"

    @classmethod
    def from_symbols(
        cls,
        symbols: Iterable[str],
        *,
        generation: int = 0,
        reason: str = "startup",
    ) -> "MarketDataSubscription":
        """Create a stable subscription from CTI symbols."""
        normalized = tuple(sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}))
        return cls(symbols=normalized, generation=generation, reason=reason)


@dataclass
class MarketDataHealth:
    """Serializable market data provider health snapshot."""

    configured_mode: str = MODE_STREAMING
    active_mode: str = MODE_POLLING
    provider: str = "polling"
    status: str = STATUS_STOPPED
    active_symbol_count: int = 0
    observations: int = 0
    started_at: datetime = field(default_factory=_now_utc)
    last_observation_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    reconnect_count: int = 0
    fallback_active: bool = False
    last_error_type: Optional[str] = None
    last_error_at: Optional[datetime] = None

    def note_observation(self, observation: PriceObservation) -> None:
        """Record one accepted observation for health summaries."""
        self.observations += 1
        self.last_observation_at = observation.received_at or _now_utc()

    def note_heartbeat(self, heartbeat_at: Optional[datetime] = None) -> None:
        """Record one stream heartbeat without creating a price observation."""
        self.last_heartbeat_at = heartbeat_at or _now_utc()

    def note_error(self, error_type: str) -> None:
        """Record a safe provider error category."""
        self.last_error_type = error_type
        self.last_error_at = _now_utc()

    def observations_per_minute(self) -> float:
        """Return the average observation rate since provider start."""
        elapsed = max(1.0, (_now_utc() - self.started_at).total_seconds())
        return round(self.observations / elapsed * 60.0, 3)

    def to_dict(self) -> dict[str, Any]:
        """Serialize health for runtime API state."""
        return {
            "configured_mode": self.configured_mode,
            "active_mode": self.active_mode,
            "provider": self.provider,
            "status": self.status,
            "active_symbol_count": self.active_symbol_count,
            "observations_per_minute": self.observations_per_minute(),
            "last_observation_at": self.last_observation_at.isoformat() if self.last_observation_at else None,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None,
            "last_heartbeat_age_seconds": _seconds_since(self.last_heartbeat_at),
            "reconnect_count": self.reconnect_count,
            "fallback_active": self.fallback_active,
            "last_error_type": self.last_error_type,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
        }


class ObservationDispatcher:
    """Publish normalized observations to shared history and journal grading."""

    def __init__(
        self,
        *,
        history: RollingPriceHistory = DEFAULT_PRICE_HISTORY,
        evaluator: Callable[[PriceObservation], Any] = evaluate_price_observation,
    ) -> None:
        self.history = history
        self.evaluator = evaluator

    def publish(self, observation: PriceObservation) -> Any:
        """Store one observation and evaluate journal outcomes once."""
        stored = self.history.publish(observation)
        try:
            return self.evaluator(stored)
        except Exception as exc:
            logger.debug("Signal outcome evaluation failed for %s: %s", stored.symbol, exc)
            return None

    def publish_many(self, observations: Iterable[PriceObservation]) -> list[Any]:
        """Publish many observations through the same consumer path."""
        return [self.publish(observation) for observation in observations]

    def publish_ticks(self, ticks: Iterable[Any], *, source: str = DASHBOARD_POLL) -> list[PriceObservation]:
        """Convert execution-client ticks into observations and dispatch them."""
        received_at = _now_utc()
        observations = [
            PriceObservation.from_tick(tick, source=source, received_at=received_at)
            for tick in ticks
        ]
        self.publish_many(observations)
        return observations


def parse_oanda_stream_line(line: bytes | str) -> Optional[dict[str, Any]]:
    """Parse one Oanda streaming response line into an event dict."""
    text = line.decode("utf-8") if isinstance(line, bytes) else str(line)
    text = text.strip()
    if not text:
        return None
    try:
        event = json.loads(text)
    except json.JSONDecodeError:
        logger.debug("Malformed Oanda stream line ignored")
        return {"type": "MALFORMED"}
    if not isinstance(event, dict):
        return {"type": "MALFORMED"}
    return event


def oanda_price_event_to_observation(event: dict[str, Any]) -> Optional[PriceObservation]:
    """Convert one Oanda PRICE event into a normalized price observation."""
    if event.get("type") not in (None, "PRICE"):
        return None
    instrument = event.get("instrument")
    if not instrument:
        return None
    symbol = config.from_oanda_symbol(str(instrument))
    bids = event.get("bids") or []
    asks = event.get("asks") or []
    bid = bids[0].get("price") if bids and isinstance(bids[0], dict) else None
    ask = asks[0].get("price") if asks and isinstance(asks[0], dict) else None
    try:
        return PriceObservation(
            symbol=symbol,
            timestamp=parse_observation_time(event.get("time")),
            bid=bid,
            ask=ask,
            source=OANDA_PRICING_STREAM,
        )
    except ValueError:
        logger.debug("Oanda price event for %s did not include usable prices", instrument)
        return None


class PollingMarketDataProvider:
    """Provider wrapper for the existing REST pricing path."""

    name = "polling"
    mode = MODE_POLLING

    def __init__(
        self,
        client: ExecutionClient,
        dispatcher: ObservationDispatcher,
        *,
        configured_mode: str = MODE_POLLING,
    ) -> None:
        self.client = client
        self.dispatcher = dispatcher
        self.subscription = MarketDataSubscription()
        self.health = MarketDataHealth(
            configured_mode=configured_mode,
            active_mode=MODE_POLLING,
            provider=self.name,
            status=STATUS_STOPPED,
        )

    def start(self, symbols: Iterable[str]) -> None:
        """Begin polling against the supplied symbols."""
        self.resubscribe(symbols, reason="startup")
        self.health.status = STATUS_RUNNING

    def stop(self) -> None:
        """Stop polling; the main loop owns the actual cadence."""
        self.health.status = STATUS_STOPPED

    def resubscribe(self, symbols: Iterable[str], reason: str = "resubscribe") -> None:
        """Replace the symbol set used on the next poll."""
        self.subscription = MarketDataSubscription.from_symbols(
            symbols,
            generation=self.subscription.generation + 1,
            reason=reason,
        )
        self.health.active_symbol_count = len(self.subscription.symbols)

    def poll_once(self, symbols: Optional[Iterable[str]] = None) -> list[PriceObservation]:
        """Fetch one REST price batch and dispatch observations."""
        active_symbols = list(symbols if symbols is not None else self.subscription.symbols)
        if not active_symbols:
            return []
        ticks = self.client.get_pricing(active_symbols)
        observations = self.dispatcher.publish_ticks(ticks, source=DASHBOARD_POLL)
        for observation in observations:
            self.health.note_observation(observation)
        self.health.status = STATUS_RUNNING
        return observations

    def snapshot_health(self) -> dict[str, Any]:
        """Return a provider-neutral health payload."""
        return self.health.to_dict()


class OandaStreamingMarketDataProvider:
    """Oanda pricing stream provider that publishes normalized observations."""

    name = "oanda_stream"
    mode = MODE_STREAMING

    def __init__(
        self,
        client: Any,
        dispatcher: ObservationDispatcher,
        *,
        session_factory: Callable[[], requests.Session] = requests.Session,
        reconnect_seconds: float = 5.0,
        heartbeat_timeout_seconds: float = 15.0,
        backoff_max_seconds: float = 60.0,
        max_reconnect_attempts: int = 5,
        logger_: Any = logger,
    ) -> None:
        self.client = client
        self.dispatcher = dispatcher
        self.session_factory = session_factory
        self.reconnect_seconds = max(0.5, float(reconnect_seconds))
        self.heartbeat_timeout_seconds = max(1.0, float(heartbeat_timeout_seconds))
        self.backoff_max_seconds = max(self.reconnect_seconds, float(backoff_max_seconds))
        self.max_reconnect_attempts = max(1, int(max_reconnect_attempts))
        self.log = logger_
        self.subscription = MarketDataSubscription()
        self.health = MarketDataHealth(
            configured_mode=MODE_STREAMING,
            active_mode=MODE_STREAMING,
            provider=self.name,
            status=STATUS_STOPPED,
        )
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._session: Optional[requests.Session] = None
        self._last_connection_attempt = 0.0

    @property
    def fallback_active(self) -> bool:
        """Return whether polling fallback should currently be used."""
        return self.health.fallback_active

    def start(self, symbols: Iterable[str]) -> None:
        """Start one background stream worker for the supplied symbols."""
        with self._lock:
            self.subscription = MarketDataSubscription.from_symbols(symbols, generation=self.subscription.generation + 1)
            self.health.active_symbol_count = len(self.subscription.symbols)
            self.health.status = STATUS_STARTING
            self.health.fallback_active = False
            if not self._stop_worker_locked():
                self.health.note_error("stream_worker_stop_timeout")
                return
            if not self.subscription.symbols:
                self.health.status = STATUS_STOPPED
                return
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run, name="tradegumi-oanda-pricing-stream", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop active stream worker and close network resources."""
        with self._lock:
            self._stop_worker_locked()
            self.health.status = STATUS_STOPPED

    def resubscribe(self, symbols: Iterable[str], reason: str = "resubscribe") -> None:
        """Replace active stream subscription with the latest symbol set."""
        self.start(MarketDataSubscription.from_symbols(symbols, reason=reason).symbols)

    def snapshot_health(self) -> dict[str, Any]:
        """Return a provider-neutral health payload."""
        return self.health.to_dict()

    def _stop_worker_locked(self) -> bool:
        """Signal and join the current worker while holding the lifecycle lock."""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            if self._session is not None:
                self._session.close()
            self._thread.join(timeout=self.heartbeat_timeout_seconds + 2.0)
            if self._thread.is_alive():
                self.log.warning("Oanda pricing stream worker did not stop before replacement")
                return False
        self._thread = None
        self._session = None
        return True

    def _run(self) -> None:
        """Run the persistent stream with bounded reconnect/fallback behavior."""
        attempts = 0
        while not self._stop_event.is_set() and attempts < self.max_reconnect_attempts:
            attempts += 1
            self.health.reconnect_count = attempts - 1
            self.health.status = STATUS_RUNNING if attempts == 1 else STATUS_RECONNECTING
            self._respect_connection_limit()
            try:
                self._stream_once()
                attempts = 0
            except requests.HTTPError as exc:
                error_type = self._error_type_for_response(exc.response)
                self.health.note_error(error_type)
                if exc.response is not None and exc.response.status_code in (401, 403):
                    self.log.error("Oanda pricing stream authentication failed; activating polling fallback")
                    break
                self.log.warning("Oanda pricing stream HTTP failure: type=%s", error_type)
            except StreamEndedError:
                self.log.info("Oanda pricing stream ended cleanly")
                break
            except Exception as exc:
                self.health.note_error(exc.__class__.__name__)
                if not self._stop_event.is_set():
                    self.log.warning("Oanda pricing stream disconnected: %s", exc.__class__.__name__)
            if not self._stop_event.is_set():
                time.sleep(self._next_backoff(attempts))

        if not self._stop_event.is_set():
            self.health.status = STATUS_FALLBACK
            self.health.active_mode = MODE_POLLING
            self.health.fallback_active = True

    def _stream_once(self) -> None:
        """Open one Oanda streaming response and consume line events."""
        session = self.session_factory()
        self._session = session
        session.headers.update({
            "Authorization": f"Bearer {getattr(self.client, 'api_key', config.OANDA_API_KEY)}",
            "Accept-Datetime-Format": "RFC3339",
        })
        url = self._stream_url()
        response = session.get(
            url,
            params={"instruments": ",".join(config.to_oanda_symbol(symbol) for symbol in self.subscription.symbols)},
            stream=True,
            timeout=(10, self.heartbeat_timeout_seconds),
        )
        response.raise_for_status()
        self.health.status = STATUS_RUNNING
        self.health.active_mode = MODE_STREAMING
        self.health.fallback_active = False
        last_hb_time = time.monotonic()
        for line in response.iter_lines(decode_unicode=False):
            if self._stop_event.is_set():
                break
            event = parse_oanda_stream_line(line)
            obs = self.handle_event(event)
            now = time.monotonic()
            # Track per-line heartbeat timeout: update on any data event.
            if obs is not None or event.get("type") == "HEARTBEAT":
                last_hb_time = now
            if now - last_hb_time > self.heartbeat_timeout_seconds:
                raise requests.ConnectionError("Heartbeat timeout")
        if not self._stop_event.is_set():
            raise StreamEndedError("Oanda pricing stream ended")

    def handle_event(self, event: Optional[dict[str, Any]]) -> Optional[PriceObservation]:
        """Handle one parsed Oanda stream event for tests and the stream loop."""
        if not event:
            return None
        event_type = event.get("type")
        if event_type == "HEARTBEAT":
            self.health.note_heartbeat(parse_observation_time(event.get("time")))
            return None
        if event_type == "MALFORMED":
            self.health.note_error("malformed_stream_line")
            return None
        observation = oanda_price_event_to_observation(event)
        if observation is None:
            self.log.debug("Ignoring unsupported Oanda stream event type=%s", event_type)
            return None
        if observation.symbol not in self.subscription.symbols:
            self.log.debug("Ignoring Oanda stream observation outside subscription: %s", observation.symbol)
            return None
        self.dispatcher.publish(observation)
        self.health.note_observation(observation)
        return observation

    def _stream_url(self) -> str:
        """Build the pricing stream URL from configured Oanda stream details."""
        base = getattr(self.client, "stream_url", config.OANDA_STREAM_URL).rstrip("/")
        account_id = getattr(self.client, "account_id", config.OANDA_ACCOUNT_ID)
        return f"{base}/v3/accounts/{account_id}/pricing/stream"

    def _next_backoff(self, attempts: int) -> float:
        """Return bounded reconnect backoff while preserving Oanda limits."""
        return min(self.backoff_max_seconds, max(self.reconnect_seconds, attempts * self.reconnect_seconds))

    def _respect_connection_limit(self) -> None:
        """Avoid more than two new stream connections per second."""
        elapsed = time.monotonic() - self._last_connection_attempt
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_connection_attempt = time.monotonic()

    def _error_type_for_response(self, response: Optional[requests.Response]) -> str:
        """Return a safe stream error category for logs and health."""
        status = response.status_code if response is not None else None
        if status in (401, 403):
            return "oanda_stream_auth_failed"
        if status == 429:
            return "oanda_stream_rate_limited"
        return "oanda_stream_http_failed"


def create_market_data_provider(client: Any, dispatcher: ObservationDispatcher) -> Any:
    """Create the configured market data provider for the current client."""
    mode = config.TRADEGUMI_MARKET_DATA_MODE
    if mode == MODE_STREAMING and hasattr(client, "stream_url"):
        return OandaStreamingMarketDataProvider(
            client,
            dispatcher,
            reconnect_seconds=config.TRADEGUMI_STREAM_RECONNECT_SECONDS,
            heartbeat_timeout_seconds=config.TRADEGUMI_STREAM_HEARTBEAT_TIMEOUT_SECONDS,
            backoff_max_seconds=config.TRADEGUMI_STREAM_BACKOFF_MAX_SECONDS,
            max_reconnect_attempts=config.TRADEGUMI_STREAM_MAX_RECONNECT_ATTEMPTS,
        )
    return PollingMarketDataProvider(client, dispatcher, configured_mode=mode)

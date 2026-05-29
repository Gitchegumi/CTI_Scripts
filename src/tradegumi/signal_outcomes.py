"""Auto-grade alert-only Signal Journal entries from price observations.

The evaluator consumes provider-neutral price observations and mutates only
Signal Journal outcome fields. It never calls broker clients, generates
signals, or executes trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Optional

from tradegumi import journal
from tradegumi.price_observations import DASHBOARD_POLL, PriceObservation

LIVE_OBSERVATION_SOURCE = "live_price_observation_1s"
LIVE_OBSERVATION_MID_SOURCE = "live_price_observation_1s_mid"
STREAM_SOURCE = "oanda_pricing_stream"
HISTORICAL_CANDLE_SOURCE = "historical_candle"
MANUAL_SOURCE = "manual"
SYSTEM_PRIME_FILTER_SOURCE = "system_prime_filter"

STATUS_PENDING = "pending"
STATUS_OPEN_SIMULATED = "open_simulated"
STATUS_CLOSED = "closed"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_INVALIDATED = "invalidated"
STATUS_EXPIRED = "expired"

OUTCOME_NONE = "none"
OUTCOME_TP = "tp"
OUTCOME_SL = "sl"
OUTCOME_AMBIGUOUS = "ambiguous"
OUTCOME_EXPIRED = "expired"
OUTCOME_MANUALLY_CLOSED = "manually_closed"
OUTCOME_INVALIDATED_BY_PRIME = "invalidated_by_prime"
OUTCOME_INVALIDATED_BY_SYSTEM = "invalidated_by_system"

GRADE_TP_HIT = "TP_HIT"
GRADE_SL_HIT = "SL_HIT"


@dataclass(frozen=True)
class OutcomeDecision:
    """Result of comparing one journal entry to one observation."""

    status: str
    outcome: str
    exit_price: Optional[float]
    outcome_source: str
    ambiguous_reason: Optional[str] = None

    @property
    def closes_signal(self) -> bool:
        """Return whether the decision resolves the signal."""
        return self.outcome in {OUTCOME_TP, OUTCOME_SL, OUTCOME_AMBIGUOUS}


@dataclass(frozen=True)
class OutcomeEvaluationSummary:
    """Compact summary of one observation-driven evaluator run."""

    evaluated_count: int
    updated: tuple[dict[str, Any], ...]


@dataclass
class _PendingJournalIndex:
    """Cached unresolved journal entries grouped by normalized symbol."""

    journal_path: Path
    signature: tuple[int, int]
    entries: list[dict[str, Any]]
    by_symbol: dict[str, list[dict[str, Any]]]


_pending_index: Optional[_PendingJournalIndex] = None
_pending_index_lock = RLock()


def reset_pending_index() -> None:
    """Clear the unresolved journal index after tests or external maintenance."""
    global _pending_index
    with _pending_index_lock:
        _pending_index = None


def _direction(value: Any) -> str:
    """Normalize direction values used by the journal and signal engine."""
    raw = str(value or "").strip().upper()
    if raw in {"BUY", "LONG", "UP", "UPTREND"}:
        return "BUY"
    if raw in {"SELL", "SHORT", "DOWN", "DOWNTREND"}:
        return "SELL"
    return raw


def _float(value: Any) -> Optional[float]:
    """Return a finite float or None for missing values."""
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _source_for_observation(observation: PriceObservation, used_mid: bool) -> str:
    """Map observation source labels to outcome-source labels."""
    if used_mid:
        if observation.source == DASHBOARD_POLL:
            return LIVE_OBSERVATION_MID_SOURCE
        return f"{observation.source}_mid"
    if observation.source == DASHBOARD_POLL:
        return LIVE_OBSERVATION_SOURCE
    if observation.source == STREAM_SOURCE:
        return STREAM_SOURCE
    if observation.source == HISTORICAL_CANDLE_SOURCE:
        return HISTORICAL_CANDLE_SOURCE
    return str(observation.source or LIVE_OBSERVATION_SOURCE)


def _entry_symbol(entry: dict[str, Any]) -> str:
    """Return the normalized symbol for a journal entry."""
    return str(entry.get("symbol") or "").strip().upper()


def _is_auto_grade_candidate(entry: dict[str, Any], symbol: str) -> bool:
    """Return whether a journal entry can be updated by auto-grading."""
    if _entry_symbol(entry) != symbol:
        return False
    if bool(entry.get("manually_overridden")) or bool(entry.get("manual_override_locked")):
        return False
    grade = str(entry.get("grade") or journal.PENDING_GRADE).upper()
    if grade != journal.PENDING_GRADE:
        return False
    trade_grade = str(entry.get("trade_grade") or journal.PENDING_GRADE).upper()
    if trade_grade != journal.PENDING_GRADE:
        return False
    status = str(entry.get("status") or STATUS_OPEN_SIMULATED).lower()
    return status in {STATUS_PENDING, STATUS_OPEN_SIMULATED, ""}


def _journal_signature() -> tuple[int, int]:
    """Return a cheap signature for detecting journal file changes."""
    try:
        stat = journal.JOURNAL_FILE.stat()
    except FileNotFoundError:
        return (0, 0)
    return (int(stat.st_mtime_ns), int(stat.st_size))


def _build_pending_index(
    path: Path,
    signature: tuple[int, int],
    entries: list[dict[str, Any]],
) -> _PendingJournalIndex:
    """Build an unresolved journal index from already-loaded entries."""
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        symbol = _entry_symbol(entry)
        if symbol and _is_auto_grade_candidate(entry, symbol):
            by_symbol.setdefault(symbol, []).append(entry)
    return _PendingJournalIndex(path, signature, entries, by_symbol)


def _load_pending_index() -> _PendingJournalIndex:
    """Load or reuse unresolved journal entries grouped by symbol."""
    global _pending_index
    with _pending_index_lock:
        path = journal.JOURNAL_FILE
        signature = _journal_signature()
        if (
            _pending_index is not None
            and _pending_index.journal_path == path
            and _pending_index.signature == signature
        ):
            return _pending_index

        entries = journal._read_entries_oldest_first()
        _pending_index = _build_pending_index(path, signature, entries)
        return _pending_index


def _refresh_pending_index(entries: list[dict[str, Any]]) -> None:
    """Refresh the in-memory index after this process rewrites the journal."""
    global _pending_index
    with _pending_index_lock:
        _pending_index = _build_pending_index(journal.JOURNAL_FILE, _journal_signature(), entries)


def evaluate_entry(entry: dict[str, Any], observation: PriceObservation) -> OutcomeDecision:
    """Evaluate one journal entry against one price observation.

    Args:
        entry: Signal Journal entry containing direction, stop, and target.
        observation: Shared price observation for the same symbol.

    Returns:
        Outcome decision that either leaves the signal open or resolves it.
    """
    direction = _direction(entry.get("direction"))
    stop_loss = _float(entry.get("stop_loss"))
    take_profit = _float(entry.get("take_profit"))
    if direction not in {"BUY", "SELL"} or stop_loss is None or take_profit is None:
        return OutcomeDecision(
            status=STATUS_AMBIGUOUS,
            outcome=OUTCOME_AMBIGUOUS,
            exit_price=None,
            outcome_source=_source_for_observation(observation, used_mid=False),
            ambiguous_reason="missing_direction_stop_or_target",
        )

    if direction == "BUY" and observation.bid is not None:
        hit_tp = observation.bid >= take_profit
        hit_sl = observation.bid <= stop_loss
        price = observation.bid
        source = _source_for_observation(observation, used_mid=False)
    elif direction == "SELL" and observation.ask is not None:
        hit_tp = observation.ask <= take_profit
        hit_sl = observation.ask >= stop_loss
        price = observation.ask
        source = _source_for_observation(observation, used_mid=False)
    elif observation.mid is not None:
        price = observation.mid
        hit_tp = price >= take_profit if direction == "BUY" else price <= take_profit
        hit_sl = price <= stop_loss if direction == "BUY" else price >= stop_loss
        source = _source_for_observation(observation, used_mid=True)
    else:
        return OutcomeDecision(STATUS_OPEN_SIMULATED, OUTCOME_NONE, None, _source_for_observation(observation, False))

    if hit_tp and hit_sl:
        return OutcomeDecision(
            status=STATUS_AMBIGUOUS,
            outcome=OUTCOME_AMBIGUOUS,
            exit_price=price,
            outcome_source=source,
            ambiguous_reason="tp_and_sl_hit_same_observation",
        )
    if hit_tp:
        return OutcomeDecision(STATUS_CLOSED, OUTCOME_TP, price, source)
    if hit_sl:
        return OutcomeDecision(STATUS_CLOSED, OUTCOME_SL, price, source)
    return OutcomeDecision(STATUS_OPEN_SIMULATED, OUTCOME_NONE, None, source)


def _excursions(entry: dict[str, Any], observation: PriceObservation) -> tuple[Optional[float], Optional[float]]:
    """Calculate favorable and adverse movement from entry price when possible."""
    entry_price = _float(entry.get("entry_price"))
    direction = _direction(entry.get("direction"))
    price = observation.bid if direction == "BUY" else observation.ask
    if price is None:
        price = observation.mid
    if entry_price is None or price is None:
        return None, None
    movement = price - entry_price if direction == "BUY" else entry_price - price
    return max(0.0, movement), max(0.0, -movement)


def _apply_decision(entry: dict[str, Any], decision: OutcomeDecision, observation: PriceObservation) -> Optional[dict[str, Any]]:
    """Apply a decision to a journal entry and return summary data if updated."""
    if not decision.closes_signal:
        return None

    checked_at = datetime.now().astimezone().isoformat()
    entry["outcome_checked_at"] = checked_at
    entry["status"] = decision.status
    entry["outcome"] = decision.outcome
    entry["outcome_source"] = decision.outcome_source
    entry["observations_to_outcome"] = int(entry.get("observations_to_outcome") or 0) + 1
    favorable, adverse = _excursions(entry, observation)
    if favorable is not None:
        entry["max_favorable_excursion"] = max(float(entry.get("max_favorable_excursion") or 0.0), favorable)
    if adverse is not None:
        entry["max_adverse_excursion"] = max(float(entry.get("max_adverse_excursion") or 0.0), adverse)
    if decision.ambiguous_reason:
        entry["ambiguous_reason"] = decision.ambiguous_reason

    entry["exit_time"] = observation.timestamp.isoformat()
    entry["exit_price"] = decision.exit_price
    if decision.outcome == OUTCOME_TP:
        entry["grade"] = GRADE_TP_HIT
        entry["trade_grade"] = GRADE_TP_HIT
        journal._deactivate_prime(entry, journal.PRIME_CLOSE_INFERRED_TP, entry["exit_time"], False)
    elif decision.outcome == OUTCOME_SL:
        entry["grade"] = GRADE_SL_HIT
        entry["trade_grade"] = GRADE_SL_HIT
        journal._deactivate_prime(entry, journal.PRIME_CLOSE_INFERRED_SL, entry["exit_time"], False)
    elif decision.outcome == OUTCOME_AMBIGUOUS:
        entry["trade_grade"] = journal.PENDING_GRADE
    entry["grade_timestamp"] = checked_at if decision.outcome in {OUTCOME_TP, OUTCOME_SL} else entry.get("grade_timestamp")
    return {
        "signal_id": entry.get("signal_id"),
        "status": entry.get("status"),
        "outcome": entry.get("outcome"),
        "outcome_source": entry.get("outcome_source"),
        "exit_price": entry.get("exit_price"),
    }


def evaluate_price_observation(observation: PriceObservation) -> OutcomeEvaluationSummary:
    """Evaluate unresolved same-symbol journal entries for one observation."""
    updated: list[dict[str, Any]] = []
    with journal._lock:
        index = _load_pending_index()
        entries_for_symbol = list(index.by_symbol.get(observation.symbol, ()))
        for entry in entries_for_symbol:
            decision = evaluate_entry(entry, observation)
            summary = _apply_decision(entry, decision, observation)
            if summary is not None:
                updated.append(summary)
        if updated:
            journal._write_entries(index.entries)
            _refresh_pending_index(index.entries)
    return OutcomeEvaluationSummary(evaluated_count=len(entries_for_symbol), updated=tuple(updated))

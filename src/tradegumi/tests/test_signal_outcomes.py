"""Tests for alert-only signal outcome auto-grading."""

import json

import pytest

from tradegumi import journal
from tradegumi.price_observations import MANUAL_BACKFILL, PriceObservation
from tradegumi.signal_outcomes import (
    LIVE_OBSERVATION_MID_SOURCE,
    LIVE_OBSERVATION_SOURCE,
    OUTCOME_AMBIGUOUS,
    OUTCOME_NONE,
    OUTCOME_SL,
    OUTCOME_TP,
    STATUS_AMBIGUOUS,
    STATUS_CLOSED,
    STATUS_OPEN_SIMULATED,
    evaluate_price_observation,
)


def write_entries(path, entries):
    """Write JSONL journal entries for evaluator tests."""
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")


@pytest.fixture
def journal_file(tmp_path, monkeypatch):
    """Redirect the Signal Journal to a temporary file."""
    path = tmp_path / "signal_journal.jsonl"
    monkeypatch.setattr(journal, "JOURNAL_FILE", path)
    return path


def base_entry(**overrides):
    """Return a minimal unresolved alert-only journal entry."""
    entry = {
        "signal_id": "sig-1",
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": 1.1000,
        "stop_loss": 1.0980,
        "take_profit": 1.1040,
        "signal_timestamp": "2026-05-27T12:00:00Z",
        "mode": "alert_only",
        "grade": "PENDING",
        "trade_grade": "PENDING",
        "status": "open_simulated",
        "outcome": "none",
    }
    entry.update(overrides)
    return entry


def observation(**overrides):
    """Return a default same-symbol live observation."""
    data = {
        "symbol": "EURUSD",
        "timestamp": "2026-05-27T12:00:05Z",
        "bid": 1.1005,
        "ask": 1.1007,
    }
    data.update(overrides)
    return PriceObservation(**data)


def only_entry():
    """Read the newest journal entry from the redirected journal."""
    return journal.read_journal()[0]


def test_long_tp_hit_closes_with_bid(journal_file):
    write_entries(journal_file, [base_entry()])

    summary = evaluate_price_observation(observation(bid=1.1041, ask=1.1043))
    entry = only_entry()

    assert summary.updated[0]["outcome"] == OUTCOME_TP
    assert entry["status"] == STATUS_CLOSED
    assert entry["outcome"] == OUTCOME_TP
    assert entry["grade"] == "TP_HIT"
    assert entry["exit_price"] == pytest.approx(1.1041)
    assert entry["outcome_source"] == LIVE_OBSERVATION_SOURCE


def test_long_sl_hit_closes_with_bid(journal_file):
    write_entries(journal_file, [base_entry()])

    evaluate_price_observation(observation(bid=1.0979, ask=1.0981))
    entry = only_entry()

    assert entry["status"] == STATUS_CLOSED
    assert entry["outcome"] == OUTCOME_SL
    assert entry["grade"] == "SL_HIT"
    assert entry["exit_price"] == pytest.approx(1.0979)


def test_short_tp_hit_closes_with_ask(journal_file):
    write_entries(journal_file, [base_entry(direction="SELL", stop_loss=1.1020, take_profit=1.0960)])

    evaluate_price_observation(observation(bid=1.0957, ask=1.0959))
    entry = only_entry()

    assert entry["status"] == STATUS_CLOSED
    assert entry["outcome"] == OUTCOME_TP
    assert entry["grade"] == "TP_HIT"
    assert entry["exit_price"] == pytest.approx(1.0959)


def test_short_sl_hit_closes_with_ask(journal_file):
    write_entries(journal_file, [base_entry(direction="SELL", stop_loss=1.1020, take_profit=1.0960)])

    evaluate_price_observation(observation(bid=1.1019, ask=1.1021))
    entry = only_entry()

    assert entry["status"] == STATUS_CLOSED
    assert entry["outcome"] == OUTCOME_SL
    assert entry["grade"] == "SL_HIT"
    assert entry["exit_price"] == pytest.approx(1.1021)


def test_no_hit_stays_open_and_updates_checked_time(journal_file):
    write_entries(journal_file, [base_entry()])

    summary = evaluate_price_observation(observation())
    entry = only_entry()

    assert summary.evaluated_count == 1
    assert summary.updated == ()
    assert entry["status"] == STATUS_OPEN_SIMULATED
    assert entry["outcome"] == OUTCOME_NONE
    assert entry["outcome_checked_at"]


def test_manual_override_is_not_overwritten(journal_file):
    write_entries(journal_file, [base_entry(manually_overridden=True, grade="TP_HIT", trade_grade="TP_HIT", outcome="tp")])

    summary = evaluate_price_observation(observation(bid=1.0970, ask=1.0972))
    entry = only_entry()

    assert summary.evaluated_count == 0
    assert entry["grade"] == "TP_HIT"
    assert entry["outcome"] == OUTCOME_TP


def test_midpoint_fallback_records_mid_source(journal_file):
    write_entries(journal_file, [base_entry()])

    evaluate_price_observation(observation(bid=None, ask=None, mid=1.1042))
    entry = only_entry()

    assert entry["outcome"] == OUTCOME_TP
    assert entry["outcome_source"] == LIVE_OBSERVATION_MID_SOURCE


def test_same_cycle_midpoint_ambiguous_records_reason(journal_file):
    write_entries(journal_file, [base_entry(stop_loss=1.1000, take_profit=1.1000)])

    evaluate_price_observation(observation(bid=None, ask=None, mid=1.1000, source=MANUAL_BACKFILL))
    entry = only_entry()

    assert entry["status"] == STATUS_AMBIGUOUS
    assert entry["outcome"] == OUTCOME_AMBIGUOUS
    assert entry["ambiguous_reason"] == "tp_and_sl_hit_same_observation"

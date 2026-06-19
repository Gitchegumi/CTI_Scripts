"""Tests for the second-row lifecycle-events drill-down (DB-free).

``get_lifecycle_events`` reads the Signal Journal via
``journal._read_entries_oldest_first`` under ``journal._lock``. These tests
monkeypatch that read with fixed entries so the metric filtering, ordering, and
field-shaping logic can be verified without a live Postgres backend.
"""

import os

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")

import pytest

from tradegumi import journal
from tradegumi.strategy_metrics import (
    LIFECYCLE_METRICS,
    _lifecycle_event_matches,
    get_lifecycle_events,
)


def _entries() -> list[dict]:
    return [
        {
            "signal_id": "prime-1",
            "symbol": "EURUSD",
            "created_at": "2026-06-11T10:00:00+00:00",
            "prime_suppressed_signal_count": 3,
            "prime_suppressed_same_direction_count": 1,
            "prime_suppressed_opposite_direction_count": 2,
            "prime_suppressed_signal_outcomes": [{"outcome": "invalidated_by_prime"}],
        },
        {
            "signal_id": "entry-1",
            "symbol": "EURUSD",
            "direction": "BUY",
            "strategy": "CTI-v1",
            "signal_type": "pullback",
            "lifecycle_role": "entry",
            "created_at": "2026-06-11T10:05:00+00:00",
            "final_decision": "emitted",
            "tp_extension_count": 1,
            "sl_tighten_count": 2,
            "break_even_move_count": 1,
            "captured_r": 1.5,
        },
        {
            "signal_id": "mgmt-accepted",
            "symbol": "EURUSD",
            "signal_type": "continuation",
            "lifecycle_role": "management",
            "created_at": "2026-06-11T10:10:00+00:00",
            "management_accepted": True,
            "old_stop_loss": 1.10,
            "new_stop_loss": 1.11,
        },
        {
            "signal_id": "mgmt-rejected",
            "symbol": "EURUSD",
            "signal_type": "continuation",
            "lifecycle_role": "management",
            "created_at": "2026-06-11T10:15:00+00:00",
            "management_accepted": False,
            "management_rejection_reason": "opposite_direction",
        },
        {
            "signal_id": "warn-1",
            "symbol": "GBPJPY",
            "signal_type": "continuation",
            "lifecycle_role": "warning",
            "created_at": "2026-06-11T10:20:00+00:00",
            "management_accepted": False,
        },
        {
            "signal_id": "outcome-1",
            "symbol": "EURUSD",
            "lifecycle_role": "outcome",
            "created_at": "2026-06-11T10:25:00+00:00",
            "captured_r": 0.5,
            "managed_result_delta": "improved",
        },
        {
            # Out of the queried range — must be excluded everywhere.
            "signal_id": "entry-old",
            "symbol": "EURUSD",
            "lifecycle_role": "entry",
            "created_at": "2026-01-01T10:00:00+00:00",
        },
    ]


@pytest.fixture
def journaled(monkeypatch):
    monkeypatch.setattr(journal, "_read_entries_oldest_first", _entries)


def _ids(records: list[dict]) -> list[str]:
    return [r["id"] for r in records]


def test_unknown_metric_raises(journaled):
    with pytest.raises(ValueError):
        get_lifecycle_events("2026-06-11", "2026-06-11", "not_a_metric")


def test_all_card_metrics_are_supported():
    assert LIFECYCLE_METRICS == (
        "prime_suppressed",
        "pullback_entries",
        "continuation_events",
        "continuation_rejected",
        "sl_moves",
        "tp_extension",
        "avg_r_captured",
    )


def test_prime_suppressed_returns_suppressing_entries(journaled):
    rows = get_lifecycle_events("2026-06-11", "2026-06-11", "prime_suppressed")
    assert _ids(rows) == ["prime-1"]
    fields = {f["label"]: f["value"] for f in rows[0]["fields"]}
    assert fields["Suppressed signals"] == 3
    assert fields["Outcomes"] == [{"outcome": "invalidated_by_prime"}]


def test_pullback_entries_filter(journaled):
    rows = get_lifecycle_events("2026-06-11", "2026-06-11", "pullback_entries")
    # entry-old is out of range, so only entry-1 remains.
    assert _ids(rows) == ["entry-1"]
    assert rows[0]["signal_type"] == "pullback"


def test_continuation_events_include_management_and_warning(journaled):
    rows = get_lifecycle_events("2026-06-11", "2026-06-11", "continuation_events")
    assert set(_ids(rows)) == {"mgmt-accepted", "mgmt-rejected", "warn-1"}


def test_continuation_rejected_excludes_accepted(journaled):
    rows = get_lifecycle_events("2026-06-11", "2026-06-11", "continuation_rejected")
    assert set(_ids(rows)) == {"mgmt-rejected", "warn-1"}
    assert "mgmt-accepted" not in _ids(rows)


def test_sl_moves_and_tp_extension_use_entry_counts(journaled):
    sl = get_lifecycle_events("2026-06-11", "2026-06-11", "sl_moves")
    tp = get_lifecycle_events("2026-06-11", "2026-06-11", "tp_extension")
    assert _ids(sl) == ["entry-1"]
    assert _ids(tp) == ["entry-1"]


def test_avg_r_captured_includes_any_captured_r(journaled):
    rows = get_lifecycle_events("2026-06-11", "2026-06-11", "avg_r_captured")
    assert set(_ids(rows)) == {"entry-1", "outcome-1"}


def test_symbol_filter(journaled):
    rows = get_lifecycle_events("2026-06-11", "2026-06-11", "continuation_events", symbol="gbpjpy")
    assert _ids(rows) == ["warn-1"]


def test_results_are_newest_first(journaled):
    rows = get_lifecycle_events("2026-06-11", "2026-06-11", "continuation_events")
    # warn-1 (10:20) is newer than mgmt-rejected (10:15) and mgmt-accepted (10:10).
    assert _ids(rows) == ["warn-1", "mgmt-rejected", "mgmt-accepted"]


def test_pagination(journaled):
    page1 = get_lifecycle_events("2026-06-11", "2026-06-11", "continuation_events", limit=2, offset=0)
    page2 = get_lifecycle_events("2026-06-11", "2026-06-11", "continuation_events", limit=2, offset=2)
    assert _ids(page1) == ["warn-1", "mgmt-rejected"]
    assert _ids(page2) == ["mgmt-accepted"]


def test_matches_helper_directly():
    assert _lifecycle_event_matches("pullback_entries", {"lifecycle_role": "entry"})
    assert not _lifecycle_event_matches("pullback_entries", {"lifecycle_role": "management"})
    assert _lifecycle_event_matches("continuation_rejected", {"lifecycle_role": "management", "management_accepted": False})
    assert not _lifecycle_event_matches("continuation_rejected", {"lifecycle_role": "management", "management_accepted": True})

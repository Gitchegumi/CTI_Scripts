import csv
import json
from io import StringIO

import pytest

from tradegumi import journal


class FakeSignal:
    def __init__(
        self,
        *,
        symbol="EURUSD",
        direction="BUY",
        strategy="CTI-v1",
        confidence=0.8,
        entry_price=1.1000,
        signal_price=None,
        signal_type="pullback",
        pullback_trigger=None,
        pullback_bridge_status=None,
        pullback_rejection_reason=None,
        shock_blocked_signal=False,
        atr=0.0010,
        setup_condition_first_true_at=None,
        prime_outcome_candles=None,
    ):
        self.symbol = symbol
        self.direction = direction
        self.strategy = strategy
        self.signal_type = signal_type
        self.confidence = confidence
        self.entry_price = entry_price
        self.signal_price = signal_price if signal_price is not None else entry_price
        if direction.upper() == "SELL":
            self.stop_loss = entry_price + 0.0020
            self.take_profit = entry_price - 0.0040
        else:
            self.stop_loss = entry_price - 0.0020
            self.take_profit = entry_price + 0.0040
        self.lot_size = 1.0
        self.atr = atr
        self.pullback_trigger = pullback_trigger
        self.pullback_bridge_status = pullback_bridge_status
        self.pullback_rejection_reason = pullback_rejection_reason
        self.shock_blocked_signal = shock_blocked_signal
        self.setup_condition_first_true_at = setup_condition_first_true_at
        self.prime_outcome_candles = prime_outcome_candles or []


def write_entries(path, entries):
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")


@pytest.fixture
def journal_file(tmp_path, monkeypatch):
    path = tmp_path / "signal_journal.jsonl"
    monkeypatch.setattr(journal, "JOURNAL_FILE", path)
    return path


def test_export_journal_csv_empty_has_analysis_header(journal_file):
    csv_text = journal.export_journal_csv()

    assert "signal_id,symbol,direction,strategy" in csv_text
    assert csv_text.count("\n") == 1


def test_export_journal_csv_filters_and_preserves_legacy_fields(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "sig-1", "symbol": "EURUSD", "grade": "PENDING", "legacy_score": 0.7},
            {"signal_id": "sig-2", "symbol": "USDJPY", "grade": "TP_HIT", "legacy_score": 0.9},
        ],
    )

    csv_text = journal.export_journal_csv("TP_HIT")

    assert "legacy_score" in csv_text
    assert "sig-2" in csv_text
    assert "sig-1" not in csv_text


def test_build_journal_export_includes_attachment_metadata(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "symbol": "EURUSD", "signal_timestamp": "2026-05-10T10:00:00Z"}])

    result = journal.build_journal_export(journal.SignalJournalExportSelection(start="2026-05-01", end="2026-05-14"))

    assert result.record_count == 1
    assert result.filename == "signal-journal-2026-05-01-to-2026-05-14.csv"
    assert result.content_type == "text/csv; charset=utf-8"
    assert result.content_disposition == 'attachment; filename="signal-journal-2026-05-01-to-2026-05-14.csv"'
    assert "sig-1" in result.csv_text


def test_export_journal_csv_filters_by_evaluated_created_and_legacy_timestamps(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "sig-old", "evaluated_at": "2026-04-30T23:59:00Z"},
            {"signal_id": "sig-evaluated", "evaluated_at": "2026-05-10T12:00:00Z"},
            {"signal_id": "sig-created", "created_at": "2026-05-11T12:00:00Z"},
            {"signal_id": "sig-legacy", "signal_timestamp": "2026-05-12T12:00:00Z"},
            {"signal_id": "sig-new", "created_at": "2026-05-15T00:01:00Z"},
        ],
    )

    csv_text = journal.export_journal_csv(start="2026-05-10T00:00:00Z", end="2026-05-14T23:59:59Z")

    assert "sig-evaluated" in csv_text
    assert "sig-created" in csv_text
    assert "sig-legacy" in csv_text
    assert "sig-old" not in csv_text
    assert "sig-new" not in csv_text


def test_build_journal_export_rejects_invalid_range(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "created_at": "2026-05-10T12:00:00Z"}])

    with pytest.raises(ValueError, match="start must be before end"):
        journal.build_journal_export(journal.SignalJournalExportSelection(start="2026-05-14", end="2026-05-10"))


def test_build_journal_export_reports_empty_selection(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "created_at": "2026-05-10T12:00:00Z"}])

    result = journal.build_journal_export(journal.SignalJournalExportSelection(start="2026-05-11"))

    assert result.record_count == 0
    assert "signal_id,symbol,direction,strategy" in result.csv_text


def test_export_journal_csv_combines_grade_and_range(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "sig-1", "grade": "PENDING", "created_at": "2026-05-10T12:00:00Z"},
            {"signal_id": "sig-2", "grade": "TP_HIT", "created_at": "2026-05-10T12:00:00Z"},
            {"signal_id": "sig-3", "grade": "TP_HIT", "created_at": "2026-04-01T12:00:00Z"},
        ],
    )

    csv_text = journal.export_journal_csv("TP_HIT", start="2026-05-01", end="2026-05-14")

    assert "sig-2" in csv_text
    assert "sig-1" not in csv_text
    assert "sig-3" not in csv_text


def test_export_journal_csv_has_required_columns_and_json_nested_values(journal_file):
    write_entries(
        journal_file,
        [
            {
                "signal_id": "sig-1",
                "symbol": "EURUSD",
                "all_blockers": ["trend", "risk"],
                "criteria": {"trend": False, "risk": True},
            }
        ],
    )

    rows = list(csv.DictReader(StringIO(journal.export_journal_csv())))

    assert rows[0]["signal_id"] == "sig-1"
    assert "opportunity_id" in rows[0]
    assert "timeframe" in rows[0]
    assert "final_decision" in rows[0]
    assert "evaluated_at" in rows[0]
    assert "created_at" in rows[0]
    assert rows[0]["all_blockers"] == '["trend","risk"]'
    assert rows[0]["criteria"] == '{"risk":true,"trend":false}'


def test_read_journal_defaults_legacy_outcome_fields(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "grade": "PENDING", "trade_grade": "PENDING"}])

    entry = journal.read_journal()[0]

    assert entry["status"] == "open_simulated"
    assert entry["outcome"] == "none"
    assert entry["manually_overridden"] is False


def test_export_journal_csv_includes_auto_grading_fields(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "symbol": "EURUSD", "grade": "PENDING"}])

    rows = list(csv.DictReader(StringIO(journal.export_journal_csv())))

    assert "outcome_source" in rows[0]
    assert "exit_time" in rows[0]
    assert "exit_price" in rows[0]
    assert "outcome_checked_at" in rows[0]
    assert "manually_overridden" in rows[0]
    assert "manual_override_reason" in rows[0]


def test_expired_and_invalidated_outcome_defaults_export(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "expired", "grade": "EXPIRED"},
            {"signal_id": "invalid", "grade": "INVALID", "trade_grade": "INVALID"},
        ],
    )

    entries = {entry["signal_id"]: entry for entry in journal.read_journal()}
    rows = {row["signal_id"]: row for row in csv.DictReader(StringIO(journal.export_journal_csv()))}

    assert entries["expired"]["status"] == "expired"
    assert entries["expired"]["outcome"] == "expired"
    assert entries["invalid"]["status"] == "invalidated"
    assert entries["invalid"]["outcome"] == "invalidated_by_system"
    assert rows["expired"]["outcome"] == "expired"
    assert rows["invalid"]["outcome"] == "invalidated_by_system"


def test_append_signal_creates_setup_group_and_trade_outcome_fields(journal_file, monkeypatch):
    monkeypatch.setattr(journal, "_now_iso", lambda: "2026-05-14T14:00:00+00:00")

    signal_id = journal.append_signal(FakeSignal(setup_condition_first_true_at="2026-05-14T13:50:00+00:00"), rr=2.0)
    entry = journal.read_journal()[0]

    assert entry["signal_id"] == signal_id
    assert entry["setup_group_id"].startswith("EURUSD:BUY:CTI-v1:")
    assert entry["is_duplicate_setup"] is False
    assert entry["entry_valid_at_signal"] is True
    assert entry["entry_miss_distance"] == {"absolute": 0.0, "atr_normalized": 0.0}
    assert entry["signal_age_bars"] == 2
    assert entry["late_signal"] is False
    assert entry["usable_for_strategy_stats"] is True
    assert entry["trade_grade"] == "PENDING"
    assert entry["prime_active"] is True
    assert entry["prime_suppressed_signal_count"] == 0


def test_append_signal_marks_duplicate_inside_group_window(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:09:59+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal())
    journal.append_signal(FakeSignal())
    first = journal.read_journal()[0]

    assert first["is_duplicate_setup"] is False
    assert first["prime_active"] is True
    assert first["prime_suppressed_signal_count"] == 1


def test_append_signal_suppresses_beyond_group_window_when_prime_unresolved(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:10:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal())
    journal.append_signal(FakeSignal())
    first = journal.read_journal()[0]

    assert len(journal.read_journal()) == 1
    assert first["prime_suppressed_signal_count"] == 1


def test_append_signal_suppresses_same_symbol_different_strategy(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:05:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal(strategy="CTI-v1"))
    journal.append_signal(FakeSignal(strategy="CTI-v2"))
    first = journal.read_journal()[0]

    assert len(journal.read_journal()) == 1
    assert first["strategy"] == "CTI-v1"
    assert first["prime_suppressed_signal_count"] == 1


def test_append_signal_marks_late_signal_and_distance(journal_file, monkeypatch):
    monkeypatch.setattr(journal, "_now_iso", lambda: "2026-05-14T14:00:00+00:00")

    journal.append_signal(FakeSignal(entry_price=1.1000, signal_price=1.1010, atr=0.0010))
    entry = journal.read_journal()[0]

    assert entry["entry_valid_at_signal"] is False
    assert entry["entry_miss_distance"]["absolute"] == pytest.approx(0.0010)
    assert entry["entry_miss_distance"]["atr_normalized"] == pytest.approx(1.0)
    assert entry["late_signal"] is True
    assert entry["usable_for_strategy_stats"] is False
    assert entry["trade_grade"] == "LATE_SIGNAL"


def test_append_signal_keeps_boundary_price_valid(journal_file, monkeypatch):
    monkeypatch.setattr(journal, "_now_iso", lambda: "2026-05-14T14:00:00+00:00")

    journal.append_signal(FakeSignal(entry_price=1.1000, signal_price=1.10025, atr=0.0010))
    entry = journal.read_journal()[0]

    assert entry["entry_valid_at_signal"] is True
    assert entry["late_signal"] is False
    assert entry["usable_for_strategy_stats"] is True


def test_append_signal_zero_atr_leaves_normalized_distance_blank(journal_file, monkeypatch):
    monkeypatch.setattr(journal, "_now_iso", lambda: "2026-05-14T14:00:00+00:00")

    journal.append_signal(FakeSignal(entry_price=1.1000, signal_price=1.1000, atr=0.0))
    entry = journal.read_journal()[0]

    assert entry["entry_miss_distance"]["absolute"] == 0.0
    assert entry["entry_miss_distance"]["atr_normalized"] is None


def test_append_signal_handles_missing_entry_context(journal_file, monkeypatch):
    monkeypatch.setattr(journal, "_now_iso", lambda: "2026-05-14T14:00:00+00:00")
    signal = FakeSignal()
    signal.entry_price = None
    signal.signal_price = None

    journal.append_signal(signal)
    entry = journal.read_journal()[0]

    assert entry["entry_valid_at_signal"] is None
    assert entry["usable_for_strategy_stats"] is False
    assert entry["trade_grade"] == "INVALID"
    assert entry["stats_exclusion_reason"] == "missing_entry_context"


def test_append_signal_marks_stale_signal(journal_file, monkeypatch):
    monkeypatch.setattr(journal, "_now_iso", lambda: "2026-05-14T14:20:00+00:00")

    journal.append_signal(FakeSignal(setup_condition_first_true_at="2026-05-14T14:00:00+00:00"))
    entry = journal.read_journal()[0]

    assert entry["signal_age_bars"] == 4
    assert entry["usable_for_strategy_stats"] is False
    assert entry["trade_grade"] == "INVALID"
    assert entry["stats_exclusion_reason"] == "stale_signal"


def test_grade_and_invalidation_update_trade_grade_and_stats(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "grade": "PENDING", "trade_grade": "PENDING", "usable_for_strategy_stats": True}])

    assert journal.grade_by_signal_id("sig-1", "BE") is True
    assert journal.read_journal()[0]["trade_grade"] == "BE"
    assert journal.invalidate_signal("sig-1", "bad setup") is True
    entry = journal.read_journal()[0]
    assert entry["grade"] == "INVALID"
    assert entry["trade_grade"] == "INVALID"
    assert entry["usable_for_strategy_stats"] is False
    assert entry["stats_exclusion_reason"] == "manual_invalidated"


def test_purge_journal_entries_scopes_to_filter(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "sig-1", "grade": "PENDING"},
            {"signal_id": "sig-2", "grade": "TP_HIT"},
            {"signal_id": "sig-3", "grade": "TP_HIT"},
        ],
    )

    result = journal.purge_journal_entries("TP_HIT")

    assert result == {"removed_count": 2, "remaining_count": 1}
    remaining = journal.read_journal()
    assert [entry["signal_id"] for entry in remaining] == ["sig-1"]
    assert journal.purge_journal_entries("TP_HIT") == {"removed_count": 0, "remaining_count": 1}


def test_reset_signal_to_pending_preserves_signal_data_and_notes(journal_file):
    write_entries(
        journal_file,
        [
            {
                "signal_id": "sig-1",
                "symbol": "EURUSD",
                "grade": "SL_HIT",
                "trade_grade": "SL_HIT",
                "entry_valid_at_signal": True,
                "is_duplicate_setup": False,
                "late_signal": False,
                "signal_age_bars": 0,
                "usable_for_strategy_stats": True,
                "grade_timestamp": "2026-05-05T10:00:00Z",
                "notes": "keep this",
                "outcome": "loss",
                "score": 0.1,
                "lr_1h": 0.003,
            }
        ],
    )

    assert journal.reset_signal_to_pending("sig-1") is True
    entry = journal.read_journal()[0]
    assert entry["grade"] == "PENDING"
    assert entry["trade_grade"] == "PENDING"
    assert entry["usable_for_strategy_stats"] is True
    assert entry["grade_timestamp"] is None
    assert entry["notes"] == "keep this"
    assert entry["lr_1h"] == 0.003
    assert entry["status"] == "open_simulated"
    assert entry["outcome"] == "none"
    assert entry["manually_overridden"] is False
    assert "score" not in entry


def test_reset_pending_or_missing_signal_is_safe(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "grade": "PENDING", "notes": "ok"}])

    assert journal.reset_signal_to_pending("sig-1") is True
    assert journal.reset_signal_to_pending("missing") is False
    assert journal.read_journal()[0]["notes"] == "ok"


def candle_at(ts, high=1.1010, low=1.0990):
    return {"t": ts, "h": high, "l": low}


def test_prime_suppresses_later_buy_without_new_row(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:12:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    first_id = journal.append_signal(FakeSignal())
    suppressed_id = journal.append_signal(FakeSignal())
    entries = journal.read_journal()

    assert len(entries) == 1
    assert entries[0]["signal_id"] == first_id
    assert suppressed_id != first_id
    assert entries[0]["prime_suppressed_signal_count"] == 1
    assert entries[0]["prime_suppressed_same_direction_count"] == 1
    assert entries[0]["prime_suppressed_opposite_direction_count"] == 0
    assert entries[0]["prime_suppressed_last_at"] == "2026-05-14T14:12:00+00:00"
    assert entries[0]["prime_suppressed_signal_outcomes"][0]["status"] == "invalidated"
    assert entries[0]["prime_suppressed_signal_outcomes"][0]["outcome"] == "invalidated_by_prime"
    assert entries[0]["prime_suppressed_signal_outcomes"][0]["outcome_source"] == "system_prime_filter"


def test_prime_suppresses_later_sell_without_new_row(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:12:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal(direction="BUY"))
    journal.append_signal(FakeSignal(direction="SELL"))
    entry = journal.read_journal()[0]

    assert entry["prime_suppressed_signal_count"] == 1
    assert entry["prime_suppressed_same_direction_count"] == 0
    assert entry["prime_suppressed_opposite_direction_count"] == 1


def test_prime_is_symbol_specific(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:01:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal(symbol="AUDUSD"))
    journal.append_signal(FakeSignal(symbol="GBPJPY", entry_price=190.0, atr=0.1))
    entries = journal.read_journal()

    assert len(entries) == 2
    assert {entry["symbol"] for entry in entries} == {"AUDUSD", "GBPJPY"}
    assert all(entry["prime_active"] for entry in entries)


def test_buy_prime_tp_hit_closes_and_replaces_prime(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:12:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal(direction="BUY"))
    journal.append_signal(FakeSignal(direction="BUY", prime_outcome_candles=[candle_at("2026-05-14T14:05:00+00:00", high=1.1045, low=1.0995)]))
    newest, old = journal.read_journal()

    assert len(journal.read_journal()) == 2
    assert old["prime_active"] is False
    assert old["prime_closed_reason"] == "inferred_tp"
    assert old["prime_closed_at"] == "2026-05-14T14:12:00+00:00"
    assert newest["prime_active"] is True
    assert newest["is_duplicate_setup"] is False


def test_buy_prime_sl_hit_closes_and_replaces_prime(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:12:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal(direction="BUY"))
    journal.append_signal(FakeSignal(direction="BUY", prime_outcome_candles=[candle_at("2026-05-14T14:05:00+00:00", high=1.1010, low=1.0975)]))
    newest, old = journal.read_journal()

    assert old["prime_closed_reason"] == "inferred_sl"
    assert old["prime_active"] is False
    assert newest["prime_active"] is True


def test_sell_prime_tp_hit_closes_and_replaces_prime(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:12:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal(direction="SELL"))
    journal.append_signal(FakeSignal(direction="SELL", prime_outcome_candles=[candle_at("2026-05-14T14:05:00+00:00", high=1.1005, low=1.0955)]))
    newest, old = journal.read_journal()

    assert old["prime_closed_reason"] == "inferred_tp"
    assert old["prime_active"] is False
    assert newest["prime_active"] is True


def test_sell_prime_sl_hit_closes_and_replaces_prime(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:12:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal(direction="SELL"))
    journal.append_signal(FakeSignal(direction="SELL", prime_outcome_candles=[candle_at("2026-05-14T14:05:00+00:00", high=1.1025, low=1.0980)]))
    newest, old = journal.read_journal()

    assert old["prime_closed_reason"] == "inferred_sl"
    assert old["prime_active"] is False
    assert newest["prime_active"] is True


def test_ambiguous_prime_close_uses_conservative_sl(journal_file, monkeypatch):
    times = iter(["2026-05-14T14:00:00+00:00", "2026-05-14T14:12:00+00:00"])
    monkeypatch.setattr(journal, "_now_iso", lambda: next(times))

    journal.append_signal(FakeSignal(direction="BUY"))
    journal.append_signal(FakeSignal(direction="BUY", prime_outcome_candles=[candle_at("2026-05-14T14:05:00+00:00", high=1.1045, low=1.0975)]))
    _, old = journal.read_journal()

    assert old["prime_closed_reason"] == "inferred_sl"
    assert old["prime_close_ambiguous"] is True


def test_active_prime_recovers_from_persisted_journal(journal_file, monkeypatch):
    write_entries(
        journal_file,
        [
            {
                "signal_id": "sig-1",
                "symbol": "EURUSD",
                "direction": "BUY",
                "strategy": "CTI-v1",
                "entry_price": 1.1,
                "stop_loss": 1.098,
                "take_profit": 1.104,
                "signal_timestamp": "2026-05-14T14:00:00+00:00",
                "grade": "PENDING",
                "trade_grade": "PENDING",
                "usable_for_strategy_stats": True,
                "prime_active": True,
                "prime_suppressed_signal_count": 0,
            }
        ],
    )
    monkeypatch.setattr(journal, "_now_iso", lambda: "2026-05-14T14:12:00+00:00")

    journal.append_signal(FakeSignal())
    entry = journal.read_journal()[0]

    assert len(journal.read_journal()) == 1
    assert entry["prime_suppressed_signal_count"] == 1


def test_export_journal_csv_includes_prime_fields(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "symbol": "EURUSD", "prime_active": True, "prime_suppressed_signal_count": 2}])

    rows = list(csv.DictReader(StringIO(journal.export_journal_csv())))

    assert "prime_active" in rows[0]
    assert "prime_suppressed_signal_count" in rows[0]
    assert "prime_suppressed_last_at" in rows[0]
    assert "prime_closed_reason" in rows[0]
    assert "prime_closed_at" in rows[0]
    assert "prime_close_ambiguous" in rows[0]


def test_journal_exports_pullback_and_shock_review_fields(journal_file):
    journal.append_signal(FakeSignal(
        strategy="CTI-v1.2-pullback",
        signal_type="pullback",
        pullback_trigger="hammer",
        pullback_bridge_status="pullback_15m_bridge_allowed",
        shock_blocked_signal=False,
    ))

    rows = list(csv.DictReader(StringIO(journal.export_journal_csv())))

    assert rows[0]["strategy"] == "CTI-v1.2-pullback"
    assert rows[0]["signal_type"] == "pullback"
    assert rows[0]["pullback_trigger"] == "hammer"
    assert rows[0]["pullback_bridge_status"] == "pullback_15m_bridge_allowed"
    assert rows[0]["shock_blocked_signal"] == "False"


def test_manual_grade_and_invalidation_deactivate_prime(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "sig-1", "grade": "PENDING", "trade_grade": "PENDING", "usable_for_strategy_stats": True, "prime_active": True},
            {"signal_id": "sig-2", "grade": "PENDING", "trade_grade": "PENDING", "usable_for_strategy_stats": True, "prime_active": True},
        ],
    )

    assert journal.grade_by_signal_id("sig-1", "TP_HIT") is True
    assert journal.invalidate_signal("sig-2", "bad setup") is True
    entries = {entry["signal_id"]: entry for entry in journal.read_journal()}

    assert entries["sig-1"]["prime_active"] is False
    assert entries["sig-1"]["prime_closed_reason"] == "manual_grade"
    assert entries["sig-2"]["prime_active"] is False
    assert entries["sig-2"]["prime_closed_reason"] == "manual_invalidated"


def test_reset_pending_deactivates_prime_state(journal_file):
    write_entries(
        journal_file,
        [
            {
                "signal_id": "sig-1",
                "grade": "SL_HIT",
                "trade_grade": "SL_HIT",
                "usable_for_strategy_stats": True,
                "prime_active": True,
                "entry_valid_at_signal": True,
                "is_duplicate_setup": False,
                "late_signal": False,
                "signal_age_bars": 0,
            }
        ],
    )

    assert journal.reset_signal_to_pending("sig-1") is True
    entry = journal.read_journal()[0]

    assert entry["prime_active"] is False
    assert entry["prime_closed_reason"] == "reset"

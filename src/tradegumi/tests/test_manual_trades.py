import sqlite3

import pytest

from tradegumi.manual_trades import (
    TradePermissionError,
    create_trade,
    delete_trade_record,
    export_agent_data,
    get_dashboard_trade_history,
    get_summary_stats,
    get_unified_trade_history,
    init_schema,
    update_trade_record,
)


def source_trade(trade_id="src-1", **overrides):
    record = {
        "id": trade_id,
        "source": "execution_history",
        "symbol": "EURUSD",
        "side": "BUY",
        "volume": 1000,
        "open_price": 1.1,
        "close_price": 1.105,
        "open_time": "2026-04-01T10:00:00Z",
        "close_time": "2026-04-01T11:00:00Z",
        "realized_pl": 5.0,
        "pnl": 5.0,
        "financing": 0.0,
        "strategy": "breakout",
        "signal_id": "sig-1",
    }
    record.update(overrides)
    return record


def test_alert_only_history_includes_source_and_manual_trades(tmp_path):
    db_path = tmp_path / "manual.db"
    manual = create_trade(
        symbol="GBPUSD",
        direction="short",
        entry_price=1.25,
        exit_price=1.24,
        entry_time="2026-04-01T09:00:00Z",
        exit_time="2026-04-01T10:00:00Z",
        notes="backtest",
        tags="london, ai-review",
        bot_mode="alert_only",
        db_path=db_path,
    )

    records = get_unified_trade_history(
        bot_mode="alert_only",
        source_trades=[source_trade()],
        db_path=db_path,
    )

    ids = {record["id"] for record in records}
    assert manual["id"] in ids
    assert "execution_history:src-1" in ids
    assert next(record for record in records if record["id"] == manual["id"])["tags"] == ["london", "ai-review"]


def test_modes_are_isolated_for_manual_rows_and_annotations(tmp_path):
    db_path = tmp_path / "manual.db"
    init_schema(db_path)
    created = create_trade(
        symbol="USDJPY",
        direction="long",
        entry_price=150.0,
        entry_time="2026-04-02T09:00:00Z",
        bot_mode="alert_only",
        db_path=db_path,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE manual_trades SET bot_mode = NULL WHERE id = ?", (created["source_trade_id"],))

    update_trade_record(
        "execution_history:src-1",
        {"notes": "demo note", "tags": "demo"},
        bot_mode="demo",
        source_trades=[source_trade()],
        db_path=db_path,
    )

    alert_records = get_unified_trade_history(
        bot_mode="alert_only",
        source_trades=[source_trade()],
        db_path=db_path,
    )
    demo_records = get_unified_trade_history(
        bot_mode="demo",
        source_trades=[source_trade()],
        db_path=db_path,
    )

    assert created["id"] in {record["id"] for record in alert_records}
    assert created["id"] not in {record["id"] for record in demo_records}
    assert next(record for record in demo_records if record["id"] == "execution_history:src-1")["notes"] == "demo note"
    assert next(record for record in alert_records if record["id"] == "execution_history:src-1")["notes"] == ""


def test_alert_only_can_override_historical_source_fields(tmp_path):
    db_path = tmp_path / "manual.db"
    updated = update_trade_record(
        "execution_history:src-1",
        {"entry_price": "1.09", "exit_price": "1.11", "notes": "corrected", "tags": ["override"]},
        bot_mode="alert_only",
        source_trades=[source_trade()],
        db_path=db_path,
    )

    assert updated["entry_price"] == 1.09
    assert updated["open_price"] == 1.09
    assert updated["exit_price"] == 1.11
    assert updated["notes"] == "corrected"
    assert updated["tags"] == ["override"]
    assert updated["has_overrides"] is True


def test_alert_only_can_update_manual_trade_fields_and_not_delete_source(tmp_path):
    db_path = tmp_path / "manual.db"
    created = create_trade(
        symbol="EURUSD",
        direction="long",
        entry_price=1.1,
        entry_time="2026-04-02T09:00:00Z",
        bot_mode="alert_only",
        db_path=db_path,
    )

    updated = update_trade_record(
        created["id"],
        {"symbol": "GBPUSD", "direction": "short", "entry_price": "1.25", "exit_price": "1.24"},
        bot_mode="alert_only",
        db_path=db_path,
    )

    assert updated["symbol"] == "GBPUSD"
    assert updated["direction"] == "short"
    assert updated["status"] == "closed"
    with pytest.raises(TradePermissionError):
        delete_trade_record("execution_history:src-1", bot_mode="alert_only", db_path=db_path)


def test_non_alert_modes_only_allow_notes_and_tags(tmp_path):
    db_path = tmp_path / "manual.db"
    updated = update_trade_record(
        "execution_history:src-1",
        {"notes": "watch", "tags": "review, live"},
        bot_mode="live",
        source_trades=[source_trade()],
        db_path=db_path,
    )

    assert updated["notes"] == "watch"
    assert updated["tags"] == ["review", "live"]
    assert updated["permissions"]["can_edit_all_fields"] is False
    with pytest.raises(TradePermissionError):
        update_trade_record(
            "execution_history:src-1",
            {"entry_price": 1.2},
            bot_mode="live",
            source_trades=[source_trade()],
            db_path=db_path,
        )


def test_delete_is_limited_to_alert_only_manual_trades(tmp_path):
    db_path = tmp_path / "manual.db"
    created = create_trade(
        symbol="AUDUSD",
        direction="long",
        entry_price=0.66,
        entry_time="2026-04-02T09:00:00Z",
        bot_mode="alert_only",
        db_path=db_path,
    )
    update_trade_record(
        created["id"],
        {"notes": "remove me", "tags": ["cleanup"], "entry_price": 0.67},
        bot_mode="alert_only",
        db_path=db_path,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO trade_annotations
            (trade_identity, source, source_trade_id, bot_mode, notes, tags, created_at, updated_at)
            VALUES (?, 'manual', ?, 'alert_only', 'orphan check', '[]', 'now', 'now')
            """,
            (created["id"], created["source_trade_id"]),
        )
        conn.execute(
            """
            INSERT INTO trade_overrides
            (trade_identity, source, source_trade_id, bot_mode, values_json, created_at, updated_at)
            VALUES (?, 'manual', ?, 'alert_only', '{}', 'now', 'now')
            """,
            (created["id"], created["source_trade_id"]),
        )

    with pytest.raises(TradePermissionError):
        delete_trade_record(created["id"], bot_mode="demo", db_path=db_path)
    assert delete_trade_record(created["id"], bot_mode="alert_only", db_path=db_path) is True
    assert get_unified_trade_history(bot_mode="alert_only", db_path=db_path) == []
    with sqlite3.connect(db_path) as conn:
        annotation_count = conn.execute("SELECT COUNT(*) FROM trade_annotations").fetchone()[0]
        override_count = conn.execute("SELECT COUNT(*) FROM trade_overrides").fetchone()[0]
    assert annotation_count == 0
    assert override_count == 0


def test_summary_and_agent_export_include_current_mode_records(tmp_path):
    db_path = tmp_path / "manual.db"
    create_trade(
        symbol="GBPUSD",
        direction="long",
        entry_price=1.25,
        exit_price=1.255,
        entry_time="2026-04-02T09:00:00Z",
        exit_time="2026-04-02T10:00:00Z",
        bot_mode="alert_only",
        db_path=db_path,
    )

    summary = get_summary_stats(
        bot_mode="alert_only",
        source_trades=[source_trade(realized_pl=-2.0, pnl=-2.0)],
        db_path=db_path,
    )
    payload = export_agent_data(
        bot_mode="alert_only",
        source_trades=[source_trade()],
        db_path=db_path,
    )

    assert summary["total_trades"] == 2
    assert summary["closed_trades"] == 2
    assert payload["schema_name"] == "Agent Export"
    assert payload["schema_version"] == "manual-trade-agent-export.v1"
    assert payload["chunking"]["chunk_count"] == 1
    assert payload["records"]


def test_dashboard_history_returns_manual_trades_when_source_history_is_empty(tmp_path):
    db_path = tmp_path / "manual.db"
    created = create_trade(
        symbol="EURUSD",
        direction="long",
        entry_price=1.1,
        exit_price=1.105,
        entry_time="2026-05-05T10:00:00Z",
        exit_time="2026-05-05T11:00:00Z",
        bot_mode="alert_only",
        db_path=db_path,
    )

    history = get_dashboard_trade_history(count=50, bot_mode="alert_only", source_trades=[], db_path=db_path)

    assert [trade["id"] for trade in history] == [created["id"]]
    assert history[0]["source"] == "manual"


def test_alert_only_can_correct_manual_trade_pnl_and_export_reflects_it(tmp_path):
    db_path = tmp_path / "manual.db"
    created = create_trade(
        symbol="GBPUSD",
        direction="long",
        entry_price=1.25,
        exit_price=1.255,
        entry_time="2026-05-05T10:00:00Z",
        exit_time="2026-05-05T11:00:00Z",
        bot_mode="alert_only",
        db_path=db_path,
    )

    updated = update_trade_record(
        created["id"],
        {"pnl": "-12.5", "pnl_percent": "-1.0"},
        bot_mode="alert_only",
        db_path=db_path,
    )
    payload = export_agent_data(bot_mode="alert_only", db_path=db_path)
    summary = get_summary_stats(bot_mode="alert_only", db_path=db_path)

    assert updated["pnl"] == -12.5
    assert updated["pnl_percent"] == -1.0
    assert payload["records"][0]["pnl"] == -12.5
    assert summary["total_pnl"] == -12.5


def test_non_alert_modes_still_reject_pnl_edits(tmp_path):
    db_path = tmp_path / "manual.db"

    with pytest.raises(TradePermissionError):
        update_trade_record(
            "execution_history:src-1",
            {"pnl": 99.0},
            bot_mode="demo",
            source_trades=[source_trade()],
            db_path=db_path,
        )

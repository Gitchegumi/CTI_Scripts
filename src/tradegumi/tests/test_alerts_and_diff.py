"""Tests for save_signal append behavior, record_trade_correlation, and format_watchlist_diff."""
import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from pytz import timezone

from tradegumi.signal_engine import Signal
from tradegumi.alerts import (
    format_signal_message,
    save_signal,
    record_trade_correlation,
    _parse_ts,
    SIGNAL_RETENTION_DAYS,
)
from tradegumi.pre_session_scanner import format_watchlist_diff

NY_TZ = timezone("America/New_York")


def make_signal(
    symbol="EURUSD", direction="BUY",
    entry=1.1000, sl=1.0900, tp=1.1400,
    confidence=0.65,
) -> Signal:
    return Signal(
        symbol=symbol, direction=direction,
        entry_price=entry, stop_loss=sl, take_profit=tp,
        atr=0.0010, lot_size=0.01, risk_pct=1.0,
        confidence=confidence, breakdown={},
        trend_direction="Uptrend", patterns_found=[],
    )


def make_result(ranked: list[tuple]) -> dict:
    return {
        "ranked": ranked,
        "tier1": [s for s, _, t in ranked if t == "Tier 1"],
        "tier2": [s for s, _, t in ranked if t == "Tier 2"],
    }


def make_raw_entry(
    symbol="EURUSD", direction="BUY", confidence=0.75,
    ts: str | None = None,
) -> dict:
    return {
        "symbol": symbol,
        "direction": direction,
        "confidence": confidence,
        "entry_price": 1.1000,
        "stop_loss": 1.0900,
        "take_profit": 1.1400,
        "lot_size": 0.01,
        "atr": 0.001,
        "rr": 4.0,
        "timestamp": ts or datetime.now(NY_TZ).isoformat(),
    }


# ── save_signal ───────────────────────────────────────────────────────────────

class TestSaveSignal:
    def test_first_insert_creates_one_entry(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal())
        data = json.loads(sig_file.read_text())
        assert len(data) == 1

    def test_each_call_appends_distinct_entry(self, tmp_path):
        """Append-only: same symbol+direction never deduplicates."""
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal(entry=1.1000))
            save_signal(make_signal(entry=1.1050))
        data = json.loads(sig_file.read_text())
        assert len(data) == 2
        assert data[0]["entry_price"] == 1.1000
        assert data[1]["entry_price"] == 1.1050

    def test_different_symbols_both_stored(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal(symbol="EURUSD"))
            save_signal(make_signal(symbol="USDJPY", entry=150.0, sl=149.0, tp=154.0))
        data = json.loads(sig_file.read_text())
        assert len(data) == 2
        assert {e["symbol"] for e in data} == {"EURUSD", "USDJPY"}

    def test_buy_and_sell_stored_as_separate_entries(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal(direction="BUY"))
            save_signal(make_signal(direction="SELL", sl=1.1100, tp=1.0600))
        data = json.loads(sig_file.read_text())
        assert len(data) == 2
        assert {e["direction"] for e in data} == {"BUY", "SELL"}

    def test_seven_day_rolling_trim_drops_stale_entries(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        stale_ts = (datetime.now(NY_TZ) - timedelta(days=SIGNAL_RETENTION_DAYS + 1)).isoformat()
        sig_file.write_text(json.dumps([make_raw_entry(ts=stale_ts)]))
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal())  # fresh signal triggers trim
        data = json.loads(sig_file.read_text())
        assert len(data) == 1
        assert data[0]["entry_price"] == 1.1000  # only the fresh entry remains

    def test_recent_entries_not_trimmed(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        recent_ts = (datetime.now(NY_TZ) - timedelta(days=SIGNAL_RETENTION_DAYS - 1)).isoformat()
        sig_file.write_text(json.dumps([make_raw_entry(ts=recent_ts)]))
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal())
        data = json.loads(sig_file.read_text())
        assert len(data) == 2  # both survive

    def test_zero_division_rr_stored_as_none(self, tmp_path):
        """When entry == stop_loss, R:R is None (undefined), not 0.0."""
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal(entry=1.1000, sl=1.1000, tp=1.1400))
        data = json.loads(sig_file.read_text())
        assert data[0]["rr"] is None

    def test_save_signal_writes_lifecycle_state(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        signal = make_signal()
        signal.signal_type = "continuation"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(signal)

        data = json.loads(sig_file.read_text())
        assert data[0]["signal_type"] == "continuation"
        assert data[0]["lifecycle_role"] == "management"
        assert data[0]["source_signal_type"] == "continuation"
        assert data[0]["current_stop_loss"] == signal.stop_loss
        assert data[0]["current_take_profit"] == signal.take_profit

    def test_format_signal_message_includes_lifecycle_field(self):
        signal = make_signal()
        signal.signal_type = "continuation"

        payload = format_signal_message(signal)
        fields = {field["name"]: field["value"] for field in payload["embeds"][0]["fields"]}

        assert fields["Signal Type"] == "continuation"
        assert fields["Lifecycle"] == "Continuation management event"

    def test_format_signal_message_uses_bullish_color_for_uptrend(self):
        signal = make_signal(direction="UPTREND")

        payload = format_signal_message(signal)

        assert payload["embeds"][0]["color"] == 0x00FF00
        assert "🟢" in payload["embeds"][0]["title"]

    def test_format_signal_message_uses_bearish_color_for_downtrend(self):
        signal = make_signal(direction="DOWNTREND")

        payload = format_signal_message(signal)

        assert payload["embeds"][0]["color"] == 0xFF0000
        assert "🔴" in payload["embeds"][0]["title"]


# ── record_trade_correlation ─────────────────────────────────────────────────

class TestRecordTradeCorrelation:
    def test_matching_signal_within_5_min_creates_correlation(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        corr_file = tmp_path / "trade_correlations.json"
        now = datetime.now(NY_TZ)
        sig_ts = (now - timedelta(minutes=3)).isoformat()
        sig_file.write_text(json.dumps([make_raw_entry(confidence=0.75, ts=sig_ts)]))

        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file), \
             patch("tradegumi.alerts.TRADE_CORRELATIONS_FILE", corr_file):
            record_trade_correlation("t-1", "EURUSD", "BUY", now)

        corr = json.loads(corr_file.read_text())
        assert len(corr) == 1
        assert corr[0]["trade_id"] == "t-1"
        assert corr[0]["confidence"] == 0.75
        assert corr[0]["signal_lag_seconds"] == pytest.approx(180, abs=5)

    def test_signal_outside_5_min_window_no_correlation(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        corr_file = tmp_path / "trade_correlations.json"
        now = datetime.now(NY_TZ)
        old_ts = (now - timedelta(minutes=10)).isoformat()
        sig_file.write_text(json.dumps([make_raw_entry(ts=old_ts)]))

        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file), \
             patch("tradegumi.alerts.TRADE_CORRELATIONS_FILE", corr_file):
            record_trade_correlation("t-2", "EURUSD", "BUY", now)

        assert not corr_file.exists()

    def test_picks_most_recent_signal_when_multiple_in_window(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        corr_file = tmp_path / "trade_correlations.json"
        now = datetime.now(NY_TZ)
        entries = [
            make_raw_entry(confidence=0.60, ts=(now - timedelta(minutes=4)).isoformat()),
            make_raw_entry(confidence=0.80, ts=(now - timedelta(minutes=1)).isoformat()),
        ]
        sig_file.write_text(json.dumps(entries))

        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file), \
             patch("tradegumi.alerts.TRADE_CORRELATIONS_FILE", corr_file):
            record_trade_correlation("t-3", "EURUSD", "BUY", now)

        corr = json.loads(corr_file.read_text())
        assert corr[0]["confidence"] == 0.80  # most recent, not oldest

    def test_wrong_direction_not_matched(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        corr_file = tmp_path / "trade_correlations.json"
        now = datetime.now(NY_TZ)
        sig_ts = (now - timedelta(minutes=2)).isoformat()
        sig_file.write_text(json.dumps([make_raw_entry(direction="SELL", ts=sig_ts)]))

        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file), \
             patch("tradegumi.alerts.TRADE_CORRELATIONS_FILE", corr_file):
            record_trade_correlation("t-4", "EURUSD", "BUY", now)

        assert not corr_file.exists()

    def test_missing_signals_file_exits_cleanly(self, tmp_path):
        sig_file = tmp_path / "nonexistent.json"
        corr_file = tmp_path / "trade_correlations.json"
        now = datetime.now(NY_TZ)

        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file), \
             patch("tradegumi.alerts.TRADE_CORRELATIONS_FILE", corr_file):
            record_trade_correlation("t-5", "EURUSD", "BUY", now)

        assert not corr_file.exists()

    def test_correlation_file_uses_rolling_7_day_trim(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        corr_file = tmp_path / "trade_correlations.json"
        now = datetime.now(NY_TZ)

        # Pre-seed an old correlation
        old_ts = (now - timedelta(days=SIGNAL_RETENTION_DAYS + 1)).isoformat()
        corr_file.write_text(json.dumps([{
            "trade_id": "old", "symbol": "EURUSD", "direction": "BUY",
            "confidence": 0.5, "signal_timestamp": old_ts,
            "trade_timestamp": old_ts, "signal_lag_seconds": 30,
        }]))

        sig_ts = (now - timedelta(minutes=2)).isoformat()
        sig_file.write_text(json.dumps([make_raw_entry(ts=sig_ts)]))

        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file), \
             patch("tradegumi.alerts.TRADE_CORRELATIONS_FILE", corr_file):
            record_trade_correlation("t-6", "EURUSD", "BUY", now)

        corr = json.loads(corr_file.read_text())
        assert len(corr) == 1  # stale entry trimmed
        assert corr[0]["trade_id"] == "t-6"


# ── _parse_ts ────────────────────────────────────────────────────────────────

class TestParseTs:
    def test_tz_aware_iso_parses_correctly(self):
        ts = "2026-04-21T16:00:00-04:00"
        result = _parse_ts(ts)
        assert result.tzinfo is not None
        assert result.hour == 16

    def test_naive_iso_gets_ny_timezone(self):
        ts = "2026-04-21T16:00:00"
        result = _parse_ts(ts)
        assert result.tzinfo is not None

    def test_invalid_string_returns_datetime_min(self):
        result = _parse_ts("not-a-date")
        assert result.year == 1  # datetime.min — treated as expired


# ── format_watchlist_diff ─────────────────────────────────────────────────────

class TestFormatWatchlistDiff:
    def test_identical_results_returns_none(self):
        r = make_result([("EURUSD", 0.60, "Tier 1"), ("USDJPY", 0.52, "Tier 2")])
        assert format_watchlist_diff(r, r) is None

    def test_score_shift_below_threshold_returns_none(self):
        prev = make_result([("EURUSD", 0.60, "Tier 1")])
        new  = make_result([("EURUSD", 0.63, "Tier 1")])  # delta 0.03 < 0.05
        assert format_watchlist_diff(prev, new) is None

    def test_score_shift_at_threshold_returns_diff(self):
        prev = make_result([("EURUSD", 0.60, "Tier 1")])
        new  = make_result([("EURUSD", 0.65, "Tier 1")])  # delta exactly 0.05
        assert format_watchlist_diff(prev, new) is not None

    def test_tier_upgrade_shows_up_arrow(self):
        prev = make_result([("EURUSD", 0.52, "Tier 2")])
        new  = make_result([("EURUSD", 0.61, "Tier 1")])
        result = format_watchlist_diff(prev, new)
        assert result is not None and "⬆️" in result

    def test_tier_downgrade_shows_down_arrow(self):
        prev = make_result([("EURUSD", 0.61, "Tier 1")])
        new  = make_result([("EURUSD", 0.52, "Tier 2")])
        result = format_watchlist_diff(prev, new)
        assert result is not None and "⬇️" in result

    def test_tier_down_despite_score_up_shows_down_arrow(self):
        # Score nudged up but tier dropped — arrow must follow tier rank, not score
        prev = make_result([("EURUSD", 0.60, "Tier 1")])
        new  = make_result([("EURUSD", 0.61, "Tier 2")])
        result = format_watchlist_diff(prev, new)
        assert result is not None
        assert "⬇️" in result
        assert "⬆️" not in result

    def test_new_symbol_shows_added_marker(self):
        prev = make_result([("EURUSD", 0.60, "Tier 1")])
        new  = make_result([("EURUSD", 0.60, "Tier 1"), ("USDJPY", 0.55, "Tier 2")])
        result = format_watchlist_diff(prev, new)
        assert result is not None
        assert "🆕" in result and "USDJPY" in result

    def test_removed_symbol_shows_removed_marker(self):
        prev = make_result([("EURUSD", 0.60, "Tier 1"), ("USDJPY", 0.55, "Tier 2")])
        new  = make_result([("EURUSD", 0.60, "Tier 1")])
        result = format_watchlist_diff(prev, new)
        assert result is not None
        assert "❌" in result and "USDJPY" in result

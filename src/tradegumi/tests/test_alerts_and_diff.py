"""Tests for save_signal upsert behavior and format_watchlist_diff."""
import json
from unittest.mock import patch

import pytest

from tradegumi.signal_engine import Signal
from tradegumi.alerts import save_signal
from tradegumi.pre_session_scanner import format_watchlist_diff


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


# ── save_signal ───────────────────────────────────────────────────────────────

class TestSaveSignal:
    def test_first_insert_has_update_count_1(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal())
        data = json.loads(sig_file.read_text())
        assert len(data) == 1
        assert data[0]["update_count"] == 1

    def test_same_symbol_and_direction_preserves_original_levels(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal(entry=1.1000, sl=1.0900, tp=1.1400, confidence=0.65))
            save_signal(make_signal(entry=1.1050, sl=1.0850, tp=1.1450, confidence=0.72))
        data = json.loads(sig_file.read_text())
        assert len(data) == 1
        assert data[0]["entry_price"] == 1.1000
        assert data[0]["stop_loss"]   == 1.0900
        assert data[0]["take_profit"] == 1.1400
        assert data[0]["confidence"]  == 0.65
        assert data[0]["update_count"] == 2

    def test_update_count_increments_on_each_repeat(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            for _ in range(5):
                save_signal(make_signal())
        data = json.loads(sig_file.read_text())
        assert data[0]["update_count"] == 5

    def test_direction_flip_replaces_entry_and_resets_count(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal(direction="BUY", entry=1.1000))
            save_signal(make_signal(direction="SELL", entry=1.1050, sl=1.1150, tp=1.0650))
        data = json.loads(sig_file.read_text())
        assert len(data) == 1
        assert data[0]["direction"] == "SELL"
        assert data[0]["entry_price"] == 1.1050
        assert data[0]["update_count"] == 1

    def test_different_symbols_stored_independently(self, tmp_path):
        sig_file = tmp_path / "signals.json"
        with patch("tradegumi.alerts.SIGNALS_FILE", sig_file):
            save_signal(make_signal(symbol="EURUSD"))
            save_signal(make_signal(symbol="USDJPY", entry=150.0, sl=149.0, tp=154.0))
        data = json.loads(sig_file.read_text())
        assert len(data) == 2
        assert {e["symbol"] for e in data} == {"EURUSD", "USDJPY"}


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

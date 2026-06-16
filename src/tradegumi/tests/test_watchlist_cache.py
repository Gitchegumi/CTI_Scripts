"""Tests for WatchlistCache rescan → available watchlist → streaming subscription handoff.

These tests are intentionally file-system free. They patch the JSON file loaders
used by ``WatchlistCache`` so we can exercise the handoff logic without needing
a persisted watchlist.json on disk.
"""
import json
from pathlib import Path

import pytest

from tradegumi import config
from tradegumi.main import WatchlistCache


@pytest.fixture(autouse=True)
def _restore_config_unavailable():
    """Reset the global unavailable-instruments set after each test."""
    original = set(config.UNAVAILABLE_INSTRUMENTS)
    yield
    config.UNAVAILABLE_INSTRUMENTS = original


@pytest.fixture
def watchlist_file(tmp_path, monkeypatch):
    """Point WATCHLIST_FILE to a temp path and return it."""
    from tradegumi import pre_session_scanner
    fake = tmp_path / "watchlist.json"
    monkeypatch.setattr(pre_session_scanner, "WATCHLIST_FILE", fake)
    return fake


def write_watchlist(path: Path, **fields) -> None:
    """Write a minimal watchlist.json payload."""
    defaults = {
        "timestamp": "2026-06-15T22:32:00",
        "tier1": [],
        "tier2": [],
        "below": [],
        "ranked": [],
        "detail": {},
    }
    defaults.update(fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(defaults))


def test_empty_watchlist_falls_back_to_execution_symbols(monkeypatch, watchlist_file):
    """Regression (#132): empty tier1/tier2 must not zero out scan_symbols."""
    write_watchlist(watchlist_file, tier1=[], tier2=[], ranked=[])
    # Monkeypatch loader so we definitely exercise the empty-tiers branch.
    monkeypatch.setattr(
        "tradegumi.main.load_watchlist_with_scores",
        lambda: {},
    )
    cache = WatchlistCache()
    available = {"EURUSD", "GBPUSD", "USDJPY"}

    cache.refresh(available)

    assert sorted(cache.scan_symbols) == sorted(available)


def test_populated_watchlist_keeps_ranked_available_symbols(monkeypatch, watchlist_file):
    """When tiers exist, scan_symbols stays limited to ranked + available."""
    write_watchlist(
        watchlist_file,
        tier1=["EURUSD"],
        tier2=["GBPUSD"],
        ranked=[["EURUSD", 0.9, "Tier 1"], ["GBPUSD", 0.7, "Tier 2"], ["USDJPY", 0.5, "Below"]],
    )
    monkeypatch.setattr(
        "tradegumi.main.load_watchlist_with_scores",
        lambda: {
            "EURUSD": {"tier": "Tier 1", "score": 0.9},
            "GBPUSD": {"tier": "Tier 2", "score": 0.7},
        },
    )
    cache = WatchlistCache()
    available = {"EURUSD", "GBPUSD", "USDJPY"}

    cache.refresh(available)

    assert sorted(cache.scan_symbols) == ["EURUSD", "GBPUSD"]


def test_unavailable_instruments_are_filtered_from_scan_symbols(monkeypatch, watchlist_file):
    """Unavailable instruments configured at rescan time must be excluded."""
    write_watchlist(
        watchlist_file,
        tier1=["EURUSD", "USDJPY"],
        tier2=["GBPUSD"],
        ranked=[
            ["EURUSD", 0.9, "Tier 1"],
            ["GBPUSD", 0.7, "Tier 2"],
            ["USDJPY", 0.6, "Tier 1"],
        ],
    )
    monkeypatch.setattr(
        "tradegumi.main.load_watchlist_with_scores",
        lambda: {
            "EURUSD": {"tier": "Tier 1", "score": 0.9},
            "GBPUSD": {"tier": "Tier 2", "score": 0.7},
            "USDJPY": {"tier": "Tier 1", "score": 0.6},
        },
    )
    config.UNAVAILABLE_INSTRUMENTS = {"USDJPY"}
    cache = WatchlistCache()
    available = {"EURUSD", "GBPUSD", "USDJPY"}

    cache.refresh(available)

    assert "USDJPY" not in cache.scan_symbols
    assert sorted(cache.scan_symbols) == ["EURUSD", "GBPUSD"]


def test_available_symbols_not_on_watchlist_are_excluded_when_watchlist_populated(monkeypatch, watchlist_file):
    """If the watchlist has entries, symbols outside it must not be added."""
    write_watchlist(
        watchlist_file,
        tier1=["EURUSD"],
        tier2=["GBPUSD"],
        ranked=[
            ["EURUSD", 0.9, "Tier 1"],
            ["GBPUSD", 0.7, "Tier 2"],
        ],
    )
    monkeypatch.setattr(
        "tradegumi.main.load_watchlist_with_scores",
        lambda: {
            "EURUSD": {"tier": "Tier 1", "score": 0.9},
            "GBPUSD": {"tier": "Tier 2", "score": 0.7},
        },
    )
    cache = WatchlistCache()
    available = {"EURUSD", "GBPUSD", "USDJPY"}

    cache.refresh(available)

    assert "USDJPY" not in cache.scan_symbols
    assert sorted(cache.scan_symbols) == ["EURUSD", "GBPUSD"]

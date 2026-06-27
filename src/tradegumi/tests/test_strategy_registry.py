"""Tests for the strategy registry (spec 022 US2 / issue #160)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tradegumi.strategy_registry import (
    BUILTIN_STRATEGY,
    _discover_folder_strategies,
    get_strategies,
)


class TestDiscoverFolderStrategies:
    """Unit tests for _discover_folder_strategies."""

    def test_returns_empty_when_base_dir_missing(self):
        """No strategies returned when the base directory does not exist."""
        strategies = _discover_folder_strategies(Path("/nonexistent/strategy/dir"))
        assert strategies == []

    def test_returns_empty_when_base_dir_has_no_subfolders(self, tmp_path):
        """No strategies returned when the base directory has no subfolders."""
        strategies = _discover_folder_strategies(tmp_path)
        assert strategies == []

    def test_returns_empty_when_base_dir_only_has_files(self, tmp_path):
        """Subfolders without strategy.json are included with a warning."""
        (tmp_path / "not-a-folder.txt").write_text("not a folder")
        strategies = _discover_folder_strategies(tmp_path)
        assert strategies == []

    def test_returns_strategy_from_valid_folder(self, tmp_path):
        """A subfolder with a valid strategy.json is returned without warning."""
        strat_dir = tmp_path / "cti-v1-pullback"
        strat_dir.mkdir()
        (strat_dir / "strategy.json").write_text(
            json.dumps({
                "id": "CTI-v1.2-pullback",
                "label": "Pullback (CTI v1.2)",
                "description": "Test strategy",
                "signal_type": "pullback",
            })
        )

        strategies = _discover_folder_strategies(tmp_path)
        assert len(strategies) == 1
        assert strategies[0].id == "CTI-v1.2-pullback"
        assert strategies[0].label == "Pullback (CTI v1.2)"
        assert strategies[0].description == "Test strategy"
        assert strategies[0].source == "folder"
        assert strategies[0].warning is None

    def test_returns_warning_when_folder_missing_strategy_json(self, tmp_path):
        """A subfolder without strategy.json is included with a warning."""
        strat_dir = tmp_path / "no-metadata"
        strat_dir.mkdir()

        strategies = _discover_folder_strategies(tmp_path)
        assert len(strategies) == 1
        assert strategies[0].id == "no-metadata"
        assert strategies[0].warning is not None
        assert "no strategy.json" in strategies[0].warning

    def test_returns_warning_when_strategy_json_is_malformed(self, tmp_path):
        """A subfolder with malformed JSON is included with a warning."""
        strat_dir = tmp_path / "bad-json"
        strat_dir.mkdir()
        (strat_dir / "strategy.json").write_text("{ not valid json }")

        strategies = _discover_folder_strategies(tmp_path)
        assert len(strategies) == 1
        assert strategies[0].id == "bad-json"
        assert strategies[0].warning is not None
        assert "malformed" in strategies[0].warning

    def test_returns_warning_when_strategy_json_has_missing_id(self, tmp_path):
        """A strategy.json without a valid 'id' field is included with a warning."""
        strat_dir = tmp_path / "missing-id"
        strat_dir.mkdir()
        (strat_dir / "strategy.json").write_text(
            json.dumps({
                "label": "Missing ID",
                "description": "Has no id field",
            })
        )

        strategies = _discover_folder_strategies(tmp_path)
        assert len(strategies) == 1
        assert strategies[0].id == "missing-id"
        assert strategies[0].warning is not None
        assert "valid 'id'" in strategies[0].warning

    def test_multiple_folders_sorted_alphabetically(self, tmp_path):
        """Multiple valid folders are returned in sorted order."""
        for name in ["zulu-strategy", "alpha-strategy", "bravo-strategy"]:
            d = tmp_path / name
            d.mkdir()
            (d / "strategy.json").write_text(
                json.dumps({"id": name, "label": name, "description": ""})
            )

        strategies = _discover_folder_strategies(tmp_path)
        ids = [s.id for s in strategies]
        assert ids == ["alpha-strategy", "bravo-strategy", "zulu-strategy"]


class TestGetStrategies:
    """Integration tests for get_strategies (end-to-end with real temp dirs)."""

    def test_builtin_cti_v1_always_first(self, monkeypatch, tmp_path):
        """CTI-v1 builtin entry is always first even when no folders exist."""
        monkeypatch.setenv("STRATEGIES_DIR", str(tmp_path))
        # No subfolders in tmp_path — only builtin should be returned
        result = get_strategies()

        assert result[0]["id"] == "CTI-v1"
        assert result[0]["source"] == "builtin"
        assert result[0]["warning"] is None
        # Folders with warnings should still appear after builtin
        # (since tmp_path is empty there are no folder entries here)

    def test_returns_folder_based_strategies(self, monkeypatch, tmp_path):
        """Folder-based strategies appear after the builtin entry."""
        strat_dir = tmp_path / "cti-v1-pullback"
        strat_dir.mkdir()
        (strat_dir / "strategy.json").write_text(
            json.dumps({
                "id": "CTI-v1.2-pullback",
                "label": "Pullback (CTI v1.2)",
                "description": "Test pullback strategy",
                "signal_type": "pullback",
            })
        )
        monkeypatch.setenv("STRATEGIES_DIR", str(tmp_path))

        result = get_strategies()

        assert result[0]["id"] == "CTI-v1"
        assert result[1]["id"] == "CTI-v1.2-pullback"
        assert result[1]["label"] == "Pullback (CTI v1.2)"
        assert result[1]["source"] == "folder"
        assert result[1]["warning"] is None

    def test_returns_warnings_for_malformed_folders(self, monkeypatch, tmp_path):
        """Folders with missing or malformed metadata include warnings in response."""
        bad_dir = tmp_path / "bad-folder"
        bad_dir.mkdir()
        (bad_dir / "strategy.json").write_text("{ broken }")

        monkeypatch.setenv("STRATEGIES_DIR", str(tmp_path))

        result = get_strategies()

        bad_entries = [r for r in result if r["id"] == "bad-folder"]
        assert len(bad_entries) == 1
        assert bad_entries[0]["warning"] is not None
        assert "malformed" in bad_entries[0]["warning"]

    def test_builtin_always_present_when_no_folders(self, monkeypatch, tmp_path):
        """Even when STRATEGIES_DIR is set to an empty directory, builtin CTI-v1 is returned."""
        # Remove STRATEGIES_DIR env var if set to avoid pollution
        monkeypatch.delenv("STRATEGIES_DIR", raising=False)
        monkeypatch.setenv("STRATEGIES_DIR", str(tmp_path))

        result = get_strategies()

        ids = [r["id"] for r in result]
        assert "CTI-v1" in ids

"""Strategy Registry — discovers strategy folders and serves metadata.

Scans a configured base directory for subfolders containing ``strategy.json``.
Each discovered strategy is returned alongside the built-in CTI-v1 entry.

Folders with missing or malformed ``strategy.json`` are included in the response
with a ``warning`` field rather than breaking the endpoint.
"""
from __future__ import annotations

import json
import logging as log
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tradegumi import config

# Built-in default/reference strategy — always present even without a folder.
BUILTIN_STRATEGY: "StrategyEntry" = {
    "id": "CTI-v1",
    "label": "CTI v1 (Default)",
    "description": "Base strategy",
    "source": "builtin",
    "warning": None,
}


@dataclass
class StrategyEntry:
    """A single strategy with its metadata and optional warning."""
    id: str
    label: str
    description: str
    source: str  # "builtin" | "folder"
    warning: Optional[str] = None


def _discover_folder_strategies(base_dir: Path) -> list[StrategyEntry]:
    """Scan ``base_dir`` for subfolders with ``strategy.json`` files.

    Returns one entry per folder. Folders without ``strategy.json`` or with
    unparseable JSON are included with a ``warning`` instead of being silently
    skipped.
    """
    strategies: list[StrategyEntry] = []

    if not base_dir.is_dir():
        log.debug("Strategy registry: base directory does not exist — %s", base_dir)
        return strategies

    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():
            continue

        metadata_path = entry / "strategy.json"
        if not metadata_path.exists():
            strategies.append(StrategyEntry(
                id=entry.name,
                label=entry.name,
                description="",
                source="folder",
                warning=f"Folder '{entry.name}' has no strategy.json",
            ))
            continue

        try:
            raw = metadata_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            strategies.append(StrategyEntry(
                id=entry.name,
                label=entry.name,
                description="",
                source="folder",
                warning=f"Folder '{entry.name}' has malformed strategy.json: {exc}",
            ))
            continue

        # Validate required fields
        strat_id = data.get("id", "")
        if not strat_id or not isinstance(strat_id, str):
            strategies.append(StrategyEntry(
                id=entry.name,
                label=entry.name,
                description="",
                source="folder",
                warning=f"Folder '{entry.name}' has strategy.json without a valid 'id' field",
            ))
            continue

        strategies.append(StrategyEntry(
            id=strat_id,
            label=data.get("label", strat_id),
            description=data.get("description", ""),
            source="folder",
            warning=None,
        ))

    return strategies


def get_strategies(strategies_dir: Optional[str] = None) -> list[dict]:
    """Return all available strategies as JSON-serialisable dicts.

    The built-in CTI-v1 entry is always first. Folder-based strategies follow
    in sorted order. Any warnings are preserved in the response so the
    dashboard can surface them without breaking the UI.
    """
    strategies_dir = strategies_dir or os.getenv("STRATEGIES_DIR", config.get_strategies_dir())
    base = Path(strategies_dir)

    folder_strategies = _discover_folder_strategies(base)
    all_strategies: list[dict] = [dict(BUILTIN_STRATEGY)]
    all_strategies.extend(s.__dict__ for s in folder_strategies)

    return all_strategies

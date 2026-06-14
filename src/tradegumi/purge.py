"""Purge utility for TradeGumi data stores.

Provides a safe way to wipe trade history, strategy metrics, and signal data
for a fresh start. Always backs up before deleting unless --no-backup is passed.

Usage:
    python -m tradegumi.purge --help
    python -m tradegumi.purge --backup-dir ~/tradegumi-backups
    python -m tradegumi.purge --force --no-backup
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tradegumi.persistence import get_db

log = logging.getLogger(__name__)

# Data directory and files (mirrors definitions in sibling modules)
DATA_DIR = Path(__file__).parent / "data"

# Files / databases that can be purged
JOURNAL_FILE = DATA_DIR / "signal_journal.jsonl"
STRATEGY_METRICS_DB = DATA_DIR / "strategy_metrics.db"
STRATEGY_METRICS_STATE = DATA_DIR / "strategy_metrics.json"
MANUAL_TRADES_DB = DATA_DIR / "manual_trades.db"
SIGNALS_FILE = DATA_DIR / "signals.json"
LOOP_STATE_FILE = DATA_DIR / "loop_state.json"
SESSION_STATE_FILE = DATA_DIR / "session_state.json"
TRADE_CORRELATIONS_FILE = DATA_DIR / "trade_correlations.json"

# Files that should NOT be purged (config-like)
PROTECTED_FILES = {
    "watchlist.json",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _backup_file(src: Path, backup_dir: Path) -> Path:
    """Copy a file to the backup directory with a timestamp suffix."""
    if not src.exists():
        return src  # nothing to back up
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / f"{src.name}.{_timestamp()}"
    shutil.copy2(src, dst)
    log.info("Backed up %s → %s", src, dst)
    return dst


def _backup_sqlite(src: Path, backup_dir: Path) -> Path:
    """Backup SQLite DB via shutil (simple copy) — assumes no concurrent writes."""
    return _backup_file(src, backup_dir)


def _truncate_postgres(tables: str) -> bool:
    """TRUNCATE the given Postgres tables (CASCADE, reset identities).

    Returns False if Postgres is unavailable so the caller can report the
    durable store was not cleared.  ``get_db()`` ensures the schema exists, so
    a missing-table error cannot occur on a configured database.
    """
    try:
        get_db().execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
        log.info("Truncated Postgres tables: %s", tables)
        return True
    except Exception as exc:
        log.error("Failed to truncate Postgres tables (%s): %s", tables, exc)
        return False


def purge_journal(*, backup_dir: Optional[Path] = None) -> bool:
    """Clear the signal journal: the JSONL audit trail and its Postgres mirror.

    Journal entries are appended to ``signal_journal.jsonl`` and synced to the
    Postgres ``journal_entries`` table, so both must be cleared for a real
    fresh start.  Success reflects whether the durable Postgres mirror was
    truncated.
    """
    if backup_dir:
        _backup_file(JOURNAL_FILE, backup_dir)
    if JOURNAL_FILE.exists():
        JOURNAL_FILE.write_text("", encoding="utf-8")
        log.info("Purged %s", JOURNAL_FILE)
    else:
        log.info("Journal file did not exist: %s", JOURNAL_FILE)
    return _truncate_postgres("journal_entries")


def purge_strategy_metrics(*, backup_dir: Optional[Path] = None) -> bool:
    """Clear strategy metrics from Postgres and reset the dashboard snapshot.

    Strategy metrics live in Postgres (``evaluated_opportunities`` and
    ``criterion_results``).  The state JSON snapshot is removed, and any leftover
    legacy SQLite database from a pre-migration install is also cleaned up.
    Success reflects whether the durable Postgres tables were truncated.
    """
    # Remove the dashboard state snapshot.
    if STRATEGY_METRICS_STATE.exists():
        if backup_dir:
            _backup_file(STRATEGY_METRICS_STATE, backup_dir)
        STRATEGY_METRICS_STATE.unlink()
        log.info("Deleted %s", STRATEGY_METRICS_STATE)
    # Clean up any leftover legacy SQLite file from before the Postgres migration.
    if STRATEGY_METRICS_DB.exists():
        if backup_dir:
            _backup_sqlite(STRATEGY_METRICS_DB, backup_dir)
        STRATEGY_METRICS_DB.unlink()
        log.info("Deleted legacy SQLite file %s", STRATEGY_METRICS_DB)
    # criterion_results is removed via ON DELETE CASCADE, but list it explicitly.
    return _truncate_postgres("criterion_results, evaluated_opportunities")


def purge_manual_trades(*, backup_dir: Optional[Path] = None) -> bool:
    """Drop and recreate the manual_trades SQLite database."""
    if backup_dir:
        _backup_sqlite(MANUAL_TRADES_DB, backup_dir)
    if MANUAL_TRADES_DB.exists():
        MANUAL_TRADES_DB.unlink()
        log.info("Deleted %s", MANUAL_TRADES_DB)
    return True


def purge_signals_state(*, backup_dir: Optional[Path] = None) -> bool:
    """Reset the current signals.json to an empty list."""
    if backup_dir:
        _backup_file(SIGNALS_FILE, backup_dir)
    SIGNALS_FILE.write_text(json.dumps([]), encoding="utf-8")
    log.info("Reset %s to []", SIGNALS_FILE)
    return True


def purge_loop_state(*, backup_dir: Optional[Path] = None) -> bool:
    """Reset loop_state.json to a minimal empty state."""
    if backup_dir:
        _backup_file(LOOP_STATE_FILE, backup_dir)
    empty = {"last_run": None, "symbols_processed": []}
    LOOP_STATE_FILE.write_text(json.dumps(empty, indent=2), encoding="utf-8")
    log.info("Reset %s", LOOP_STATE_FILE)
    return True


def purge_session_state(*, backup_dir: Optional[Path] = None) -> bool:
    """Reset session_state.json to a minimal empty state."""
    if backup_dir:
        _backup_file(SESSION_STATE_FILE, backup_dir)
    empty = {"session_id": None, "started_at": None}
    SESSION_STATE_FILE.write_text(json.dumps(empty, indent=2), encoding="utf-8")
    log.info("Reset %s", SESSION_STATE_FILE)
    return True


def purge_trade_correlations(*, backup_dir: Optional[Path] = None) -> bool:
    """Remove trade_correlations.json if it exists."""
    if backup_dir:
        _backup_file(TRADE_CORRELATIONS_FILE, backup_dir)
    if TRADE_CORRELATIONS_FILE.exists():
        TRADE_CORRELATIONS_FILE.unlink()
        log.info("Deleted %s", TRADE_CORRELATIONS_FILE)
        return True
    return False


# Map of purge targets → function
def get_purge_targets() -> dict[str, callable]:
    return {
        "journal": purge_journal,
        "strategy_metrics": purge_strategy_metrics,
        "manual_trades": purge_manual_trades,
        "signals": purge_signals_state,
        "loop_state": purge_loop_state,
        "session_state": purge_session_state,
        "trade_correlations": purge_trade_correlations,
    }


def purge_all(
    *,
    backup_dir: Optional[Path] = None,
    targets: Optional[list[str]] = None,
) -> dict[str, bool]:
    """Run selected (or all) purge functions.

    Args:
        backup_dir: Directory to store backups. None = no backup.
        targets: List of target names to purge. None = purge everything.

    Returns:
        Dict mapping target name to True/False result.
    """
    all_targets = get_purge_targets()
    to_run = {k: v for k, v in all_targets.items() if targets is None or k in targets}
    results: dict[str, bool] = {}
    for name, fn in to_run.items():
        try:
            results[name] = fn(backup_dir=backup_dir)
        except Exception as exc:
            log.error("Failed to purge %s: %s", name, exc)
            results[name] = False
    return results


def _confirm(prompt: str) -> bool:
    """Ask user for confirmation in interactive mode."""
    try:
        reply = input(f"{prompt} [y/N]: ").strip().lower()
        return reply in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Purge TradeGumi trade history and metrics for a fresh start.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=DATA_DIR / "backups",
        help="Directory to store backups before purging (default: data/backups)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup (destructive — use with caution)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip interactive confirmation",
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        choices=list(get_purge_targets().keys()) + ["all"],
        default=["all"],
        help="Specific targets to purge (default: all)",
    )
    parser.add_argument(
        "--list-targets",
        action="store_true",
        help="List available purge targets and exit",
    )
    args = parser.parse_args(argv)

    if args.list_targets:
        for name in sorted(get_purge_targets().keys()):
            print(f"  {name}")
        return 0

    targets = None if "all" in args.targets else args.targets
    backup_dir = None if args.no_backup else args.backup_dir

    target_list = targets or list(get_purge_targets().keys())
    print("Targets to purge:", ", ".join(target_list))
    if backup_dir:
        print("Backup directory:", backup_dir)
    else:
        print("WARNING: No backup will be created (--no-backup specified)")

    if not args.force:
        if not _confirm("Proceed with purge?"):
            print("Aborted.")
            return 1

    results = purge_all(backup_dir=backup_dir, targets=targets)

    print("\nResults:")
    for name, ok in sorted(results.items()):
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")

    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\nFailed purges: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

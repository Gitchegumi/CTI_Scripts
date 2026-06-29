"""Strategy plugin loader — discovers and loads executable strategy folders.

TradeGumi core provides the runtime framework (market data, execution, trend /
chop / shock filters, cooldown, diagnostics, risk sizing). The *decision* logic
for a strategy lives in a self-contained folder under ``strategies/`` and is
loaded here as a plugin.

Folder contract (see ``strategies/example-strategy/``)::

    strategies/<name>/
    ├── strategy.json     # metadata (id, label, description, signal_type)
    ├── strategy.py       # exposes get_strategy() -> BaseStrategy
    ├── indicators.py     # (optional) strategy-specific indicators
    ├── management.py     # (optional) trade-management helpers
    └── tests/            # (optional) strategy-specific tests

The folder is imported as a synthetic package so intra-folder relative imports
(``from .indicators import ...``) work even when the folder name is not a valid
Python identifier (e.g. ``example-strategy``).
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import logging as log
import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Optional

from tradegumi import config

# Folder name of the bundled reference strategy, used as the runtime default.
DEFAULT_STRATEGY = os.getenv("TRADEGUMI_STRATEGY", "example-strategy")


class StrategyLoadError(RuntimeError):
    """Raised when a strategy folder cannot be discovered or imported."""


@dataclass
class StrategyContext:
    """Per-evaluation inputs handed from the runtime framework to a strategy.

    Carries everything a strategy needs to make a signal decision without
    re-fetching market data. The runtime (``SignalEngine``) is passed separately
    to ``BaseStrategy.evaluate`` so strategies can reuse shared helpers such as
    cached candle access and configured thresholds.
    """
    symbol: str
    trend: str
    candles: list                       # raw M5 candles (count=100)
    closed_window: list                 # closed candles for indicator math
    closed_candle: object               # last fully closed candle (or None)
    criteria: list = field(default_factory=list)  # pre-seeded (candle-close gate)
    trend_lr: Optional[tuple] = None    # (lr_1h, lr_15m, lr_5m) from trend filter
    raw_lr_1h: float = 0.0
    raw_lr_15m: float = 0.0
    raw_lr_5m: float = 0.0
    filtered_lr_1h: float = 0.0
    filtered_lr_15m: float = 0.0
    filtered_lr_5m: float = 0.0
    trend_changed_after_filter: bool = False
    shock_result: object = None
    allow_continuation: bool = True
    pullback_bridge_status: Optional[str] = None


@dataclass
class StrategyDecision:
    """A strategy's verdict for one evaluation.

    Mirrors the historical ``SignalEngine._get_signal`` return contract so the
    ``check_symbol`` consumer is unchanged: ``(signal, criteria, reason,
    confidence)``.
    """
    signal: object                      # tradegumi.signal_engine.Signal | None
    criteria: list
    reason: str
    confidence: Optional[float] = None

    def as_tuple(self) -> tuple:
        return self.signal, self.criteria, self.reason, self.confidence


# ── Open-trade / continuation management contract ──────────────────────────────
# A strategy owns "how continuation or management signals behave". The runtime
# (``journal``) detects a continuation against an active trade, builds a
# ``ManagedTradeContext``, calls ``strategy.manage_open_trade``, and persists the
# returned ``TradeManagementDecision`` — it never decides SL/TP changes itself.

MANAGEMENT_ACCEPTED = "accepted"
MANAGEMENT_REJECTED_DISABLED = "management_disabled"
MANAGEMENT_REJECTED_INSUFFICIENT_PROGRESS = "insufficient_progress"
MANAGEMENT_REJECTED_RISK_INCREASE = "risk_increase"
MANAGEMENT_REJECTED_EXTENSION_CAP = "extension_cap_reached"
MANAGEMENT_REJECTED_DUPLICATE_EVENT = "duplicate_management_event"
MANAGEMENT_REJECTED_MISSING_CONTEXT = "missing_management_context"
MANAGEMENT_NOT_IMPLEMENTED = "management_not_implemented"


@dataclass
class ManagedTradeContext:
    """Journal-free inputs a strategy needs to manage one active trade.

    The runtime builds this from its persisted trade row + the continuation
    signal, so the strategy decides SL/TP changes from clean numbers without
    knowing anything about journal storage.
    """
    direction: str                      # normalized "BUY" / "SELL"
    entry_price: Optional[float]
    current_stop_loss: Optional[float]
    current_take_profit: Optional[float]
    risk_at_entry: Optional[float]
    price_at_event: Optional[float]
    tp_extension_count: int = 0
    already_seen: bool = False          # this continuation already managed the trade


@dataclass(frozen=True)
class TradeManagementDecision:
    """A strategy's verdict for one continuation against an active trade."""

    accepted: bool
    reason: str
    rejection_reason: Optional[str]
    old_stop_loss: Optional[float]
    new_stop_loss: Optional[float]
    old_take_profit: Optional[float]
    new_take_profit: Optional[float]
    price_at_event: Optional[float]
    tp_extended: bool = False
    sl_tightened: bool = False
    break_even_moved: bool = False


@dataclass
class StrategyValidation:
    """Result of validating one strategy folder against the plugin contract."""
    folder: str
    id: Optional[str]
    ok: bool
    error: Optional[str] = None


class BaseStrategy(ABC):
    """Contract every strategy plugin implements.

    Concrete strategies live in ``strategies/<name>/strategy.py`` and are
    instantiated by a module-level ``get_strategy()`` factory.
    """

    #: Stable identifier (matches ``strategy.json``'s ``id``).
    id: str = ""
    #: Parsed ``strategy.json`` contents.
    metadata: dict = {}

    @abstractmethod
    def evaluate(self, engine, ctx: "StrategyContext") -> "StrategyDecision":
        """Run the strategy's decision logic and return a StrategyDecision."""
        raise NotImplementedError

    def bridge_trend(
        self,
        engine,
        lr_1h: float,
        lr_15m: float,
        candles_15m: list,
    ) -> tuple[Optional[str], Optional[dict]]:
        """Optionally salvage a directional bias when the trend filter is flat.

        Returns ``(chosen_trend, bridge_result)`` or ``(None, None)`` when no
        bridge applies. Default: no bridging.
        """
        return None, None

    def manage_open_trade(self, ctx: "ManagedTradeContext") -> "TradeManagementDecision":
        """Decide SL/TP changes for an active trade given a continuation signal.

        Strategies that manage open trades (e.g. break-even / profit-protect /
        TP-extension on continuation) override this. The default declines, so a
        strategy that only emits entries still loads and runs unchanged.
        """
        return TradeManagementDecision(
            accepted=False,
            reason=MANAGEMENT_NOT_IMPLEMENTED,
            rejection_reason=MANAGEMENT_NOT_IMPLEMENTED,
            old_stop_loss=ctx.current_stop_loss,
            new_stop_loss=ctx.current_stop_loss,
            old_take_profit=ctx.current_take_profit,
            new_take_profit=ctx.current_take_profit,
            price_at_event=ctx.price_at_event,
        )


def _synthetic_pkg_name(folder: Path) -> str:
    """Deterministic, import-safe package name for a strategy folder."""
    return "cti_strategy_" + re.sub(r"\W", "_", folder.name)


def load_strategy_module(folder: Path) -> ModuleType:
    """Import ``<folder>/strategy.py`` as a synthetic package submodule.

    The folder is registered as a package whose ``__path__`` points at itself,
    so the strategy's relative imports resolve to its own siblings and stay
    isolated from other strategies.
    """
    folder = Path(folder).resolve()
    strategy_path = folder / "strategy.py"
    if not strategy_path.exists():
        raise StrategyLoadError(f"strategy folder has no strategy.py: {folder}")

    pkg_name = _synthetic_pkg_name(folder)
    mod_name = f"{pkg_name}.strategy"

    # Reuse an already-imported strategy module so its namespace (and any test
    # monkeypatches applied to it) is shared by every consumer of this folder.
    existing = sys.modules.get(mod_name)
    if existing is not None:
        return existing

    if pkg_name not in sys.modules:
        pkg_spec = importlib.machinery.ModuleSpec(pkg_name, None, is_package=True)
        pkg = importlib.util.module_from_spec(pkg_spec)
        pkg.__path__ = [str(folder)]
        sys.modules[pkg_name] = pkg

    spec = importlib.util.spec_from_file_location(mod_name, strategy_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _resolve_folder(base: Path, strategy_id: Optional[str]) -> Path:
    """Find the strategy folder by folder name or by ``strategy.json`` id."""
    if not base.is_dir():
        raise StrategyLoadError(f"strategies directory does not exist: {base}")

    name = strategy_id or DEFAULT_STRATEGY

    # 1. Direct folder-name match.
    direct = base / name
    if direct.is_dir():
        return direct

    # 2. Match by the ``id`` field inside each folder's strategy.json.
    for entry in sorted(base.iterdir()):
        meta = entry / "strategy.json"
        if entry.is_dir() and meta.exists():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if data.get("id") == name:
                return entry

    raise StrategyLoadError(f"strategy not found: {name} (under {base})")


def load_strategy(
    strategy_id: Optional[str] = None,
    strategies_dir: Optional[str] = None,
) -> BaseStrategy:
    """Discover and instantiate a strategy plugin.

    Defaults to the bundled ``example-strategy`` reference when no id is given.
    """
    base = Path(strategies_dir or config.get_strategies_dir())
    folder = _resolve_folder(base, strategy_id)
    module = load_strategy_module(folder)

    factory = getattr(module, "get_strategy", None)
    if not callable(factory):
        raise StrategyLoadError(
            f"{folder / 'strategy.py'} does not expose a get_strategy() factory"
        )
    strategy = factory()
    if not isinstance(strategy, BaseStrategy):
        raise StrategyLoadError(
            f"get_strategy() in {folder} did not return a BaseStrategy"
        )
    log.debug("Loaded strategy '%s' from %s", getattr(strategy, "id", "?"), folder)
    return strategy


def _looks_like_strategy_folder(entry: Path) -> bool:
    """A subfolder is a strategy candidate if it has strategy.py or strategy.json."""
    return (entry / "strategy.py").exists() or (entry / "strategy.json").exists()


def discover_strategies(strategies_dir: Optional[str] = None) -> list[StrategyValidation]:
    """Discover every strategy folder and validate it implements the contract.

    Unlike ``strategy_registry`` (which only reads ``strategy.json`` metadata for
    the dashboard dropdown), this actually loads each folder and confirms it
    exposes a ``get_strategy()`` factory returning a ``BaseStrategy``. Each folder
    is reported as ``ok`` or with a useful ``error`` — one bad folder never breaks
    discovery of the others.
    """
    base = Path(strategies_dir or config.get_strategies_dir())
    results: list[StrategyValidation] = []
    if not base.is_dir():
        log.debug("Strategy discovery: base directory does not exist — %s", base)
        return results

    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or not _looks_like_strategy_folder(entry):
            continue
        try:
            strategy = load_strategy(entry.name, strategies_dir=str(base))
            results.append(StrategyValidation(entry.name, getattr(strategy, "id", None), True))
        except StrategyLoadError as exc:
            results.append(StrategyValidation(entry.name, None, False, str(exc)))
        except Exception as exc:  # import errors, bad factories, etc.
            results.append(
                StrategyValidation(entry.name, None, False, f"{type(exc).__name__}: {exc}")
            )
    return results


def default_strategy_module() -> ModuleType:
    """Return the imported module object for the default strategy.

    Useful for tests that need to monkeypatch indicator functions in the
    strategy's own namespace.
    """
    base = Path(config.get_strategies_dir())
    folder = _resolve_folder(base, None)
    return load_strategy_module(folder)

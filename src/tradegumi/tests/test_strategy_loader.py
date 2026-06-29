"""Tests for the strategy plugin loader and discovery from ``strategies/``."""
from pathlib import Path

import pytest

from tradegumi import config
from tradegumi.strategy_loader import (
    MANAGEMENT_ACCEPTED,
    MANAGEMENT_NOT_IMPLEMENTED,
    MANAGEMENT_REJECTED_DISABLED,
    MANAGEMENT_REJECTED_DUPLICATE_EVENT,
    MANAGEMENT_REJECTED_EXTENSION_CAP,
    MANAGEMENT_REJECTED_MISSING_CONTEXT,
    MANAGEMENT_REJECTED_RISK_INCREASE,
    BaseStrategy,
    ManagedTradeContext,
    StrategyLoadError,
    discover_strategies,
    load_strategy,
    load_strategy_module,
)


def test_load_default_example_strategy():
    """The bundled example-strategy loads as an executable BaseStrategy."""
    strategy = load_strategy()
    assert isinstance(strategy, BaseStrategy)
    assert strategy.id == "example-pullback"
    assert strategy.metadata.get("signal_type") == "pullback"
    assert hasattr(strategy, "evaluate")
    assert callable(strategy.evaluate)


def test_load_strategy_by_id():
    """A strategy can be resolved by its strategy.json id, not just folder name."""
    strategy = load_strategy("example-pullback")
    assert strategy.id == "example-pullback"


def test_signal_engine_wires_default_strategy():
    """SignalEngine loads the default strategy at construction."""
    from tradegumi.signal_engine import SignalEngine

    class _FakeClient:
        def get_candles(self, *a, **k):
            return []

        def get_pricing(self, *a, **k):
            return {}

        def get_account_balance(self):
            return 0.0

        def get_open_positions(self):
            return []

        def place_order(self, order):
            return None

        def get_trade_history(self, count=50):
            return []

    engine = SignalEngine(_FakeClient(), {"EURUSD"})
    assert isinstance(engine.strategy, BaseStrategy)
    assert engine.strategy.id == "example-pullback"


def test_explicit_strategy_overrides_default():
    """An explicitly supplied strategy is used instead of the default."""
    from tradegumi.signal_engine import SignalEngine

    sentinel = load_strategy()
    engine = SignalEngine.__new__(SignalEngine)  # avoid full init/client
    # The constructor accepts a strategy override; verify it is stored verbatim.
    SignalEngine.__init__(engine, client=_DummyClient(), strategy=sentinel)
    assert engine.strategy is sentinel


class _DummyClient:
    def get_candles(self, *a, **k):
        return []

    def get_pricing(self, *a, **k):
        return {}

    def get_account_balance(self):
        return 0.0

    def get_open_positions(self):
        return []

    def place_order(self, order):
        return None

    def get_trade_history(self, count=50):
        return []


def test_missing_strategy_raises(tmp_path):
    """Requesting an unknown strategy id raises a clear error."""
    with pytest.raises(StrategyLoadError):
        load_strategy("does-not-exist", strategies_dir=str(tmp_path))


def test_folder_without_strategy_py_raises(tmp_path):
    """A folder lacking strategy.py cannot be loaded as a plugin."""
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "strategy.json").write_text('{"id": "broken"}', encoding="utf-8")
    with pytest.raises(StrategyLoadError):
        load_strategy("broken", strategies_dir=str(tmp_path))


def test_factory_must_return_base_strategy(tmp_path):
    """get_strategy() returning a non-BaseStrategy is rejected."""
    folder = tmp_path / "bad"
    folder.mkdir()
    (folder / "strategy.json").write_text('{"id": "bad"}', encoding="utf-8")
    (folder / "strategy.py").write_text(
        "def get_strategy():\n    return object()\n", encoding="utf-8"
    )
    with pytest.raises(StrategyLoadError):
        load_strategy("bad", strategies_dir=str(tmp_path))


def test_example_strategy_dir_is_discoverable():
    """The reference strategy lives under the configured strategies directory."""
    base = Path(config.get_strategies_dir())
    assert (base / "example-strategy" / "strategy.py").exists()
    module = load_strategy_module(base / "example-strategy")
    assert hasattr(module, "get_strategy")


# ── Discovery / interface validation (issue #168) ──────────────────────────────


def test_discover_strategies_reports_both_reference_strategies():
    """Both bundled strategies are discovered and validated against the contract."""
    results = {r.folder: r for r in discover_strategies()}
    assert results["example-strategy"].ok is True
    assert results["example-strategy"].id == "example-pullback"
    assert results["macd-momentum"].ok is True
    assert results["macd-momentum"].id == "macd-momentum"


def test_two_strategies_load_without_core_edits():
    """At least two strategies load through the same contract — no core changes."""
    example = load_strategy("example-pullback")
    macd = load_strategy("macd-momentum")
    assert isinstance(example, BaseStrategy) and isinstance(macd, BaseStrategy)
    assert example.id != macd.id


def test_discover_reports_invalid_folder_without_breaking_others(tmp_path):
    """A broken folder is reported with an error; valid siblings still validate."""
    good = tmp_path / "good"
    good.mkdir()
    (good / "strategy.json").write_text('{"id": "good"}', encoding="utf-8")
    (good / "strategy.py").write_text(
        "from tradegumi.strategy_loader import BaseStrategy, StrategyDecision\n"
        "class S(BaseStrategy):\n"
        "    id = 'good'\n"
        "    def evaluate(self, engine, ctx):\n"
        "        return StrategyDecision(None, [], 'noop', None)\n"
        "def get_strategy():\n    return S()\n",
        encoding="utf-8",
    )
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "strategy.json").write_text('{"id": "bad"}', encoding="utf-8")
    (bad / "strategy.py").write_text("def get_strategy():\n    return object()\n", encoding="utf-8")

    results = {r.folder: r for r in discover_strategies(strategies_dir=str(tmp_path))}
    assert results["good"].ok is True
    assert results["bad"].ok is False
    assert results["bad"].error


# ── manage_open_trade contract (issue #168) ────────────────────────────────────


def test_manage_open_trade_default_declines():
    """A strategy that does not manage trades uses the safe default (declines)."""
    strategy = load_strategy("macd-momentum")
    ctx = ManagedTradeContext(
        direction="BUY", entry_price=1.1, current_stop_loss=1.098,
        current_take_profit=1.104, risk_at_entry=0.002, price_at_event=1.1022,
    )
    decision = strategy.manage_open_trade(ctx)
    assert decision.accepted is False
    assert decision.reason == MANAGEMENT_NOT_IMPLEMENTED
    assert decision.new_stop_loss == 1.098


def _be_context(**overrides) -> ManagedTradeContext:
    base = dict(
        direction="BUY", entry_price=1.1000, current_stop_loss=1.0980,
        current_take_profit=1.1040, risk_at_entry=0.0020, price_at_event=1.1022,
        tp_extension_count=0, already_seen=False,
    )
    base.update(overrides)
    return ManagedTradeContext(**base)


def test_example_manage_open_trade_accepts_and_moves_to_break_even(monkeypatch):
    """Sufficient progress moves SL to break-even and extends the target."""
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_ENABLED", True)
    strategy = load_strategy("example-pullback")
    decision = strategy.manage_open_trade(_be_context())
    assert decision.accepted is True
    assert decision.reason == MANAGEMENT_ACCEPTED
    assert decision.new_stop_loss == 1.1000  # break-even
    assert decision.tp_extended is True


def test_example_manage_open_trade_rejects_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_ENABLED", False)
    strategy = load_strategy("example-pullback")
    decision = strategy.manage_open_trade(_be_context())
    assert decision.accepted is False
    assert decision.rejection_reason == MANAGEMENT_REJECTED_DISABLED


def test_example_manage_open_trade_rejects_duplicate(monkeypatch):
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_ENABLED", True)
    strategy = load_strategy("example-pullback")
    decision = strategy.manage_open_trade(_be_context(already_seen=True))
    assert decision.rejection_reason == MANAGEMENT_REJECTED_DUPLICATE_EVENT


def test_example_manage_open_trade_rejects_missing_context(monkeypatch):
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_ENABLED", True)
    strategy = load_strategy("example-pullback")
    decision = strategy.manage_open_trade(_be_context(risk_at_entry=None))
    assert decision.rejection_reason == MANAGEMENT_REJECTED_MISSING_CONTEXT


def test_example_manage_open_trade_rejects_risk_increase(monkeypatch):
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_ENABLED", True)
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_BE_TRIGGER_R", 1.0)
    strategy = load_strategy("example-pullback")
    # SL already past break-even — moving to BE would loosen it.
    decision = strategy.manage_open_trade(_be_context(current_stop_loss=1.1010))
    assert decision.rejection_reason == MANAGEMENT_REJECTED_RISK_INCREASE


def test_example_manage_open_trade_rejects_extension_cap(monkeypatch):
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_ENABLED", True)
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_BE_TRIGGER_R", 1.0)
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_PROFIT_PROTECT_TRIGGER_R", 99.0)
    monkeypatch.setattr(config, "CONTINUATION_MANAGEMENT_MAX_TP_EXTENSIONS", 0)
    strategy = load_strategy("example-pullback")
    # SL already at break-even (== entry) so no new SL, and extensions capped.
    decision = strategy.manage_open_trade(_be_context(current_stop_loss=1.1000))
    assert decision.rejection_reason == MANAGEMENT_REJECTED_EXTENSION_CAP

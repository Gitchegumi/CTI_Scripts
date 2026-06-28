"""Tests for the strategy plugin loader and discovery from ``strategies/``."""
from pathlib import Path

import pytest

from tradegumi import config
from tradegumi.strategy_loader import (
    BaseStrategy,
    StrategyLoadError,
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

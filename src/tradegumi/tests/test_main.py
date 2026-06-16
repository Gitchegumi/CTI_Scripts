"""Unit tests for main.check_and_execute around the orphan continuation suppression surface."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from tradegumi.signal_engine import Signal, SignalDiagnostic
from tradegumi.main import check_and_execute, OandaClient, MatchTraderClient


def _make_signal(signal_type="pullback", direction="BUY"):
    return Signal(
        symbol="EURUSD",
        direction=direction,
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1200,
        atr=0.0010,
        lot_size=1000,
        risk_pct=0.25,
        confidence=0.72,
        breakdown={"stoch_rsi": 0.8, "keltner": 0.7},
        trend_direction="Uptrend",
        patterns_found=[],
        strategy="CTI-v1.2-pullback",
        signal_type=signal_type,
    )


def _make_diagnostic():
    return SignalDiagnostic(
        symbol="EURUSD",
        evaluated_at=datetime.utcnow().isoformat(),
        trend="Uptrend",
        lr_1h=0.5,
        lr_15m=0.3,
        lr_5m=0.1,
        final_decision="approved",
        decision_reason="tests",
    )


def _stub_engine(signal, trend="Uptrend", lr_1h=0.5, lr_15m=0.3, lr_5m=0.1, diagnostic=None):
    engine = MagicMock()
    engine.check_symbol.return_value = (
        signal,
        trend,
        lr_1h,
        lr_15m,
        lr_5m,
        diagnostic or _make_diagnostic(),
    )
    return engine


def test_suppressed_continuation_skips_callback_and_place_order(monkeypatch):
    """An orphan continuation must not alert, callback, or place orders."""
    signal = _make_signal(signal_type="continuation", direction="BUY")
    engine = _stub_engine(signal)
    client = MagicMock(spec=OandaClient)
    client.get_account_balance.return_value = 10000.0
    trailing = MagicMock()

    calls = {"callback": False, "post": False}

    def fake_post_signal(s):
        calls["post"] = True
        return {"ok": True, "suppressed": True}

    def fake_send_callback(payload):
        calls["callback"] = True

    monkeypatch.setattr("tradegumi.main.post_signal", fake_post_signal)
    monkeypatch.setattr("tradegumi.main.send_signal_callback", fake_send_callback)
    monkeypatch.setattr("tradegumi.main.is_trading_open", lambda s: True)
    monkeypatch.setattr("tradegumi.main.is_swap_blackout", lambda s: False)
    monkeypatch.setattr("tradegumi.main.can_open_position", lambda c: (True, ""))
    monkeypatch.setattr(
        "tradegumi.main.config",
        MagicMock(TRADEGUMI_MODE="demo", TRADEGUMI_RISK_PER_TRADE=0.25),
    )

    tag, *_ = check_and_execute(engine, client, "EURUSD", "demo", trailing)

    assert tag == "B(suppressed)"
    assert calls["post"] is True
    assert calls["callback"] is False
    client.place_order.assert_not_called()


def test_normal_pullback_alerts_and_executes(monkeypatch):
    """A normal pullback signal should callback and place an order in demo mode."""
    signal = _make_signal(signal_type="pullback", direction="BUY")
    engine = _stub_engine(signal)
    client = MagicMock(spec=OandaClient)
    client.get_account_balance.return_value = 10000.0
    trailing = MagicMock()

    calls = {"callback": False, "post": False}

    def fake_post_signal(s):
        calls["post"] = True
        return {"ok": True, "suppressed": False}

    def fake_send_callback(payload):
        calls["callback"] = True

    monkeypatch.setattr("tradegumi.main.post_signal", fake_post_signal)
    monkeypatch.setattr("tradegumi.main.send_signal_callback", fake_send_callback)
    monkeypatch.setattr("tradegumi.main.is_trading_open", lambda s: True)
    monkeypatch.setattr("tradegumi.main.is_swap_blackout", lambda s: False)
    monkeypatch.setattr("tradegumi.main.can_open_position", lambda c: (True, ""))
    monkeypatch.setattr(
        "tradegumi.main.config",
        MagicMock(TRADEGUMI_MODE="demo", TRADEGUMI_RISK_PER_TRADE=0.25),
    )

    tag, *_ = check_and_execute(engine, client, "EURUSD", "demo", trailing)

    assert tag == "B(conf=0.72)"
    assert calls["post"] is True
    assert calls["callback"] is True
    client.place_order.assert_called_once()


def test_risk_blocked_signal_still_callbacks_but_does_not_execute(monkeypatch):
    """Risk-blocked signal is posted for the block reason but never executed."""
    signal = _make_signal(signal_type="pullback", direction="BUY")
    engine = _stub_engine(signal)
    client = MagicMock(spec=OandaClient)
    client.get_account_balance.return_value = 10000.0
    trailing = MagicMock()

    calls = {"callback": False, "post": False}

    def fake_post_signal(s):
        calls["post"] = True
        return {"ok": True, "suppressed": False}

    def fake_send_callback(payload):
        calls["callback"] = True

    monkeypatch.setattr("tradegumi.main.post_signal", fake_post_signal)
    monkeypatch.setattr("tradegumi.main.send_signal_callback", fake_send_callback)
    monkeypatch.setattr("tradegumi.main.is_trading_open", lambda s: True)
    monkeypatch.setattr("tradegumi.main.is_swap_blackout", lambda s: False)
    monkeypatch.setattr("tradegumi.main.can_open_position", lambda c: (False, "max_exposure"))
    monkeypatch.setattr(
        "tradegumi.main.config",
        MagicMock(TRADEGUMI_MODE="demo", TRADEGUMI_RISK_PER_TRADE=0.25),
    )

    tag, *_ = check_and_execute(engine, client, "EURUSD", "demo", trailing)

    assert tag == "B(blocked)"
    assert calls["post"] is True
    assert calls["callback"] is True
    client.place_order.assert_not_called()

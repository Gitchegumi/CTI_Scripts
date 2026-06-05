from tradegumi.alerts import format_signal_message
from tradegumi.signal_engine import Signal


def test_format_signal_message_includes_pullback_strategy_and_type():
    signal = Signal(
        symbol="EURUSD",
        direction="BUY",
        entry_price=1.1000,
        stop_loss=1.0970,
        take_profit=1.1120,
        atr=0.0010,
        lot_size=1000,
        risk_pct=0.25,
        confidence=0.72,
        breakdown={"stoch_rsi": 0.8, "keltner": 0.7},
        trend_direction="Uptrend",
        patterns_found=[],
        strategy="CTI-v1.2-pullback",
        signal_type="pullback",
    )

    payload = format_signal_message(signal)
    fields = {field["name"]: field["value"] for field in payload["embeds"][0]["fields"]}

    assert fields["Strategy"] == "CTI-v1.2-pullback"
    assert fields["Signal Type"] == "pullback"

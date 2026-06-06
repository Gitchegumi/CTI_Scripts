# Quickstart: High-Value KC Band Pullbacks

This guide describes how to verify the high-value KC band pullback strategy implementation.

## Prerequisites

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
# Or if using poetry:
poetry install
```

## Running Verification Tests

Run the test suite to verify the new high-value pullback conditions work as expected:

```bash
pytest src/tradegumi/tests/test_signal_engine.py
```

### Verifying High-Value Pullbacks

We have added test scenarios covering:
1. **Valid high-value pullback (outside KC band)**:
   - Price breaks outer band, stays outside KC band, MACD histogram matches trend direction, Stoch RSI/structure/trigger candle shapes pass. -> Emits `high_value_pullback` signal.
2. **Valid high-value pullback (inside outer band but before midline)**:
   - Price breaks outer band, retraces inside outer band but does not reach midline, MACD histogram matches trend direction, Stoch RSI/structure/trigger candle shapes pass. -> Emits `high_value_pullback` signal.
3. **Invalid MACD histogram**:
   - Same price setups as above, but MACD histogram does not match trend direction (e.g., histogram >= 0 for Downtrend). -> Rejected, no signal emitted.
4. **Regression test**:
   - Standard midline pullbacks continue to trigger standard `pullback` signals.

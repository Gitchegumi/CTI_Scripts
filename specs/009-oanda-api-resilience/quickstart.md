# Quickstart: Validate OANDA API resilience

## Focused Tests

Run OANDA client tests:

```powershell
pytest src/tradegumi/tests/test_oanda_client.py
```

Run signal diagnostics tests:

```powershell
$env:NUMBA_DISABLE_JIT='1'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; pytest src/tradegumi/tests/test_signal_engine.py
```

Run metrics tests:

```powershell
$env:NUMBA_DISABLE_JIT='1'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; pytest src/tradegumi/tests/test_strategy_metrics.py
```

Run combined focused validation:

```powershell
$env:NUMBA_DISABLE_JIT='1'; $env:PYTEST_ADDOPTS='-p no:cacheprovider'; pytest src/tradegumi/tests/test_oanda_client.py src/tradegumi/tests/test_signal_engine.py src/tradegumi/tests/test_strategy_metrics.py
```

## Manual Audit Checklist

1. Confirm OANDA base URLs normalize trailing slashes.
2. Confirm candle fetch URL is `/v3/instruments/{instrument}/candles` with `price=M`.
3. Confirm pricing, account, position, trade, and order paths match `contracts/oanda-v20-endpoints.md`.
4. Simulate 504, 429, 500, 502, and 503 responses and verify retries occur.
5. Simulate a repeated 504 and verify the final signal diagnostic is indeterminate, provider-specific, and not a strategy rejection.
6. Simulate incomplete candles and verify signal indicators are built only from complete candles.
7. Simulate transaction-based order creation responses and verify parsing does not require a top-level `order`.

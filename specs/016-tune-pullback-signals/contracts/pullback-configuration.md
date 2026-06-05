# Contract: Pullback Configuration

## Purpose

All material pullback tuning behavior must be configurable without code changes and included in threshold-version diagnostics when it affects signal decisions.

## Existing Settings To Preserve

- `PULLBACK_ENABLED`
- `PULLBACK_15M_MEMORY_CANDLES`
- `PULLBACK_15M_STRONG_OPPOSITE_MULTIPLIER`
- `PULLBACK_REQUIRE_1H_ALIGNMENT`
- `PULLBACK_STRUCTURE_LOOKBACK_BARS`
- `PULLBACK_KC_BREAK_LOOKBACK_BARS`
- `PULLBACK_KC_MIDLINE_TOLERANCE_ATR`
- `PULLBACK_KC_MIDLINE_TOLERANCE_CHANNEL_WIDTH`
- `PULLBACK_STOCH_OVERSOLD`
- `PULLBACK_STOCH_OVERSOLD_RECENT`
- `PULLBACK_STOCH_OVERBOUGHT`
- `PULLBACK_STOCH_OVERBOUGHT_RECENT`

## New Or Verified Settings

| Setting | Default Intent | Decision Impact |
| --- | --- | --- |
| `PULLBACK_TRIGGER_MAX_BODY_RANGE_RATIO` | Accept small-body rejection candles around 0.33 or lower | Hard gate |
| `PULLBACK_TRIGGER_MIN_REJECTION_WICK_RANGE_RATIO` | Require meaningful direction-side wick | Hard gate |
| `PULLBACK_TRIGGER_MIN_REJECTION_WICK_BODY_RATIO` | Ensure wick is materially larger than body | Hard gate |
| `PULLBACK_STOCH_MEMORY_BARS` | Configure recent exhaustion memory window | Hard gate |
| `PULLBACK_MACD_HARD_BLOCK_ENABLED` | `false` by default | Hard gate only when enabled |

## Requirements

- Each setting must be read from environment-backed config.
- `.env.example` must document each new setting with conservative defaults.
- `get_threshold_version()` or equivalent threshold hashing must include each setting that changes signal qualification.
- Invalid values must fail safely or normalize conservatively.
- Defaults must not make MACD a hard blocker for pullbacks.

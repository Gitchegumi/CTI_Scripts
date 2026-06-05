# Contract: Signal Diagnostics

## Purpose

Every evaluated pullback candidate must produce stable, reportable diagnostic criteria so issue #99 can be measured before and after tuning.

## Required Criterion Names

- `pullback_15m_bridge`
- `pullback_structure`
- `keltner_pullback_sequence`
- `pullback_trigger_candle`
- `stoch_rsi`
- `macd_soft_score`
- `pullback_macd_hard_block` when hard-block mode is enabled

## Required Reason Names

- `pullback_1h_anchor_failed`
- `pullback_15m_bridge_allowed`
- `pullback_15m_bridge_strong_opposite`
- `pullback_structure_failed`
- `pullback_kc_sequence_failed`
- `pullback_trigger_candle_failed`
- `pullback_trigger_hammer`
- `pullback_trigger_shooting_star`
- `pullback_trigger_bullish_engulfing`
- `pullback_trigger_bearish_engulfing`
- `pullback_stoch_rsi_failed`
- `pullback_macd_soft_score`
- `pullback_macd_hard_block_failed`

## Trigger Context Fields

- `pattern`
- `body_to_range`
- `upper_wick`
- `lower_wick`
- `rejection_wick_ratio`
- `rejection_wick_body_ratio`
- `close_position`
- `value_area_relation`
- `passed`
- `reason`

## Value-Area Context Fields

- `prior_break`
- `near_midline`
- `trigger_close`
- `midline`
- `distance_to_midline`
- `tolerance`
- `tolerance_atr_component`
- `tolerance_channel_component`
- `passed`
- `reason`

## Exhaustion Context Fields

- `k`
- `d`
- `recent_low` for BUY candidates
- `recent_high` for SELL candidates
- `memory_bars`
- `recovery_or_roll_down`
- `passed`
- `reason`

## Behavior

- Required criteria that fail must mark the opportunity as rejected.
- Soft MACD criteria must not mark the opportunity rejected unless explicit hard-block mode is enabled.
- The first blocker or blocker category must be stable enough for metrics aggregation.
- Emitted pullback opportunities must carry `strategy=CTI-v1.2-pullback` and `signal_type=pullback`.

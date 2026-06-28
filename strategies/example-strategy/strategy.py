"""Example strategy — CTI pullback with continuation management.

This is the reference TradeGumi strategy plugin. It owns the signal *decision*
logic (the 4-layer signal stack and the continuation/pullback dual path); the
TradeGumi runtime (``tradegumi.signal_engine.SignalEngine``) owns the framework
around it (market data, trend/chop/shock filters, cooldown, diagnostics).

Copy this whole folder to create a new strategy — see ``README.md``.
"""
from __future__ import annotations

import json
import logging as log
from pathlib import Path

import pandas as pd

from tradegumi import config
from tradegumi.indicators import (
    calculate_stoch_rsi,
    calculate_macd,
    calculate_keltner_channels,
    calculate_candlestick_patterns,
    calculate_linear_regression,
    calculate_atr,
    stoch_rsi_score,
    macd_histogram_score,
    keltner_score,
    candlestick_score,
    trend_score,
    candles_to_df,
)
from tradegumi.signal_engine import (
    Signal,
    CONTINUATION_STRATEGY_VERSION,
    PULLBACK_STRATEGY_VERSION,
    _criterion,
    _first_matching_column,
    _live_trigger_price,
    _price_decimals,
    _signal_data_not_ready_criterion,
    _signal_readiness_issue,
    _signal_window_issue,
    _usable_indicator_window,
)
from tradegumi.strategy_loader import BaseStrategy, StrategyContext, StrategyDecision

from .indicators import (
    classify_pullback_trend_bridge,
    pullback_keltner_sequence,
    pullback_stoch_rsi,
    pullback_structure,
    pullback_trigger,
)
from .management import (
    MIN_CONFIDENCE,
    compute_sl_tp,
    continuation_confidence,
    pullback_confidence,
)

_METADATA_PATH = Path(__file__).resolve().parent / "strategy.json"


def _load_metadata() -> dict:
    try:
        return json.loads(_METADATA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


class PullbackStrategy(BaseStrategy):
    """CTI pullback strategy with continuation management."""

    def __init__(self) -> None:
        self.metadata = _load_metadata()
        self.id = self.metadata.get("id", "example-pullback")

    # ── Trend bridge hook ─────────────────────────────────────────────────────
    def bridge_trend(self, engine, lr_1h, lr_15m, candles_15m):
        """Salvage a directional bias from recent M15 memory during a pullback."""
        if not config.PULLBACK_ENABLED:
            return None, None
        try:
            df_15_for_bridge = candles_to_df(candles_15m)
            lr_15_series = calculate_linear_regression(df_15_for_bridge, length=25)
            recent_lr_15 = lr_15_series.dropna().iloc[-config.PULLBACK_15M_MEMORY_CANDLES:].tolist()
        except (IndexError, KeyError, ValueError):
            recent_lr_15 = []
        for candidate_trend in ("Uptrend", "Downtrend"):
            bridge = classify_pullback_trend_bridge(
                lr_1h,
                lr_15m,
                recent_lr_15,
                candidate_trend,
                engine.LR_1H_THRESHOLD,
                engine.LR_15M_THRESHOLD,
                memory_candles=config.PULLBACK_15M_MEMORY_CANDLES,
                strong_opposite_multiplier=config.PULLBACK_15M_STRONG_OPPOSITE_MULTIPLIER,
            )
            if bridge["passed"]:
                return candidate_trend, bridge
        return None, None

    # ── Signal decision ───────────────────────────────────────────────────────
    def evaluate(self, engine, ctx: StrategyContext) -> StrategyDecision:
        symbol = ctx.symbol
        trend = ctx.trend
        candles = ctx.candles
        closed_window = ctx.closed_window
        closed_candle = ctx.closed_candle
        criteria = ctx.criteria
        trend_lr = ctx.trend_lr
        raw_lr_1h = ctx.raw_lr_1h
        raw_lr_15m = ctx.raw_lr_15m
        raw_lr_5m = ctx.raw_lr_5m
        filtered_lr_1h = ctx.filtered_lr_1h
        filtered_lr_15m = ctx.filtered_lr_15m
        filtered_lr_5m = ctx.filtered_lr_5m
        trend_changed_after_filter = ctx.trend_changed_after_filter
        shock_result = ctx.shock_result
        allow_continuation = ctx.allow_continuation
        pullback_bridge_status = ctx.pullback_bridge_status

        # ── Layer 1: StochRSI ────────────────────────────────────────────────
        window_issue = _signal_window_issue(closed_window, engine.SIGNAL_WINDOW_MIN_CANDLES)
        if window_issue:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=engine.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=engine.SIGNAL_INDICATOR_MIN_WINDOW,
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return StrategyDecision(None, criteria, "signal_stack_data_not_ready", None)

        df = candles_to_df(closed_window)
        df.index = pd.DatetimeIndex([candle.time for candle in closed_window])
        stoch = calculate_stoch_rsi(df, length=14, k=3, d=3)
        k_col = _first_matching_column(stoch, lambda name: "k" in name, "stoch_rsi_k")
        d_col = _first_matching_column(stoch, lambda name: "d" in name, "stoch_rsi_d")
        stoch, stoch_available, stoch_ready = _usable_indicator_window(
            stoch,
            [k_col, d_col],
            engine.SIGNAL_INDICATOR_MIN_WINDOW,
            closed_candle,
        )
        if not stoch_ready:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=engine.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=engine.SIGNAL_INDICATOR_MIN_WINDOW,
                available_indicator_window=stoch_available,
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return StrategyDecision(None, criteria, "signal_stack_data_not_ready", None)
        k = stoch[k_col].iloc[-1]
        d = stoch[d_col].iloc[-1]
        k_prev3 = stoch[k_col].iloc[-4:]

        if trend == "Uptrend":
            if config.PULLBACK_STOCH_RSI_RELAXED:
                # CTI-v1.1 pullback: allow curling up from below 40 (not strictly oversold)
                stoch_ok = (
                    (k_prev3.min() < 30 and k > d)  # strict cross from oversold
                    or (k_prev3.min() < 40 and k > d and k < 50)  # curling up from below 40
                )
            else:
                stoch_ok = k_prev3.min() < 30 and k > d
            stoch_margin = min(30 - float(k_prev3.min()), float(k - d))
        else:
            if config.PULLBACK_STOCH_RSI_RELAXED:
                # CTI-v1.1 pullback: allow rolling down from above 60 (not strictly overbought)
                stoch_ok = (
                    (k_prev3.max() > 70 and k < d)  # strict cross from overbought
                    or (k_prev3.max() > 60 and k < d and k > 50)  # rolling down from above 60
                )
            else:
                stoch_ok = k_prev3.max() > 70 and k < d
            stoch_margin = min(float(k_prev3.max()) - 70, float(d - k))

        stoch_strength = stoch_rsi_score(
            k, d, k_prev3.min(), k_prev3.max(), trend
        )

        # ── Layer 2: MACD histogram ───────────────────────────────────────────
        macd_df = calculate_macd(df, fast=12, slow=26, signal=9)
        hist_col = _first_matching_column(macd_df, lambda name: "h" in name, "macd_histogram")
        macd_line_col = _first_matching_column(
            macd_df,
            lambda name: "macd" in name and "h" not in name and "s" not in name,
            "macd_line",
        )
        macd_signal_col = _first_matching_column(macd_df, lambda name: "s" in name and "h" not in name, "macd_signal")
        macd_df, macd_available, macd_ready = _usable_indicator_window(
            macd_df,
            [hist_col, macd_line_col, macd_signal_col],
            engine.SIGNAL_INDICATOR_MIN_WINDOW,
            closed_candle,
        )
        if not macd_ready or len(macd_df[hist_col].iloc[-6:-1]) < 5:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=engine.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=engine.SIGNAL_INDICATOR_MIN_WINDOW,
                available_indicator_window=macd_available,
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return StrategyDecision(None, criteria, "signal_stack_data_not_ready", None)
        macd_current = macd_df[hist_col].iloc[-1]
        macd_prev5   = macd_df[hist_col].iloc[-6:-1]
        macd_line = macd_df[macd_line_col].iloc[-1]
        macd_signal_val = macd_df[macd_signal_col].iloc[-1]

        if trend == "Uptrend":
            macd_ok = macd_current > macd_prev5.min()
            macd_margin = float(macd_current - macd_prev5.min())
        else:
            macd_ok = macd_current < macd_prev5.max()
            macd_margin = float(macd_prev5.max() - macd_current)

        macd_strength = macd_histogram_score(
            macd_current,
            macd_prev5.min(),
            macd_prev5.max(),
            trend,
        )

        # ── Layer 3: Keltner Channel — band breach (outer bands) ───────────
        kc = calculate_keltner_channels(df, length=20, multiplier=1.5, mamode="ema")
        kc_upper_col = _first_matching_column(kc, lambda name: "u" in name and "l" not in name and "b" not in name, "keltner_upper")
        kc_lower_col = _first_matching_column(kc, lambda name: "l" in name and "u" not in name and "b" not in name, "keltner_lower")
        kc_mid_col = _first_matching_column(kc, lambda name: ("b" in name and "u" not in name and "l" not in name) or "m" in name, "keltner_mid")
        kc, kc_available, kc_ready = _usable_indicator_window(
            kc,
            [kc_upper_col, kc_lower_col, kc_mid_col],
            engine.SIGNAL_INDICATOR_MIN_WINDOW,
            closed_candle,
        )
        if not kc_ready:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=engine.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=engine.SIGNAL_INDICATOR_MIN_WINDOW,
                available_indicator_window=kc_available,
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return StrategyDecision(None, criteria, "signal_stack_data_not_ready", None)

        # Compute ATR early for use in Keltner proximity threshold
        atr_ser = calculate_atr(df)
        atr = atr_ser.iloc[-1]

        last5_low  = df["l"].iloc[-5:].min()
        last5_high = df["h"].iloc[-5:].max()
        kc_upper_last5 = kc[kc_upper_col].iloc[-5:]
        kc_lower_last5 = kc[kc_lower_col].iloc[-5:]

        if trend == "Uptrend":
            # CTI-v1.1 pullback: must breach OR come within proximity of lower band
            channel_width = float(kc_upper_last5.iloc[-1] - kc_lower_last5.iloc[-1])
            proximity_threshold = min(float(atr) * config.PULLBACK_KC_PROXIMITY_ATR, channel_width * 0.25)
            kc_ok = last5_low <= kc_lower_last5.min() or last5_low <= kc_lower_last5.min() + proximity_threshold
            kc_margin = float(kc_lower_last5.min() - last5_low)
        else:
            channel_width = float(kc_upper_last5.iloc[-1] - kc_lower_last5.iloc[-1])
            proximity_threshold = min(float(atr) * config.PULLBACK_KC_PROXIMITY_ATR, channel_width * 0.25)
            kc_ok = last5_high >= kc_upper_last5.max() or last5_high >= kc_upper_last5.max() - proximity_threshold
            kc_margin = float(last5_high - kc_upper_last5.max())

        keltner_strength = keltner_score(
            last5_low, last5_high, kc_lower_last5.min(), kc_upper_last5.max(), trend
        )

        # ── Layer 4: Candlestick (optional) ──────────────────────────────────
        patterns_df = calculate_candlestick_patterns(df)
        usable_patterns = patterns_df.dropna(how="all")
        if len(usable_patterns) < 5:
            context = _signal_readiness_issue(
                raw_candles=candles,
                closed_candles=closed_window,
                required_candles=engine.SIGNAL_WINDOW_MIN_CANDLES,
                required_indicator_window=5,
                available_indicator_window=len(usable_patterns),
                selected_closed_candle=closed_candle,
            )
            criteria.append(_signal_data_not_ready_criterion(context))
            return StrategyDecision(None, criteria, "signal_stack_data_not_ready", None)
        recent = patterns_df.iloc[-5:].dropna(how="all")
        identified = recent.columns[(recent != 0).any(axis=0)].tolist()

        if trend == "Uptrend":
            bullish_patterns = {"CDL_ENGULFING", "CDL_HAMMER"}
            candle_ok = bool(set(identified) & bullish_patterns)
        else:
            bearish_patterns = {"CDL_ENGULFING", "CDL_SHOOTINGSTAR", "CDL_SPINNINGTOP"}
            candle_ok = bool(set(identified) & bearish_patterns)

        candle_strength = candlestick_score(patterns_df, trend)

        # ── CTI-v1.1 Dual Path: Try Continuation first, then Pullback ──────
        # Continuation path: trend aligned, MACD supports, price on correct side of midline, structure OK
        # No StochRSI required for continuation

        continuation_ok = False
        continuation_criteria: list = []

        # Check continuation: MACD supports direction
        if trend == "Uptrend":
            macd_continuation_ok = macd_current > 0
            macd_continuation_margin = float(macd_current)
        else:
            macd_continuation_ok = macd_current < 0
            macd_continuation_margin = float(abs(macd_current))

        # Check continuation: price on correct side of Keltner midline
        midline = float(kc[kc_mid_col].iloc[-1])
        last_close = float(df["c"].iloc[-1])
        trigger_price = _live_trigger_price(symbol, trend, last_close)
        if trend == "Uptrend":
            kc_continuation_ok = trigger_price > midline
            kc_continuation_margin = trigger_price - midline
        else:
            kc_continuation_ok = trigger_price < midline
            kc_continuation_margin = midline - trigger_price

        # Check continuation: structure (last N candles show HH/HL or LH/LL)
        # Require at least one strictly progressive bar (not just flat/equal)
        structure_bars = config.CONTINUATION_STRUCTURE_BARS
        recent_highs = df["h"].iloc[-structure_bars:].tolist()
        recent_lows = df["l"].iloc[-structure_bars:].tolist()
        if trend == "Uptrend":
            has_higher_high = any(recent_highs[i] > recent_highs[i-1] for i in range(1, len(recent_highs)))
            has_higher_low = any(recent_lows[i] > recent_lows[i-1] for i in range(1, len(recent_lows)))
            structure_ok = has_higher_high or has_higher_low
        else:
            has_lower_high = any(recent_highs[i] < recent_highs[i-1] for i in range(1, len(recent_highs)))
            has_lower_low = any(recent_lows[i] < recent_lows[i-1] for i in range(1, len(recent_lows)))
            structure_ok = has_lower_high or has_lower_low

        # 5M trend alignment check for continuation (configurable)
        trend_5m_aligned = True
        if config.CONTINUATION_TREND_REQUIRE_5M:
            trend_5m_aligned = (trend == "Uptrend" and raw_lr_5m > 0) or (trend == "Downtrend" and raw_lr_5m < 0)

        continuation_all_pass = macd_continuation_ok and kc_continuation_ok and structure_ok and trend_5m_aligned

        continuation_criteria.extend([
            _criterion("macd", "signal_stack", float(macd_current), "supports direction", bool(macd_continuation_ok), macd_continuation_margin),
            _criterion("keltner", "signal_stack", {"trigger_price": trigger_price, "closed_candle_close": last_close, "midline": midline}, "correct side of midline", bool(kc_continuation_ok), kc_continuation_margin),
            _criterion("structure", "signal_stack", {"recent_highs": recent_highs, "recent_lows": recent_lows}, "HH/HL or LH/LL", bool(structure_ok), None),
            _criterion("trend_5m", "signal_stack", raw_lr_5m, "aligned with bias" if config.CONTINUATION_TREND_REQUIRE_5M else "optional", bool(trend_5m_aligned), abs(raw_lr_5m), required=config.CONTINUATION_TREND_REQUIRE_5M),
        ])

        if allow_continuation and continuation_all_pass:
            log.debug("%s continuation signal passed: macd=%s kc=%s structure=%s 5m=%s",
                      symbol, macd_continuation_ok, kc_continuation_ok, structure_ok, trend_5m_aligned)
            # Build continuation signal
            breakdown = {
                "stoch_rsi": 0.0,  # not used for continuation
                "macd": macd_strength,
                "keltner": keltner_strength,
                "candlestick": 0.0,  # not required for continuation
                "structure": 1.0 if structure_ok else 0.0,
            }

            lr_1h = filtered_lr_1h if engine.shock_filter.enabled else raw_lr_1h
            lr_15 = filtered_lr_15m if engine.shock_filter.enabled else raw_lr_15m
            lr_5 = filtered_lr_5m if engine.shock_filter.enabled else raw_lr_5m
            trend_str = trend_score(lr_15, lr_5, trend,
                                    engine.LR_15M_THRESHOLD, engine.LR_5M_THRESHOLD)
            breakdown["trend"] = trend_str

            # Weighted confidence for continuation (no stoch/candle requirement)
            raw_confidence = continuation_confidence(breakdown)
            if raw_confidence < MIN_CONFIDENCE:
                log.debug("%s continuation signal rejected: confidence %.1f%% < %.0f%% threshold",
                          symbol, raw_confidence * 100, MIN_CONFIDENCE * 100)
                continuation_criteria.append(_criterion("confidence", "confidence", raw_confidence, MIN_CONFIDENCE, False, raw_confidence - MIN_CONFIDENCE, "gte"))
                # Don't return here — fall through to try pullback
            else:
                continuation_criteria.append(_criterion("confidence", "confidence", raw_confidence, MIN_CONFIDENCE, True, raw_confidence - MIN_CONFIDENCE, "gte"))
                confidence = round(raw_confidence, 3)

                entry_price = trigger_price
                setup_condition_first_true_at = closed_candle.time.isoformat() if closed_candle else None

                sl, tp = compute_sl_tp(entry_price, atr, trend)

                return StrategyDecision(Signal(
                    symbol=symbol,
                    direction=trend,
                    entry_price=round(entry_price, _price_decimals(entry_price)),
                    stop_loss=sl,
                    take_profit=tp,
                    atr=round(atr, 6),
                    lot_size=0.0,
                    risk_pct=config.RISK_PER_TRADE * 100,
                    confidence=confidence,
                    breakdown=breakdown,
                    trend_direction=trend,
                    patterns_found=[],
                    strategy=CONTINUATION_STRATEGY_VERSION,
                    signal_type="continuation",
                    # Indicator snapshot
                    stochrsi_k=0.0,
                    stochrsi_d=0.0,
                    macd_line=macd_line,
                    macd_signal=macd_signal_val,
                    macd_histogram=macd_current,
                    kc_upper=float(kc_upper_last5.iloc[-1]),
                    kc_mid=midline,
                    kc_lower=float(kc_lower_last5.iloc[-1]),
                    # Shock diagnostics
                    raw_lr_1h=raw_lr_1h,
                    raw_lr_15m=raw_lr_15m,
                    raw_lr_5m=raw_lr_5m,
                    filtered_lr_1h=filtered_lr_1h,
                    filtered_lr_15m=filtered_lr_15m,
                    filtered_lr_5m=filtered_lr_5m,
                    trend_changed_after_filter=trend_changed_after_filter,
                    volatility_shock_detected=shock_result.detected if shock_result else False,
                    shock_timeframe=shock_result.timeframe if shock_result else None,
                    shock_candle_time=shock_result.candle_time if shock_result else None,
                    shock_true_range=shock_result.true_range if shock_result else None,
                    shock_atr=shock_result.atr if shock_result else None,
                    shock_atr_multiple=shock_result.atr_multiple if shock_result else None,
                    shock_lookback_bars=shock_result.lookback_bars if shock_result else 0,
                    shock_direction=shock_result.direction if shock_result else "none",
                    shock_suppression_until=shock_result.suppression_until if shock_result else None,
                    shock_suppression_candles_remaining=shock_result.suppression_candles_remaining if shock_result else 0,
                    market_validity_state="invalid" if (shock_result and shock_result.detected) else "valid",
                    market_validity_reason="market_invalid:volatility_shock" if (shock_result and shock_result.detected) else None,
                    lr_1h=lr_1h,
                    lr_15m=lr_15,
                    lr_5m=lr_5,
                    signal_price=round(entry_price, _price_decimals(entry_price)),
                    suggested_entry=round(entry_price, _price_decimals(entry_price)),
                    entry_tolerance=round(atr * config.SIGNAL_ENTRY_TOLERANCE_ATR, _price_decimals(entry_price)),
                    setup_condition_first_true_at=setup_condition_first_true_at,
                ), continuation_criteria, "emitted", confidence)

        # ── Pullback Path ────────────────────────────────────────────────────
        if not config.PULLBACK_ENABLED:
            return StrategyDecision(None, criteria, "criteria_failed", None)

        structure_result = pullback_structure(df, trend)
        keltner_result = pullback_keltner_sequence(
            df, kc, trend, float(atr), kc_upper_col, kc_lower_col, kc_mid_col, macd_current=macd_current
        )
        trigger_result = pullback_trigger(
            patterns_df,
            trend,
            df,
            value_area_midline=keltner_result.get("midline"),
            value_area_tolerance=keltner_result.get("tolerance"),
            macd_current=float(macd_current),
        )
        stoch_result = pullback_stoch_rsi(float(k), float(d), stoch[k_col], trend)
        macd_soft_context = {
            "histogram": float(macd_current),
            "line": float(macd_line),
            "signal": float(macd_signal_val),
            "hard_blocker": bool(config.PULLBACK_MACD_HARD_BLOCK_ENABLED),
        }
        pullback_criteria = [
            _criterion("stoch_rsi", "signal_stack", {"k": float(k), "d": float(d), **stoch_result}, "pullback exhaustion", bool(stoch_result["passed"]), stoch_margin, reason=stoch_result["reason"], context=stoch_result),
            _criterion("macd_soft_score", "signal_stack", macd_soft_context, "soft confidence only", bool(macd_ok), macd_margin, required=False, reason="pullback_macd_soft_score", context=macd_soft_context),
            _criterion("keltner_pullback_sequence", "signal_stack", keltner_result, "prior outer break plus midline pullback", bool(keltner_result["passed"]), None, reason=keltner_result["reason"], context=keltner_result),
            _criterion("pullback_structure", "signal_stack", structure_result, "HH/HL or LH/LL protected structure", bool(structure_result["passed"]), None, reason=structure_result["reason"], context=structure_result),
            _criterion("pullback_trigger_candle", "confirmation", trigger_result, "approved pullback trigger", bool(trigger_result["passed"]), None, reason=trigger_result["reason"], context=trigger_result),
        ]
        if config.PULLBACK_MACD_HARD_BLOCK_ENABLED:
            pullback_criteria.append(
                _criterion(
                    "pullback_macd_hard_block",
                    "signal_stack",
                    macd_soft_context,
                    "macd supports pullback direction",
                    bool(macd_ok),
                    macd_margin,
                    reason="pullback_macd_hard_block_ok" if macd_ok else "pullback_macd_hard_block_failed",
                    context=macd_soft_context,
                )
            )
        criteria.extend(pullback_criteria)

        all_pass = (
            stoch_result["passed"]
            and keltner_result["passed"]
            and structure_result["passed"]
            and trigger_result["passed"]
            and (not config.PULLBACK_MACD_HARD_BLOCK_ENABLED or macd_ok)
        )
        if not all_pass:
            log.debug("%s pullback signal blocked: stoch=%s kc=%s structure=%s trigger=%s",
                      symbol, stoch_result["passed"], keltner_result["passed"], structure_result["passed"], trigger_result["passed"])
            return StrategyDecision(None, criteria, "criteria_failed", None)

        # Layer 2 score breakdown
        breakdown = {
            "stoch_rsi": stoch_strength,
            "macd": max(0.0, macd_strength),
            "keltner": keltner_strength,
            "candlestick": candle_strength,
        }

        # Trend strength component. check_symbol passes these values from
        # _get_trend so scan cycles do not fetch H1/M15/M5 candles twice.
        # When trend_lr is provided (remote tuple API), use it directly.
        # Otherwise fetch the trend candles ourselves (legacy / standalone call).
        if trend_lr is None:
            candles_1h  = engine._get_cached_candles(symbol, "H1",  count=30)
            candles_15m = engine._get_cached_candles(symbol, "M15", count=60)
            candles_5m  = engine._get_cached_candles(symbol, "M5",  count=24)
            df_1h = candles_to_df(candles_1h)
            df_15 = candles_to_df(candles_15m)
            df_5  = candles_to_df(candles_5m)
            raw_lr_1h = calculate_linear_regression(df_1h, length=20).iloc[-1]
            raw_lr_15m = calculate_linear_regression(df_15, length=25).iloc[-1]
            raw_lr_5m = calculate_linear_regression(df_5,  length=14).iloc[-1]
            lr_1h = raw_lr_1h
            lr_15 = raw_lr_15m
            lr_5 = raw_lr_5m
        else:
            lr_1h, lr_15, lr_5 = trend_lr
        trend_str = trend_score(lr_15, lr_5, trend,
                                engine.LR_15M_THRESHOLD, engine.LR_5M_THRESHOLD)
        breakdown["trend"] = trend_str

        # Weighted confidence (candle optional — lower weight)
        raw_confidence = pullback_confidence(breakdown)
        # ── Confidence gate ──────────────────────────────────────────────────
        # Signals below 55% confidence are too weak to act on
        if raw_confidence < MIN_CONFIDENCE:
            log.debug("%s signal rejected: confidence %.1f%% < %.0f%% threshold",
                      symbol, raw_confidence * 100, MIN_CONFIDENCE * 100)
            criteria.append(_criterion("confidence", "confidence", raw_confidence, MIN_CONFIDENCE, False, raw_confidence - MIN_CONFIDENCE, "gte"))
            return StrategyDecision(None, criteria, "confidence_failed", raw_confidence)

        criteria.append(_criterion("confidence", "confidence", raw_confidence, MIN_CONFIDENCE, True, raw_confidence - MIN_CONFIDENCE, "gte"))

        confidence = round(raw_confidence, 3)

        # ── Risk / Pricing ───────────────────────────────────────────────────
        # atr already computed at Keltner layer
        entry_price = trigger_price
        setup_condition_first_true_at = closed_candle.time.isoformat() if closed_candle else None

        sl, tp = compute_sl_tp(entry_price, atr, trend)

        return StrategyDecision(Signal(
            symbol=symbol,
            direction=trend,
            entry_price=round(entry_price, _price_decimals(entry_price)),
            stop_loss=sl,
            take_profit=tp,
            atr=round(atr, 6),
            lot_size=0.0,   # filled by caller via risk.py
            risk_pct=config.RISK_PER_TRADE * 100,
            confidence=confidence,
            breakdown=breakdown,
            trend_direction=trend,
            patterns_found=identified,
            strategy=PULLBACK_STRATEGY_VERSION,
            signal_type="high_value_pullback" if keltner_result.get("is_high_value", False) else "pullback",
            pullback_trigger=trigger_result["trigger"],
            pullback_bridge_status=pullback_bridge_status,
            pullback_rejection_reason=None,
            # Indicator snapshot
            stochrsi_k=k,
            stochrsi_d=d,
            macd_line=macd_line,
            macd_signal=macd_signal_val,
            macd_histogram=macd_current,
            kc_upper=float(kc_upper_last5.iloc[-1]),
            kc_mid=float(kc[kc_mid_col].iloc[-1]),
            kc_lower=float(kc_lower_last5.iloc[-1]),
            # Shock diagnostics
            raw_lr_1h=raw_lr_1h,
            raw_lr_15m=raw_lr_15m,
            raw_lr_5m=raw_lr_5m,
            filtered_lr_1h=filtered_lr_1h,
            filtered_lr_15m=filtered_lr_15m,
            filtered_lr_5m=filtered_lr_5m,
            trend_changed_after_filter=trend_changed_after_filter,
            volatility_shock_detected=shock_result.detected if shock_result else False,
            shock_timeframe=shock_result.timeframe if shock_result else None,
            shock_candle_time=shock_result.candle_time if shock_result else None,
            shock_true_range=shock_result.true_range if shock_result else None,
            shock_atr=shock_result.atr if shock_result else None,
            shock_atr_multiple=shock_result.atr_multiple if shock_result else None,
            shock_lookback_bars=shock_result.lookback_bars if shock_result else 0,
            shock_direction=shock_result.direction if shock_result else "none",
            shock_suppression_until=shock_result.suppression_until if shock_result else None,
            shock_suppression_candles_remaining=shock_result.suppression_candles_remaining if shock_result else 0,
            market_validity_state="invalid" if (shock_result and shock_result.detected) else "valid",
            market_validity_reason="market_invalid:volatility_shock" if (shock_result and shock_result.detected) else None,
            lr_1h=lr_1h,
            lr_15m=lr_15,
            lr_5m=lr_5,
            signal_price=round(entry_price, _price_decimals(entry_price)),
            suggested_entry=round(entry_price, _price_decimals(entry_price)),
            entry_tolerance=round(atr * config.SIGNAL_ENTRY_TOLERANCE_ATR, _price_decimals(entry_price)),
            setup_condition_first_true_at=setup_condition_first_true_at,
            recent_candles=candles,
        ), criteria, "emitted", confidence)


def get_strategy() -> PullbackStrategy:
    """Factory used by the TradeGumi strategy loader."""
    return PullbackStrategy()

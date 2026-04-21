"""Layer 1 Pre-Session Scanner.

Runs at 06:30 ET every trading day. For each CTI-allowed symbol:
- ADR consumption: how much of the average daily range has already been used
- Volatility regime: 5d ATR vs 20d ATR (expanding vs contracting)
- Breakout probability: % of last 20 sessions with >1x ATR directional move
- Day-of-week bias

Outputs ranked watchlist (Tier 1/2/Below threshold) to console + saves to JSON.
"""
import json
import logging as log
from datetime import datetime
from pathlib import Path

from pytz import timezone

from tradegumi import config
from tradegumi.api.base_client import ExecutionClient, Candle
from tradegumi.indicators import calculate_atr, candles_to_df
from tradegumi.session_rules import day_of_week_bias

log = log.getLogger(__name__)
NY_TZ = timezone("America/New_York")
CT_TZ = timezone("America/Chicago")
NY_TZ = timezone("America/New_York")

WATCHLIST_FILE = Path(__file__).parent / "data" / "watchlist.json"
SESSION_FILE = Path(__file__).parent / "data" / "session_state.json"


def calc_adr(client: ExecutionClient, symbol: str, lookback: int = 20) -> float:
    """Average True Range as percentage of close (ADR)."""
    candles = client.get_candles(symbol, "D", count=lookback + 1)
    if len(candles) < lookback:
        return 0.0
    df = candles_to_df(candles)
    adr = float(calculate_atr(df.tail(lookback)).mean())
    last_close = float(df["c"].iloc[-1])
    return (adr / last_close) * 100 if last_close else 0.0


def calc_adr_consumed(client: ExecutionClient, symbol: str, lookback: int = 20) -> float:
    """How much of today's ADR range has already been used (0–100%).

    Uses the *completed* prior day's candle as today's range proxy,
    since the current daily candle is still forming and understates range.
    """
    # Get last 2 daily candles — [0] = yesterday (complete), [-1] = today (incomplete)
    candles = client.get_candles(symbol, "D", count=2)
    if len(candles) < 2:
        return 0.0
    df = candles_to_df(candles)
    # Use yesterday's completed candle for range used
    yesterday = df.iloc[-2]
    range_used = float(yesterday["h"] - yesterday["l"])

    # ADR baseline from prior sessions (excluding today's incomplete candle)
    prior_candles = client.get_candles(symbol, "D", count=lookback + 1)
    prior_df = candles_to_df(prior_candles[:-1])
    adr = float(calculate_atr(prior_df).mean())

    if adr == 0 or adr != adr:
        return 0.0
    return min(100.0, (range_used / adr) * 100)


def calc_volatility_regime(client: ExecutionClient, symbol: str) -> float:
    """Return ratio of 5d ATR / 20d ATR.

    > 1.0 = expanding (high volatility), < 1.0 = contracting.
    """
    # ATR(14) needs ~15 rows warmup; request enough for both windows
    candles_5  = client.get_candles(symbol, "D", count=20)
    candles_20 = client.get_candles(symbol, "D", count=35)
    if len(candles_5) < 20 or len(candles_20) < 35:
        return 1.0
    df_5  = candles_to_df(candles_5)
    df_20 = candles_to_df(candles_20)
    atr_5  = float(calculate_atr(df_5).iloc[-1])
    atr_20 = float(calculate_atr(df_20).mean())
    if atr_20 == 0 or atr_20 != atr_20 or atr_5 != atr_5:  # catch NaN/zero
        return 1.0
    return atr_5 / atr_20


def calc_breakout_probability(client: ExecutionClient, symbol: str, sessions: int = 20) -> float:
    """Fraction of last N daily sessions that had a >1.5x ATR range.

    Uses daily candles — a 'breakout' day has a range exceeding 1.5x the
    20-day ATR, indicating above-average volatility and directional commitment.
    """
    candles = client.get_candles(symbol, "D", count=sessions + 1)
    if len(candles) < sessions + 1:
        return 0.5  # insufficient data

    df = candles_to_df(candles)
    # Exclude today's incomplete candle
    df_completed = df.iloc[:-1].tail(sessions)
    if len(df_completed) < sessions:
        return 0.5

    # Calculate ATR for baseline
    atr_df = df_completed.copy()
    atr_series = calculate_atr(atr_df)
    atr_mean = float(atr_series.mean())

    if atr_mean == 0 or atr_mean != atr_mean:
        return 0.5

    breakout_sessions = 0
    for idx in df_completed.index:
        daily_range = float(df_completed.loc[idx, "h"] - df_completed.loc[idx, "l"])
        if daily_range > 1.5 * atr_mean:
            breakout_sessions += 1

    return breakout_sessions / sessions


def score_symbol(
    client: ExecutionClient,
    symbol: str,
    adr_consumed: float,
    vol_regime: float,
    breakout_prob: float,
    dow_bias: float,
) -> dict:
    """Score a symbol across Layer 1 factors. Returns factor dict."""
    factors = {
        "adr_consumed": adr_consumed,
        "vol_regime": vol_regime,
        "breakout_prob": breakout_prob,
        "dow_bias": dow_bias,
    }

    # ADR: lower consumed = better (compressed range = better EV)
    # Scale: 0-40% consumed = full score, drops linearly to 0 at 100%
    if adr_consumed < 40:
        adr_score = 1.0 - (adr_consumed / 100.0)  # 1.0 → 0.6
    elif adr_consumed < 80:
        adr_score = 0.6 - ((adr_consumed - 40) / 100.0)  # 0.6 → 0.2
    else:
        adr_score = max(0.0, 0.2 - ((adr_consumed - 80) / 100.0))

    # Vol regime: near 1.0 = normal; >1.5 = noisy (penalise); <0.7 = too quiet
    if 0.85 <= vol_regime <= 1.2:
        vol_score = 1.0
    elif 0.7 <= vol_regime <= 1.5:
        vol_score = 0.6  # acceptable but not ideal
    elif vol_regime > 1.5:
        vol_score = max(0.0, 0.6 - (vol_regime - 1.5))
    else:
        vol_score = max(0.0, vol_regime / 0.7)  # too quiet

    # Breakout: higher = better (more opportunity)
    breakout_score = breakout_prob  # 0–1

    # DOW: 0.0 = skip (weekend), 1.0 = full weight
    dow_score = dow_bias

    raw = adr_score * 0.25 + vol_score * 0.25 + breakout_score * 0.30 + dow_score * 0.20
    total = round(raw, 3)
    factors["scores"] = {
        "adr": round(adr_score, 3),
        "vol": round(vol_score, 3),
        "breakout": round(breakout_score, 3),
        "dow": round(dow_score, 3),
        "total": total,
    }
    return factors


def tier_from_score(score: float) -> str:
    """Assign tier from total score.

    Calibrated for realistic score distribution (floor ~0.35 on weekdays).
    Tier 1: high-confidence setups (compressed range + breakouts)
    Tier 2: reasonable opportunities
    Below: skip
    """
    if score >= 0.55:
        return "Tier 1"
    if score >= 0.50:
        return "Tier 2"
    return "Below Threshold"


def _load_session_state() -> dict:
    """Load or create session state tracking starting balance."""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_session_state(state: dict) -> None:
    """Persist session state."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def run_scan(client: ExecutionClient, available: set[str] | None = None) -> dict:
    """Run full Layer 1 scan across available execution symbols.

    Args:
        client: Execution client for market data.
        available: Set of CTI symbols available on this account.
                   If None, scans all EXECUTION_SYMBOLS.

    Returns dict suitable for Discord embed + watchlist persistence.
    """
    now = datetime.now(CT_TZ)
    dow_bias = day_of_week_bias("EURUSD", datetime.now(NY_TZ))  # market TZ for bias

    # Only scan instruments that are actually available on this account
    scan_symbols = available if available else set(config.EXECUTION_SYMBOLS)
    results = {}
    for symbol in scan_symbols:
        try:
            adr_consumed  = calc_adr_consumed(client, symbol)
            vol_regime    = calc_volatility_regime(client, symbol)
            breakout_prob = calc_breakout_probability(client, symbol)
            factors       = score_symbol(
                client, symbol, adr_consumed, vol_regime, breakout_prob, dow_bias
            )
            tier = tier_from_score(factors["scores"]["total"])
            results[symbol] = {
                "tier": tier,
                "factors": factors,
            }
        except Exception as e:
            log.warning("Failed to score %s: %s", symbol, e)
            results[symbol] = {
                "tier": "Below Threshold",
                "factors": {"error": str(e)},
            }

    # Sort by score descending
    ranked = sorted(
        results.items(),
        key=lambda x: x[1]["factors"].get("scores", {}).get("total", 0),
        reverse=True,
    )

    tier1 = [s for s, d in ranked if d["tier"] == "Tier 1"]
    tier2 = [s for s, d in ranked if d["tier"] == "Tier 2"]
    below = [s for s, d in ranked if d["tier"] == "Below Threshold"]

    output = {
        "timestamp": now.isoformat(),
        "tier1": tier1,
        "tier2": tier2,
        "below": below,
        "ranked": [(s, d["factors"].get("scores", {}).get("total", 0), d["tier"]) for s, d in ranked],
        "detail": results,
    }

    # ── Account info for watchlist header ────────────────────────────────────
    try:
        from tradegumi.api.oanda_client import OandaClient
        if isinstance(client, OandaClient):
            acct_data = client._request("GET", f"/v3/accounts/{client.account_id}/summary")
            acct = acct_data.get("account", {})
            balance = float(acct.get("balance", 0))
            unrealized_pl = float(acct.get("unrealizedPL", 0))
            realized_pl = float(acct.get("pl", 0))
            nav = float(acct.get("NAV", 0))
            open_trades = int(acct.get("openTradeCount", 0))

            # Track session starting balance
            state = _load_session_state()
            today_str = now.strftime("%Y-%m-%d")
            if state.get("start_date") != today_str or "start_balance" not in state:
                state["start_date"] = today_str
                state["start_balance"] = balance
                _save_session_state(state)
            start_balance = float(state.get("start_balance", balance))

            # CTI metrics — all percentages, dollar amounts derived from live balance
            cti_tier = config.get_cti_tier(balance)
            daily_loss_pct = cti_tier["daily_loss_pct"]
            max_dd_pct = cti_tier["max_dd_pct"]
            active_target_pct = cti_tier["active_target_pct"]
            program = cti_tier["program"]
            phase = cti_tier["phase"]
            phase_label = cti_tier["phase_label"]

            session_pnl = nav - start_balance
            session_pnl_pct = (session_pnl / start_balance * 100) if start_balance else 0

            # Profit target: active_target_pct * start_balance (derived from balance)
            profit_target_dollars = active_target_pct * start_balance
            profit_target_remaining = profit_target_dollars - max(0, session_pnl)
            profit_target_remaining_pct = max(0, (1 - max(0, session_pnl) / profit_target_dollars) * 100) if profit_target_dollars else 0

            # Daily loss remaining: daily_loss_pct * start_balance - today's losses
            daily_loss_limit = daily_loss_pct * start_balance
            daily_loss_used = max(0, -session_pnl)  # how much lost today
            daily_loss_remaining = daily_loss_limit - daily_loss_used
            daily_loss_remaining_pct = max(0, (1 - daily_loss_used / daily_loss_limit) * 100) if daily_loss_limit else 0

            # Max drawdown remaining: max_dd_pct * start_balance - total drawdown from start
            max_dd_dollars = max_dd_pct * start_balance
            drawdown_from_start = start_balance - nav  # how far NAV is below starting balance
            dd_remaining = max_dd_dollars - max(0, drawdown_from_start)
            dd_remaining_pct = max(0, (1 - max(0, drawdown_from_start) / max_dd_dollars) * 100) if max_dd_dollars else 0

            output["account"] = {
                "balance": balance,
                "nav": nav,
                "unrealized_pl": unrealized_pl,
                "realized_pl": realized_pl,
                "open_trades": open_trades,
                "start_balance": start_balance,
                "session_pnl": session_pnl,
                "session_pnl_pct": session_pnl_pct,
                # CTI info
                "cti_program": program,
                "cti_phase": phase,
                "cti_phase_label": phase_label,
                "active_target_pct": active_target_pct,
                "has_profit_target": True,
                "profit_target_dollars": profit_target_dollars,
                "profit_target_remaining": profit_target_remaining,
                "profit_target_remaining_pct": profit_target_remaining_pct,
                "daily_loss_limit": daily_loss_limit,
                "daily_loss_remaining": daily_loss_remaining,
                "daily_loss_remaining_pct": daily_loss_remaining_pct,
                "max_dd_dollars": max_dd_dollars,
                "dd_remaining": dd_remaining,
                "dd_remaining_pct": dd_remaining_pct,
                "active_target_pct": active_target_pct,
                "daily_loss_pct": daily_loss_pct,
                "max_dd_pct": max_dd_pct,
            }
    except Exception as e:
        log.warning("Failed to fetch account info for watchlist: %s", e)

    # Persist watchlist
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)

    return output


def load_watchlist() -> set[str]:
    """Load today's watchlist from persisted file (tier1 + tier2 symbols only)."""
    if not WATCHLIST_FILE.exists():
        return set(config.EXECUTION_SYMBOLS)
    with open(WATCHLIST_FILE) as f:
        data = json.load(f)
    tier1 = set(data.get("tier1", []))
    tier2 = set(data.get("tier2", []))
    return tier1 | tier2


def load_watchlist_with_scores() -> dict[str, dict]:
    """Load watchlist with tier and score info for loop sorting.

    Returns dict mapping symbol -> {"tier": str, "score": float}.
    Only includes Tier 1 and Tier 2 symbols.
    """
    if not WATCHLIST_FILE.exists():
        return {s: {"tier": "unranked", "score": 0.0} for s in config.EXECUTION_SYMBOLS}
    with open(WATCHLIST_FILE) as f:
        data = json.load(f)
    tier1 = set(data.get("tier1", []))
    tier2 = set(data.get("tier2", []))
    ranked = data.get("ranked", [])
    result = {}
    for entry in ranked:
        symbol, score, tier_label = entry[0], entry[1], entry[2]
        if symbol in tier1 or symbol in tier2:
            result[symbol] = {"tier": tier_label, "score": score}
    return result


_TIER_RANK = {"Tier 1": 2, "Tier 2": 1}  # higher = better; unlisted tiers rank 0


def format_watchlist_diff(prev_result: dict, new_result: dict) -> str | None:
    """Format only what changed between two scans for periodic Discord updates.

    Returns None if nothing meaningful changed (no tier moves, no score shift ≥0.05).
    """
    prev = {s: {"score": sc, "tier": t} for s, sc, t in prev_result.get("ranked", [])}
    new  = {s: {"score": sc, "tier": t} for s, sc, t in new_result.get("ranked", [])}

    changes = []
    for symbol, n in new.items():
        p = prev.get(symbol)
        if p is None:
            changes.append(f"🆕 **{symbol}**: added — {n['tier']} ({n['score']:.3f})")
        elif p["tier"] != n["tier"]:
            arrow = "⬆️" if _TIER_RANK.get(n["tier"], 0) > _TIER_RANK.get(p["tier"], 0) else "⬇️"
            changes.append(f"{arrow} **{symbol}**: {p['tier']} → {n['tier']} ({n['score']:.3f})")
        elif abs(n["score"] - p["score"]) >= 0.05:
            arrow = "↑" if n["score"] > p["score"] else "↓"
            changes.append(f"{arrow} **{symbol}**: {p['score']:.3f} → {n['score']:.3f} ({n['tier']})")

    for symbol in prev:
        if symbol not in new:
            changes.append(f"❌ **{symbol}**: removed from watchlist")

    if not changes:
        return None

    now_et = datetime.now(NY_TZ)
    lines = [f"**📊 Watchlist Update** — {now_et.strftime('%H:%M ET')}"] + changes
    return "\n".join(lines)


def format_watchlist_text(scan_result: dict) -> str:
    """Format scan result as a readable Discord message.

    Shows each pair with tier and score, sorted by score descending.
    Includes account balance, PnL, and CTI risk metrics.
    """
    now = datetime.now(CT_TZ)
    now_et = datetime.now(NY_TZ)
    ranked = scan_result.get("ranked", [])
    acct = scan_result.get("account")

    # ── Account header ──────────────────────────────────────────────────────
    lines = [f"**🌅 Morning Watchlist**"]
    lines.append(f"Generated: {now_et.strftime('%A %b %d, %Y %I:%M %p ET')} ({now.strftime('%I:%M %p CT')})")

    if acct:
        lines.append("")
        lines.append(f"💰 **Balance:** ${acct['balance']:,.2f} | **NAV:** ${acct['nav']:,.2f}")

        pnl_sign = "+" if acct['session_pnl'] >= 0 else ""
        lines.append(f"📊 **Session PnL:** {pnl_sign}${acct['session_pnl']:,.2f} ({pnl_sign}{acct['session_pnl_pct']:.2f}%)")

        # CTI program and phase
        lines.append(f"🏷️ **CTI:** {acct['cti_phase_label']} ({acct['active_target_pct']*100:.0f}% target)")

        # Profit target progress
        lines.append(f"🎯 **Profit Target:** ${acct['profit_target_remaining']:,.2f} remaining ({acct['profit_target_remaining_pct']:.1f}% left)")

        # Daily loss remaining
        lines.append(f"🛡️ **Daily Loss:** ${acct['daily_loss_remaining']:,.2f} remaining ({acct['daily_loss_remaining_pct']:.1f}% left of {acct['daily_loss_pct']*100:.0f}%)")

        # Max drawdown remaining
        lines.append(f"⚠️ **Max DD:** ${acct['dd_remaining']:,.2f} remaining ({acct['dd_remaining_pct']:.1f}% left of {acct['max_dd_pct']*100:.0f}%)")

        if acct['open_trades'] > 0:
            u_pnl = acct['unrealized_pl']
            u_sign = "+" if u_pnl >= 0 else ""
            lines.append(f"📐 **Open Trades:** {acct['open_trades']} | Unrealized: {u_sign}${u_pnl:,.2f}")

    # ── Ranked pairs ────────────────────────────────────────────────────────
    lines.append("")
    lines.append("```")
    lines.append(f"{'Pair':<10} {'Tier':<8} {'Score'}")
    lines.append(f"{'─'*10} {'─'*8} {'─'*5}")
    for symbol, score, tier in ranked:
        tier_emoji = "🟢" if tier == "Tier 1" else "🟡" if tier == "Tier 2" else "⬛"
        tier_short = tier.replace("Tier ", "T") if tier.startswith("Tier") else "T-"
        lines.append(f"{symbol:<10} {tier_emoji}{tier_short:<7} {score:.3f}")
    lines.append("```")

    # Summary counts
    tier1_count = len(scan_result.get("tier1", []))
    tier2_count = len(scan_result.get("tier2", []))
    below_count = len(scan_result.get("below", []))
    lines.append(f"🟢 Tier 1: {tier1_count} | 🟡 Tier 2: {tier2_count} | ⬛ Below: {below_count}")

    return "\n".join(lines)
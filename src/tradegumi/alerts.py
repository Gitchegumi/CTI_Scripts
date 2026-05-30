"""Discord webhook alerter.

Posts signals and pre-session watchlists to Discord.
Format is explicit and scannable; every signal gets a message regardless of
whether execution follows.
"""
import json
import logging as log
import requests
from typing import Optional

from tradegumi import config
from datetime import datetime, timedelta
from pytz import timezone

NY_TZ = timezone('America/New_York')
CT_TZ = timezone('America/Chicago')
from tradegumi.signal_engine import Signal
from pathlib import Path

log = log.getLogger(__name__)

WEBHOOK_URL = config.DISCORD_WEBHOOK_URL
MODE = config.TRADEGUMI_MODE

SIGNALS_FILE = Path(__file__).parent / "data" / "signals.json"
TRADE_CORRELATIONS_FILE = Path(__file__).parent / "data" / "trade_correlations.json"
SIGNAL_RETENTION_DAYS = 7
CORRELATION_WINDOW_SECONDS = 300  # 5 minutes


def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO timestamp string to a timezone-aware datetime.

    On parse failure, logs a warning and returns datetime.min (treated as
    expired by all rolling-window trims, so malformed entries are dropped).
    """
    try:
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = NY_TZ.localize(ts)
        return ts
    except Exception:
        log.warning("Could not parse timestamp %r — treating as expired", ts_str)
        return datetime.min.replace(tzinfo=NY_TZ)


def _post(payload: dict) -> bool:
    """Send a payload to the Discord webhook. Returns True on success."""
    if not WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL not set — alert not sent")
        return False
    try:
        resp = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        log.error("Discord webhook error: %s", e)
        return False


def format_signal_message(signal: Signal) -> dict:
    """Build a Discord embed for a trade signal.

    Even if signal is blocked, format with the block reason so there's a record.
    """
    sym  = signal.symbol
    dirn = signal.direction
    conf = signal.confidence
    conf_pct = int(conf * 100) if conf <= 1.0 else int(conf)

    if signal.is_blocked():
        color = 0x808080   # grey for blocked
        title = f"🚫 {sym} {dirn} | BLOCKED"
        desc  = f"**Reason:** {signal.blocked_reason}"
        fields = []
    else:
        color = 0x00FF00 if dirn == "BUY" else 0xFF0000
        title = f"{'🟢' if dirn == 'BUY' else '🔴'} {sym} {dirn}"
        desc  = f"Confidence: **{conf_pct}%** | Risk: {signal.risk_pct:.2f}%"
        fields = [
            {"name": "Buy Price",   "value": str(signal.entry_price), "inline": True},
            {"name": "Stop Loss",   "value": str(signal.stop_loss), "inline": True},
            {"name": "Take Profit", "value": str(signal.take_profit), "inline": True},
            {"name": "Units",       "value": f"{signal.lot_size:,.0f}", "inline": True},
            {"name": "ATR",         "value": f"{signal.atr:.5f}", "inline": True},
            {"name": "R:R Ratio",    "value": "1:4", "inline": True},
        ]

        if signal.patterns_found:
            patterns_str = ", ".join(signal.patterns_found)
            fields.append({"name": "Patterns", "value": patterns_str, "inline": False})

        # Layer 2 breakdown
        br = signal.breakdown
        score_lines = "\n".join(
            f"• {k}: {v:.3f}" if isinstance(v, float) else f"• {k}: {v}"
            for k, v in br.items()
        )
        fields.append({"name": "Layer 2 Scoring", "value": score_lines, "inline": False})

    return {
        "embeds": [{
            "title": title,
            "description": desc,
            "color": color,
            "fields": fields,
            "footer": {"text": f"TradeGumi {MODE} | {datetime.now(NY_TZ):%I:%M %p ET} ({datetime.now(CT_TZ):%I:%M %p CT})"},
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }]
    }


def save_signal(signal: Signal) -> None:
    """Append signal to the rolling 7-day signals log.

    Every firing is stored as a distinct entry. The dashboard filters this
    list client-side to the 60-minute display window.
    """
    try:
        SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if SIGNALS_FILE.exists():
            with open(SIGNALS_FILE) as f:
                existing = json.load(f)

        now = datetime.now(NY_TZ)
        try:
            rr: Optional[float] = round(
                abs(signal.take_profit - signal.entry_price)
                / abs(signal.entry_price - signal.stop_loss),
                1,
            )
        except ZeroDivisionError:
            rr = None  # entry == stop_loss; undefined R:R

        entry = {
            "symbol": signal.symbol,
            "direction": signal.direction,
            "confidence": round(signal.confidence, 3),
            "strategy": getattr(signal, "strategy", "CTI-v1"),
            "signal_type": getattr(signal, "signal_type", "pullback"),
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "lot_size": signal.lot_size,
            "atr": signal.atr,
            "rr": rr,
            "timestamp": now.isoformat(),
            # Indicator snapshot
            "stochrsi_k": getattr(signal, "stochrsi_k", 0.0),
            "stochrsi_d": getattr(signal, "stochrsi_d", 0.0),
            "macd_line": getattr(signal, "macd_line", 0.0),
            "macd_signal": getattr(signal, "macd_signal", 0.0),
            "macd_histogram": getattr(signal, "macd_histogram", 0.0),
            "kc_upper": getattr(signal, "kc_upper", 0.0),
            "kc_mid": getattr(signal, "kc_mid", 0.0),
            "kc_lower": getattr(signal, "kc_lower", 0.0),
            "lr_1h": getattr(signal, "lr_1h", 0.0),
            "lr_15m": getattr(signal, "lr_15m", 0.0),
            "lr_5m": getattr(signal, "lr_5m", 0.0),
        }

        existing.append(entry)

        # Trim to 7-day rolling window
        cutoff = now - timedelta(days=SIGNAL_RETENTION_DAYS)
        existing = [e for e in existing if _parse_ts(e.get("timestamp", "")) > cutoff]

        with open(SIGNALS_FILE, "w") as f:
            json.dump(existing, f, indent=2, default=str)
    except Exception as e:
        log.warning("Failed to save signal to signals.json: %s", e)


def record_trade_correlation(
    trade_id: str,
    symbol: str,
    direction: str,
    trade_time: datetime,
) -> None:
    """If a signal fired within 5 min of this trade, record the confidence for analysis."""
    try:
        if not SIGNALS_FILE.exists():
            return
        with open(SIGNALS_FILE) as f:
            signals = json.load(f)

        window_start = trade_time - timedelta(seconds=CORRELATION_WINDOW_SECONDS)
        matching = [
            s for s in signals
            if s.get("symbol") == symbol
            and s.get("direction") == direction
            and window_start <= _parse_ts(s.get("timestamp", "")) <= trade_time
        ]
        if not matching:
            log.debug("No signal within 5 min for %s %s trade %s", symbol, direction, trade_id)
            return

        recent = max(matching, key=lambda s: _parse_ts(s["timestamp"]))
        lag = int((trade_time - _parse_ts(recent["timestamp"])).total_seconds())

        corr = {
            "trade_id": trade_id,
            "symbol": symbol,
            "direction": direction,
            "confidence": recent["confidence"],
            "signal_timestamp": recent["timestamp"],
            "trade_timestamp": trade_time.isoformat(),
            "signal_lag_seconds": lag,
        }

        existing = []
        if TRADE_CORRELATIONS_FILE.exists():
            with open(TRADE_CORRELATIONS_FILE) as f:
                existing = json.load(f)

        existing.append(corr)

        cutoff = trade_time - timedelta(days=SIGNAL_RETENTION_DAYS)
        existing = [e for e in existing if _parse_ts(e.get("trade_timestamp", "")) > cutoff]

        TRADE_CORRELATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TRADE_CORRELATIONS_FILE, "w") as f:
            json.dump(existing, f, indent=2, default=str)

        log.info(
            "Signal correlation: trade=%s %s %s confidence=%.3f lag=%ds",
            trade_id, symbol, direction, recent["confidence"], lag,
        )
    except Exception as e:
        log.warning("Failed to record trade correlation: %s", e)


def post_signal(signal: Signal) -> bool:
    """Send a signal alert. Prefers Discord DM (bot); falls back to webhook.

    Always writes to signals.json (dashboard display) and appends to the
    permanent journal regardless of which delivery path is used.
    """
    from tradegumi.discord_bot import post_signal_dm
    from tradegumi.journal import append_signal

    try:
        rr: Optional[float] = round(
            abs(signal.take_profit - signal.entry_price)
            / abs(signal.entry_price - signal.stop_loss),
            1,
        )
    except ZeroDivisionError:
        rr = None

    # Attempt DM first; fall back to webhook if bot not configured / fails
    msg_id = post_signal_dm(signal, rr=rr)
    if msg_id:
        log.info("Discord DM: signal sent for %s %s (msg_id=%s)", signal.symbol, signal.direction, msg_id)
        ok = True
    else:
        payload = format_signal_message(signal)
        ok = _post(payload)
        if ok:
            log.info("Discord webhook: signal posted for %s %s", signal.symbol, signal.direction)
        msg_id = None

    if ok:
        save_signal(signal)
        try:
            append_signal(signal, rr=rr, discord_msg_id=msg_id)
        except Exception as e:
            log.warning("Failed to append signal to journal: %s", e)

    return ok


def _fmt_watchlist_dm(watchlist_text: str, scan_result: dict | None, title: str) -> str:
    """Format a watchlist/update as plain text for Discord DM."""
    lines = [f"**{title}**", "", watchlist_text]

    if scan_result and "account" in scan_result:
        acct = scan_result["account"]
        pnl_sign = "+" if acct["session_pnl"] >= 0 else ""
        program = acct.get("cti_program", "challenge").title()
        phase = acct.get("cti_phase_label", "Phase 1")
        lines += [
            "",
            f"💰 **{phase} — {program}**",
            f"Balance `${acct['balance']:,.2f}` | NAV `${acct['nav']:,.2f}`",
            f"Session PnL `{pnl_sign}${acct['session_pnl']:,.2f}` ({pnl_sign}{acct['session_pnl_pct']:.2f}%)",
            f"🎯 Target ({acct['active_target_pct']*100:.0f}%) — `${acct['profit_target_remaining']:,.2f}` left ({acct['profit_target_remaining_pct']:.1f}%)",
            f"🛡️ Daily Loss ({acct['daily_loss_pct']*100:.0f}%) — `${acct['daily_loss_remaining']:,.2f}` left ({acct['daily_loss_remaining_pct']:.1f}%)",
            f"⚠️ Max DD ({acct['max_dd_pct']*100:.0f}%) — `${acct['dd_remaining']:,.2f}` left ({acct['dd_remaining_pct']:.1f}%)",
        ]

    lines.append(f"\n_TradeGumi {MODE} — {datetime.now(NY_TZ):%I:%M %p ET} ({datetime.now(CT_TZ):%I:%M %p CT})_")
    return "\n".join(lines)


def post_watchlist(watchlist_text: str, scan_result: dict | None = None, title: str = "🌅 Morning Watchlist — TradeGumi") -> bool:
    """Post a watchlist message. Prefers Discord DM; falls back to webhook."""
    from tradegumi.discord_bot import send_dm

    dm_text = _fmt_watchlist_dm(watchlist_text, scan_result, title)
    if send_dm(dm_text):
        log.info("Discord DM: watchlist/update sent (%d chars)", len(dm_text))
        return True

    # Fall back to webhook with embed layout
    embeds = [{
        "title": title,
        "color": 0x1E90FF,
        "footer": {"text": f"TradeGumi {MODE} | {datetime.now(NY_TZ):%I:%M %p ET} ({datetime.now(CT_TZ):%I:%M %p CT})"},
    }]

    if scan_result and "account" in scan_result:
        acct = scan_result["account"]
        pnl_sign = "+" if acct["session_pnl"] >= 0 else ""
        program = acct.get("cti_program", "challenge").title()
        phase = acct.get("cti_phase_label", "Phase 1")
        embeds.append({
            "title": f"💰 {phase}",
            "color": 0x00FF00 if acct["session_pnl"] >= 0 else 0xFF0000,
            "fields": [
                {"name": "Balance", "value": f"${acct['balance']:,.2f}", "inline": True},
                {"name": "NAV", "value": f"${acct['nav']:,.2f}", "inline": True},
                {"name": "Session PnL", "value": f"{pnl_sign}${acct['session_pnl']:,.2f} ({pnl_sign}{acct['session_pnl_pct']:.2f}%)", "inline": True},
                {"name": f"🎯 Target ({acct['active_target_pct']*100:.0f}%)", "value": f"${acct['profit_target_remaining']:,.2f} left ({acct['profit_target_remaining_pct']:.1f}%)", "inline": True},
                {"name": f"🛡️ Daily Loss ({acct['daily_loss_pct']*100:.0f}%)", "value": f"${acct['daily_loss_remaining']:,.2f} left ({acct['daily_loss_remaining_pct']:.1f}%)", "inline": True},
                {"name": f"⚠️ Max DD ({acct['max_dd_pct']*100:.0f}%)", "value": f"${acct['dd_remaining']:,.2f} left ({acct['dd_remaining_pct']:.1f}%)", "inline": True},
            ],
            "footer": {"text": f"TradeGumi {MODE} — {program}"},
        })

    return _post({"content": watchlist_text, "embeds": embeds})


def post_blocked_signal(signal: Signal, reason: str) -> bool:
    """Log and post a blocked signal with the reason."""
    signal.blocked_reason = reason
    log.info("Signal blocked for %s: %s", signal.symbol, reason)
    return post_signal(signal)

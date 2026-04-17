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
from datetime import datetime
from pytz import timezone

NY_TZ = timezone('America/New_York')
CT_TZ = timezone('America/Chicago')
from tradegumi.signal_engine import Signal

log = log.getLogger(__name__)

WEBHOOK_URL = config.DISCORD_WEBHOOK_URL
MODE = config.TRADEGUMI_MODE


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
            {"name": "Lot Size",    "value": f"{signal.lot_size:.2f}", "inline": True},
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


def post_signal(signal: Signal) -> bool:
    """Post a signal to Discord. Returns True on success."""
    if config.TRADEGUMI_MODE == "alert_only":
        mode_label = "alert_only"
    elif config.TRADEGUMI_MODE == "demo":
        mode_label = "demo"
    else:
        mode_label = "live"

    payload = format_signal_message(signal)
    ok = _post(payload)
    if ok:
        log.info("Discord: signal posted for %s %s", signal.symbol, signal.direction)
    return ok


def post_watchlist(watchlist_text: str, scan_result: dict | None = None) -> bool:
    """Post the morning pre-session watchlist to Discord."""
    embeds = [{
        "title": "🌅 Morning Watchlist — TradeGumi",
        "color": 0x1E90FF,
        "footer": {"text": f"TradeGumi {MODE} | {datetime.now(NY_TZ):%I:%M %p ET} ({datetime.now(CT_TZ):%I:%M %p CT})"},
    }]

    # Add account info embed if available
    if scan_result and "account" in scan_result:
        acct = scan_result["account"]
        pnl_sign = "+" if acct["session_pnl"] >= 0 else ""
        program = acct.get("cti_program", "challenge").title()
        phase = acct.get("cti_phase_label", "Phase 1")

        fields = [
            {"name": "Balance", "value": f"${acct['balance']:,.2f}", "inline": True},
            {"name": "NAV", "value": f"${acct['nav']:,.2f}", "inline": True},
            {"name": "Session PnL", "value": f"{pnl_sign}${acct['session_pnl']:,.2f} ({pnl_sign}{acct['session_pnl_pct']:.2f}%)", "inline": True},
            {"name": f"🎯 Target ({acct['active_target_pct']*100:.0f}%)", "value": f"${acct['profit_target_remaining']:,.2f} left ({acct['profit_target_remaining_pct']:.1f}%)", "inline": True},
            {"name": f"🛡️ Daily Loss ({acct['daily_loss_pct']*100:.0f}%)", "value": f"${acct['daily_loss_remaining']:,.2f} left ({acct['daily_loss_remaining_pct']:.1f}%)", "inline": True},
            {"name": f"⚠️ Max DD ({acct['max_dd_pct']*100:.0f}%)", "value": f"${acct['dd_remaining']:,.2f} left ({acct['dd_remaining_pct']:.1f}%)", "inline": True},
        ]

        embeds.append({
            "title": f"💰 {phase}",
            "color": 0x00FF00 if acct["session_pnl"] >= 0 else 0xFF0000,
            "fields": fields,
            "footer": {"text": f"TradeGumi {MODE} — {program}"},
        })

    payload = {
        "content": watchlist_text,
        "embeds": embeds,
    }

    return _post(payload)


def post_blocked_signal(signal: Signal, reason: str) -> bool:
    """Log and post a blocked signal with the reason."""
    signal.blocked_reason = reason
    log.info("Signal blocked for %s: %s", signal.symbol, reason)
    return post_signal(signal)
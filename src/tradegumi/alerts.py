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
        title = f"{'🟢' if dirn == 'BUY' else '🔴'} {sym} {dirn} | CTI Strategy"
        desc  = f"Confidence: **{conf_pct}%**"
        fields = [
            {"name": "Entry",   "value": str(signal.entry_price), "inline": True},
            {"name": "SL",      "value": f"{signal.stop_loss} ({signal.atr:.5f} ATR)", "inline": True},
            {"name": "TP",      "value": f"{signal.take_profit} ({signal.atr:.5f} ATR)", "inline": True},
            {"name": "Size",    "value": f"{signal.lot_size} lots", "inline": True},
            {"name": "Risk",    "value": f"{signal.risk_pct:.2f}%", "inline": True},
            {"name": "Mode",    "value": MODE, "inline": True},
        ]

        if signal.patterns_found:
            patterns_str = ", ".join(signal.patterns_found)
            fields.append({"name": "Patterns", "value": patterns_str, "inline": False})

        # Layer 2 breakdown
        br = signal.breakdown
        score_lines = "\n".join(
            f"• {k}: {v}" for k, v in br.items()
        )
        fields.append({"name": "Layer 2 Scoring", "value": score_lines, "inline": False})

    return {
        "embeds": [{
            "title": title,
            "description": desc,
            "color": color,
            "fields": fields,
            "footer": {"text": f"TradeGumi {MODE}"},
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


def post_watchlist(watchlist_text: str, json_path: str | None = None) -> bool:
    """Post the morning pre-session watchlist to Discord with JSON attachment."""
    payload = {
        "content": watchlist_text,
        "embeds": [{
            "title": "🌅 Morning Watchlist — TradeGumi",
            "color": 0x1E90FF,
            "footer": {"text": f"TradeGumi {MODE}"},
        }]
    }

    if json_path:
        try:
            with open(json_path, "rb") as f:
                files = {"file": ("watchlist.json", f, "application/json")}
                # When sending files, payload goes as form_data["payload_json"]
                resp = requests.post(
                    WEBHOOK_URL,
                    data={"payload_json": json.dumps(payload)},
                    files=files,
                    timeout=15,
                )
                resp.raise_for_status()
                return True
        except Exception as e:
            log.error("Discord webhook (file attach) error: %s — falling back to text-only", e)
            return _post(payload)
    else:
        return _post(payload)


def post_blocked_signal(signal: Signal, reason: str) -> bool:
    """Log and post a blocked signal with the reason."""
    signal.blocked_reason = reason
    log.info("Signal blocked for %s: %s", signal.symbol, reason)
    return post_signal(signal)
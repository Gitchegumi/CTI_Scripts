"""TradeGumi Callback — sends structured signal data to DockeGumi.

When a signal fires, TradeGumi posts the full signal context to DockeGumi's
webhook endpoint. This allows DockeGumi to:
  - Receive signals in real time
  - Make decisions (escalate, suppress, adjust risk)
  - Send commands back via TradeGumi's API (/api/config/*, /api/action/*)

The callback is fire-and-forget. Failures are logged but don't block the bot.
"""
import json
import logging as log
import threading
from typing import Any

import urllib.request
import urllib.error

from tradegumi import config


def send_callback(event_type: str, payload: dict[str, Any]) -> None:
    """POST a structured event to DockeGumi (or any callback URL).

    Args:
        event_type: One of "signal", "rescan", "mode_change", "trade_open",
                    "trade_close", "status", "closed_market"
        payload: Event-specific data dict

    The callback URL is configured via TRADEGUMI_CALLBACK_URL env var.
    If empty, this is a no-op.
    """
    url = config.CALLBACK_URL
    if not url:
        return

    body = json.dumps({
        "source": "tradegumi",
        "version": 1,
        "event_type": event_type,
        "payload": payload,
    }, default=str).encode()

    def _post():
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status >= 300:
                    log.warning("Callback returned %d for %s", resp.status, event_type)
                else:
                    log.debug("Callback sent: %s (%d bytes)", event_type, len(body))
        except urllib.error.URLError as e:
            log.warning("Callback failed for %s: %s", event_type, e.reason)
        except Exception as e:
            log.warning("Callback error for %s: %s", event_type, e)

    # Fire-and-forget in background thread
    threading.Thread(target=_post, daemon=True).start()


def send_signal_callback(signal_data: dict) -> None:
    """Convenience: send a trade signal event."""
    send_callback("signal", signal_data)


def send_rescan_callback(scan_result: dict) -> None:
    """Convenience: send a re-scan event."""
    send_callback("rescan", scan_result)


def send_mode_change_callback(mode: str, previous_mode: str) -> None:
    """Convenience: send a mode change event."""
    send_callback("mode_change", {"mode": mode, "previous_mode": previous_mode})


def send_trade_callback(action: str, trade_data: dict) -> None:
    """Convenience: send a trade open/close event."""
    send_callback(f"trade_{action}", trade_data)


def send_status_callback(status: dict) -> None:
    """Convenience: send a periodic status heartbeat."""
    send_callback("status", status)


def send_closed_market_callback(day_name: str, message: str) -> None:
    """Convenience: send a closed-market notification."""
    send_callback("closed_market", {"day": day_name, "message": message})
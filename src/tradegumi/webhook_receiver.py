"""DockeGumi TradeGumi Webhook Receiver.

Receives structured events from TradeGumi running on TrueNAS.
Interprets signals and takes automated action:
  - Escalate high-confidence signals to GitcheGumi via Discord
  - Auto-switch modes based on risk thresholds
  - Track signal statistics and alert on anomalies

Runs as part of the DockeGumi API server on port 8198.
"""
import json
import logging as log
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

WEBHOOK_PORT = 8198
DATA_DIR = Path(__file__).parent.parent / "repos" / "CTI_Scripts" / "src" / "tradegumi" / "data"

# ── Signal statistics ────────────────────────────────────────────────────────
_signal_stats: dict[str, Any] = {
    "total_signals": 0,
    "blocked_signals": 0,
    "by_symbol": {},
    "by_direction": {"long": 0, "short": 0},
    "last_signal_time": None,
}


def process_event(event: dict) -> dict:
    """Process an incoming TradeGumi event and return action instructions."""
    event_type = event.get("event_type", "")
    payload = event.get("payload", {})

    if event_type == "signal":
        return _handle_signal(payload)
    elif event_type == "mode_change":
        return _handle_mode_change(payload)
    elif event_type == "rescan":
        return _handle_rescan(payload)
    elif event_type == "closed_market":
        return _handle_closed_market(payload)
    else:
        log.info("Unknown event type: %s", event_type)
        return {"status": "ack", "action": "none"}


def _handle_signal(payload: dict) -> dict:
    """Process a trade signal."""
    symbol = payload.get("symbol", "???")
    direction = payload.get("direction", "???")
    confidence = payload.get("confidence", 0)
    blocked = payload.get("blocked")
    mode = payload.get("mode", "alert_only")

    _signal_stats["total_signals"] += 1
    _signal_stats["last_signal_time"] = payload.get("timestamp")
    _signal_stats["by_symbol"][symbol] = _signal_stats["by_symbol"].get(symbol, 0) + 1
    if direction.lower() in _signal_stats["by_direction"]:
        _signal_stats["by_direction"][direction.lower()] += 1

    if blocked:
        _signal_stats["blocked_signals"] += 1
        log.info("Signal BLOCKED: %s %s (conf=%.2f, reason=%s)", direction, symbol, confidence, blocked)
        return {"status": "ack", "action": "blocked_logged"}
    else:
        log.info("Signal: %s %s (conf=%.2f, mode=%s)", direction, symbol, confidence, mode)

        # High-confidence escalation
        if confidence >= 0.85 and mode in ("demo", "live"):
            log.info("HIGH CONFIDENCE: %.2f — escalating to GitcheGumi", confidence)
            return {"status": "ack", "action": "escalate", "confidence": confidence}

        return {"status": "ack", "action": "logged"}


def _handle_mode_change(payload: dict) -> dict:
    """Process a mode change event."""
    mode = payload.get("mode", "???")
    previous = payload.get("previous_mode", "???")
    log.info("Mode changed: %s → %s", previous, mode)

    # Alert on live mode activation
    if mode == "live" and previous != "live":
        log.warning("⚠️ TradeGumi switched to LIVE mode!")
        return {"status": "ack", "action": "live_mode_alert"}

    return {"status": "ack", "action": "mode_change_logged"}


def _handle_rescan(payload: dict) -> dict:
    """Process a re-scan event."""
    trigger = payload.get("trigger", "unknown")
    log.info("Watchlist re-scan complete (trigger: %s)", trigger)
    return {"status": "ack", "action": "rescan_logged"}


def _handle_closed_market(payload: dict) -> dict:
    """Process a closed-market event."""
    day = payload.get("day", "???")
    log.info("Market closed: %s", day)
    return {"status": "ack", "action": "closed_market_logged"}


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for TradeGumi webhook callbacks."""

    def log_message(self, format, *args):
        log.debug("Webhook: %s", format % args)

    def do_POST(self):
        if self.path != "/api/tradegumi/webhook":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        try:
            event = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid json"}).encode())
            return

        result = process_event(event)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def start_webhook_server(port: int = WEBHOOK_PORT) -> HTTPServer:
    """Start the webhook receiver server."""
    import threading
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("TradeGumi webhook receiver started on port %d", port)
    return server
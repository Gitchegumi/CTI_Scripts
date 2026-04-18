"""TradeGumi HTTP API — lightweight config + control server.

Serves loop_state.json, watchlist.json, signals.json for the dashboard,
and accepts POST requests to change mode, program, phase, and trigger re-scans.

Runs on port 8199 by default.
"""
import json
import logging as log
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from tradegumi import config

DATA_DIR = Path(__file__).parent / "data"
API_PORT = int(__import__("os").getenv("TRADEGUMI_API_PORT", "8199"))

# ── Shared runtime state (set from main.py) ────────────────────────────────
_runtime_state: dict = {}
_runtime_lock = threading.Lock()


def set_runtime_state(state: dict) -> None:
    """Called from main.py to share the current runtime state."""
    with _runtime_lock:
        _runtime_state.update(state)


def get_runtime_state() -> dict:
    with _runtime_lock:
        return dict(_runtime_state)


class TradeGumiAPIHandler(BaseHTTPRequestHandler):
    """Minimal REST API for dashboard config and data."""

    def log_message(self, format, *args):
        log.debug("API: %s", format % args)

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    # ── GET endpoints ──────────────────────────────────────────────────────

    def do_GET(self):

        if self.path == "/api/status":
            # Current config + runtime state
            state = get_runtime_state()
            self._send_json({
                "mode": config.TRADEGUMI_MODE,
                "program": config.CTI_PROGRAM,
                "phase": config.CTI_PHASE,
                "daily_loss_pct": config.CTI_DAILY_LOSS_PCT,
                "max_dd_pct": config.CTI_MAX_DD_PCT,
                "running": state.get("running", False),
                "loop_count": state.get("loop_count", 0),
                "last_signal_time": state.get("last_signal_time"),
            })
            return

        if self.path == "/api/data/loop_state":
            f = DATA_DIR / "loop_state.json"
            if f.exists():
                self._send_json(json.loads(f.read_text()))
            else:
                self._send_json({"symbols": [], "mode": config.TRADEGUMI_MODE, "provider": "Oanda"})
            return

        if self.path == "/api/data/watchlist":
            f = DATA_DIR / "watchlist.json"
            if f.exists():
                self._send_json(json.loads(f.read_text()))
            else:
                self._send_json({"tier1": [], "tier2": [], "below": [], "ranked": []})
            return

        if self.path == "/api/data/signals":
            f = DATA_DIR / "signals.json"
            if f.exists():
                self._send_json(json.loads(f.read_text()))
            else:
                self._send_json([])
            return

        self._send_json({"error": "not found"}, 404)

    # ── POST endpoints ────────────────────────────────────────────────────

    def do_POST(self):
        body = self._read_body()

        if self.path == "/api/config/mode":
            mode = body.get("mode", "").lower()
            if mode not in ("alert_only", "demo", "live"):
                self._send_json({"error": "invalid mode. Use: alert_only, demo, live"}, 400)
                return
            config.TRADEGUMI_MODE = mode
            # Also update .env file
            _update_env("TRADEGUMI_MODE", mode)
            log.info("API: Mode changed to %s", mode)
            self._send_json({"mode": config.TRADEGUMI_MODE})

        elif self.path == "/api/config/program":
            program = body.get("program", "").lower()
            if program not in ("challenge", "instant"):
                self._send_json({"error": "invalid program. Use: challenge, instant"}, 400)
                return
            config.CTI_PROGRAM = program
            _update_env("CTI_PROGRAM", program)
            # If instant, phase doesn't matter
            log.info("API: Program changed to %s", program)
            self._send_json({"program": config.CTI_PROGRAM, "phase": config.CTI_PHASE})

        elif self.path == "/api/config/phase":
            phase = body.get("phase")
            if phase is None or int(phase) not in (1, 2, 3):
                self._send_json({"error": "invalid phase. Use: 1, 2, or 3"}, 400)
                return
            config.CTI_PHASE = int(phase)
            _update_env("CTI_PHASE", str(config.CTI_PHASE))
            log.info("API: Phase changed to %d", config.CTI_PHASE)
            self._send_json({"phase": config.CTI_PHASE, "program": config.CTI_PROGRAM})

        elif self.path == "/api/action/rescan":
            # Trigger an immediate re-scan
            state = get_runtime_state()
            state["force_rescan"] = True
            set_runtime_state(state)
            log.info("API: Re-scan triggered via API")
            self._send_json({"status": "rescan_triggered"})

        elif self.path == "/api/action/restart":
            # Signal main loop to restart (set flag)
            state = get_runtime_state()
            state["restart_requested"] = True
            set_runtime_state(state)
            log.info("API: Restart requested via API")
            self._send_json({"status": "restart_requested"})

        else:
            self._send_json({"error": "not found"}, 404)


def _update_env(key: str, value: str) -> None:
    """Update .env file with a new value, creating the file if needed."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    lines = []
    if env_path.exists():
        with open(env_path) as f:
            lines = f.readlines()

    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    # Also update the runtime environment
    import os
    os.environ[key] = value


def start_api_server(port: int = API_PORT) -> HTTPServer:
    """Start the API server in a background thread."""
    server = HTTPServer(("0.0.0.0", port), TradeGumiAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("API server started on port %d", port)
    return server
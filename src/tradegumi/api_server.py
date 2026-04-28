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
from typing import Any, Optional

from tradegumi import config
from tradegumi.manual_trades import _now_iso as manual_now_iso

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

    def _check_auth(self) -> bool:
        """Verify X-API-Key header against JOURNAL_TOKEN."""
        expected = config.JOURNAL_TOKEN
        if not expected:
            return True  # No auth required if not configured
        provided = self.headers.get("X-API-Key", "")
        return provided == expected

    def _require_auth(self) -> bool:
        """Send 401 if auth fails. Returns True if authenticated."""
        if not self._check_auth():
            self._send_json({"error": "Unauthorized"}, 401)
            return False
        return True

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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _get_query_param(self, name: str) -> Optional[str]:
        """Extract a query parameter from the path."""
        if "?" not in self.path:
            return None
        qs = self.path.split("?", 1)[1]
        for pair in qs.split("&"):
            if pair.startswith(f"{name}="):
                return pair.split("=", 1)[1]
        return None

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
                "challenge_type": config.CTI_CHALLENGE_TYPE,
                "program": config.CTI_PROGRAM,
                "phase": config.CTI_PHASE,
                "daily_loss_pct": config.CTI_DAILY_LOSS_PCT,
                "max_dd_pct": config.CTI_MAX_DD_PCT,
                "running": state.get("running", False),
                "loop_count": state.get("loop_count", 0),
                "last_signal_time": state.get("last_signal_time"),
                "tiers": config.CTI_CHALLENGE_TIERS if config.CTI_CHALLENGE_TYPE != "instant" else config.CTI_INSTANT_TIERS,
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

        if self.path == "/api/data/journal":
            f = DATA_DIR / "signal_journal.jsonl"
            if f.exists():
                entries = []
                for line in f.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                # Newest first
                self._send_json(list(reversed(entries)))
            else:
                self._send_json([])
            return

        # ── Live API endpoints (require Oanda client) ──
        if self.path == "/api/positions":
            client = get_runtime_state().get("client")
            if not client:
                self._send_json({"error": "client not available"}, 503)
                return
            try:
                positions = client.get_open_positions()
                self._send_json([{
                    "id": p.id,
                    "symbol": p.symbol,
                    "side": p.side,
                    "volume": p.volume,
                    "open_price": p.open_price,
                    "current_price": p.current_price,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "unrealized_pl": p.unrealized_pl,
                    "net_profit": p.net_profit,
                } for p in positions])
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if self.path.startswith("/api/trades") and not self.path.startswith("/api/trades/manual"):
            client = get_runtime_state().get("client")
            if not client:
                self._send_json({"error": "client not available"}, 503)
                return
            # Parse count from query string
            count = 50
            if "?" in self.path:
                qs = self.path.split("?", 1)[1]
                for pair in qs.split("&"):
                    if pair.startswith("count="):
                        count = int(pair.split("=")[1])
            try:
                trades = client.get_trade_history(count=count)
                self._send_json([{
                    "id": t.id,
                    "symbol": t.symbol,
                    "side": t.side,
                    "volume": t.volume,
                    "open_price": t.open_price,
                    "close_price": t.close_price,
                    "open_time": t.open_time,
                    "close_time": t.close_time,
                    "realized_pl": t.realized_pl,
                    "financing": t.financing,
                    "pnl": t.pnl,
                } for t in trades])
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        # Manual trades endpoints — require auth
        if self.path == "/api/trades/manual":
            if not self._require_auth():
                return
            # GET /api/trades/manual — list manual trades with filters
            try:
                from tradegumi.manual_trades import get_all_trades
                symbol = self._get_query_param("symbol")
                status = self._get_query_param("status")
                start_date = self._get_query_param("start_date")
                end_date = self._get_query_param("end_date")
                limit = int(self._get_query_param("limit") or 100)
                
                trades = get_all_trades(
                    symbol=symbol or None,
                    status=status or None,
                    start_date=start_date or None,
                    end_date=end_date or None,
                    limit=limit
                )
                self._send_json(trades)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if self.path == "/api/trades/manual/stats":
            if not self._require_auth():
                return
            # GET /api/trades/manual/stats — summary statistics
            try:
                from tradegumi.manual_trades import get_summary_stats
                self._send_json(get_summary_stats())
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        self._send_json({"error": "not found"}, 404)

    def do_PUT(self):
        body = self._read_body()
        
        if self.path.startswith("/api/trades/manual/"):
            # PUT /api/trades/manual/:id — update trade
            if not self._require_auth():
                return
            parts = self.path.split("/")
            if len(parts) >= 5:
                trade_id_str = parts[4]
                try:
                    trade_id = int(trade_id_str)
                except ValueError:
                    self._send_json({"error": "Invalid trade ID"}, 400)
                    return
                
                try:
                    from tradegumi.manual_trades import update_trade
                    symbol = body.get("symbol")
                    direction = body.get("direction", "").lower() if body.get("direction") else None
                    entry_price = body.get("entry_price")
                    if entry_price is not None:
                        entry_price = float(entry_price)
                    exit_price = body.get("exit_price")
                    if exit_price is not None:
                        exit_price = float(exit_price)
                    entry_time = body.get("entry_time")
                    exit_time = body.get("exit_time")
                    notes = body.get("notes")
                    
                    updated = update_trade(
                        trade_id=trade_id,
                        symbol=symbol,
                        direction=direction if direction else None,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        entry_time=entry_time,
                        exit_time=exit_time,
                        notes=notes
                    )
                    if updated:
                        self._send_json(updated)
                    else:
                        self._send_json({"error": "Trade not found"}, 404)
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
            else:
                self._send_json({"error": "not found"}, 404)
            return
        
        self._send_json({"error": "Method not allowed"}, 405)

    def do_DELETE(self):
        if self.path.startswith("/api/trades/manual/"):
            # DELETE /api/trades/manual/:id — delete trade
            if not self._require_auth():
                return
            parts = self.path.split("/")
            if len(parts) >= 5:
                trade_id_str = parts[4]
                try:
                    trade_id = int(trade_id_str)
                except ValueError:
                    self._send_json({"error": "Invalid trade ID"}, 400)
                    return
                
                try:
                    from tradegumi.manual_trades import delete_trade
                    deleted = delete_trade(trade_id)
                    if deleted:
                        self._send_json({"ok": True})
                    else:
                        self._send_json({"error": "Trade not found"}, 404)
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
            else:
                self._send_json({"error": "not found"}, 404)
            return
        
        self._send_json({"error": "Method not allowed"}, 405)

    # ── POST endpoints ────────────────────────────────────────────────────

    def do_POST(self):
        body = self._read_body()

        if self.path == "/api/config/mode":
            mode = body.get("mode", "").lower()
            if mode not in ("alert_only", "demo", "live"):
                self._send_json({"error": "invalid mode. Use: alert_only, demo, live"}, 400)
                return
            previous = config.TRADEGUMI_MODE
            config.TRADEGUMI_MODE = mode
            _update_env("TRADEGUMI_MODE", mode)
            log.info("API: Mode changed from %s to %s", previous, mode)
            # Notify DockeGumi
            from tradegumi.callback import send_mode_change_callback
            send_mode_change_callback(mode, previous)
            self._send_json({"mode": config.TRADEGUMI_MODE})

        elif self.path == "/api/config/challenge_type":
            challenge_type = body.get("challenge_type", "").lower()
            if challenge_type not in ("1-step", "2-step", "instant"):
                self._send_json({"error": "invalid challenge_type. Use: 1-step, 2-step, or instant"}, 400)
                return
            config.CTI_CHALLENGE_TYPE = challenge_type
            _update_env("CTI_CHALLENGE_TYPE", challenge_type)
            log.info("API: Challenge type changed to %s", challenge_type)
            # Immediately refresh account metrics in watchlist.json
            client = get_runtime_state().get("client")
            if client:
                from tradegumi.pre_session_scanner import refresh_account_metrics
                metrics = refresh_account_metrics(client)
                if metrics:
                    log.info("API: Account metrics refreshed immediately")
            self._send_json({
                "challenge_type": config.CTI_CHALLENGE_TYPE,
                "phase": config.CTI_PHASE,
            })

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
            # Immediately refresh account metrics in watchlist.json
            client = get_runtime_state().get("client")
            if client:
                from tradegumi.pre_session_scanner import refresh_account_metrics
                metrics = refresh_account_metrics(client)
                if metrics:
                    log.info("API: Account metrics refreshed immediately")
            self._send_json({"phase": config.CTI_PHASE, "program": config.CTI_PROGRAM})

        elif self.path == "/api/journal/grade":
            signal_id = body.get("signal_id", "").strip()
            grade = body.get("grade", "").strip().upper()
            notes = body.get("notes", "").strip()
            if not signal_id or not grade:
                self._send_json({"error": "signal_id and grade are required"}, 400)
                return
            from tradegumi.journal import grade_by_signal_id
            ok = grade_by_signal_id(signal_id, grade, notes)
            if ok:
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Signal not found or invalid grade"}, 404)

        elif self.path == "/api/journal/notes":
            signal_id = body.get("signal_id", "").strip()
            notes = body.get("notes", "").strip()
            if not signal_id:
                self._send_json({"error": "signal_id is required"}, 400)
                return
            from tradegumi.journal import set_notes_by_signal_id
            ok = set_notes_by_signal_id(signal_id, notes)
            if ok:
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Signal not found"}, 404)

        elif self.path == "/api/trades/manual":
            # POST /api/trades/manual — create new manual trade
            if not self._require_auth():
                return
            try:
                from tradegumi.manual_trades import create_trade
                symbol = body.get("symbol", "").strip().upper()
                direction = body.get("direction", "").lower()
                entry_price = float(body.get("entry_price", 0))
                exit_price = body.get("exit_price")
                if exit_price is not None:
                    exit_price = float(exit_price)
                entry_time = body.get("entry_time", manual_now_iso())
                exit_time = body.get("exit_time")
                notes = body.get("notes", "")
                
                if not symbol or direction not in ("long", "short"):
                    self._send_json({"error": "symbol and direction (long/short) are required"}, 400)
                    return
                
                if exit_price is not None and not exit_time:
                    exit_time = manual_now_iso()
                
                trade = create_trade(
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    entry_time=entry_time,
                    exit_price=exit_price,
                    exit_time=exit_time,
                    notes=notes
                )
                self._send_json(trade, status=201)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        elif self.path.startswith("/api/trades/manual/"):
            # PUT/DELETE are handled by do_PUT/do_DELETE
            self._send_json({"error": "Method not allowed — use PUT or DELETE"}, 405)
            return

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
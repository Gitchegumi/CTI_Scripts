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
from urllib.parse import parse_qs, unquote, urlparse

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
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            log.debug("API: client disconnected before JSON response completed")
            self.close_connection = True

    def _send_text(
        self,
        body: str,
        content_type: str = "text/plain; charset=utf-8",
        status: int = 200,
        extra_headers: Optional[dict[str, str]] = None,
    ):
        """Send a text response for non-JSON exports."""
        encoded = body.encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Access-Control-Allow-Origin", "*")
            for name, value in (extra_headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            log.debug("API: client disconnected before text response completed")
            self.close_connection = True

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
        values = parse_qs(urlparse(self.path).query)
        if name not in values or not values[name]:
            return None
        return values[name][0]

    def _route_path(self) -> str:
        """Return the request path without query parameters."""
        path = urlparse(self.path).path
        if path == "/api/manual-trades":
            return "/api/trades/manual"
        if path.startswith("/api/manual-trades/"):
            return f"/api/trades/manual/{path.removeprefix('/api/manual-trades/')}"
        return path

    def _source_trade_history(self, count: int = 1000) -> list:
        """Return broker/source trade history when a runtime client is available."""
        client = get_runtime_state().get("client")
        if not client:
            return []
        safe_count = max(1, min(int(count or 50), 500))
        try:
            return client.get_trade_history(count=safe_count)
        except Exception as e:
            log.warning("API: could not load source trade history: %s", e)
            return []

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    # ── GET endpoints ──────────────────────────────────────────────────────

    def do_GET(self):
        path = self._route_path()

        if path == "/api/status":
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
                "market_data": state.get("market_data"),
                "tiers": config.CTI_CHALLENGE_TIERS if config.CTI_CHALLENGE_TYPE != "instant" else config.CTI_INSTANT_TIERS,
            })
            return

        if path == "/api/data/loop_state":
            runtime_loop_state = get_runtime_state().get("loop_state")
            if runtime_loop_state is not None:
                self._send_json(runtime_loop_state)
                return
            f = DATA_DIR / "loop_state.json"
            if f.exists():
                self._send_json(json.loads(f.read_text()))
            else:
                self._send_json({"symbols": [], "mode": config.TRADEGUMI_MODE, "provider": "Oanda"})
            return

        if path == "/api/data/watchlist":
            f = DATA_DIR / "watchlist.json"
            if f.exists():
                self._send_json(json.loads(f.read_text()))
            else:
                self._send_json({"tier1": [], "tier2": [], "below": [], "ranked": []})
            return

        if path == "/api/data/signals":
            f = DATA_DIR / "signals.json"
            if f.exists():
                self._send_json(json.loads(f.read_text()))
            else:
                self._send_json([])
            return

        if path.startswith("/api/strategy-metrics/summary"):
            try:
                from tradegumi.strategy_metrics import get_summary
                start = self._get_query_param("start")
                end = self._get_query_param("end")
                symbol = self._get_query_param("symbol")
                strategy = self._get_query_param("strategy")
                signal_type = self._get_query_param("signal_type")
                decision = self._get_query_param("decision")
                first_blocker = self._get_query_param("first_blocker")
                if not start or not end:
                    self._send_json({"error": "start and end are required"}, 400)
                    return
                self._send_json(get_summary(
                    start,
                    end,
                    symbol=symbol or None,
                    strategy=strategy or None,
                    signal_type=signal_type or None,
                    decision=decision or None,
                    first_blocker=first_blocker or None,
                ))
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path.startswith("/api/strategy-metrics/opportunities"):
            try:
                from tradegumi.strategy_metrics import get_opportunities
                start = self._get_query_param("start")
                end = self._get_query_param("end")
                symbol = self._get_query_param("symbol")
                decision = self._get_query_param("decision")
                strategy = self._get_query_param("strategy")
                signal_type = self._get_query_param("signal_type")
                first_blocker = self._get_query_param("first_blocker")
                near_miss_param = self._get_query_param("near_miss")
                limit = int(self._get_query_param("limit") or 100)
                offset = int(self._get_query_param("offset") or 0)
                near_miss = None
                if near_miss_param is not None:
                    near_miss = near_miss_param.lower() == "true"
                if not start or not end:
                    self._send_json({"error": "start and end are required"}, 400)
                    return
                self._send_json(get_opportunities(
                    start,
                    end,
                    symbol=symbol or None,
                    decision=decision or None,
                    strategy=strategy or None,
                    signal_type=signal_type or None,
                    first_blocker=first_blocker or None,
                    near_miss=near_miss,
                    limit=limit,
                    offset=offset,
                ))
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path.startswith("/api/strategy-metrics/compare"):
            try:
                from tradegumi.strategy_metrics import compare_periods
                base_start = self._get_query_param("base_start")
                base_end = self._get_query_param("base_end")
                compare_start = self._get_query_param("compare_start")
                compare_end = self._get_query_param("compare_end")
                symbol = self._get_query_param("symbol")
                if not all([base_start, base_end, compare_start, compare_end]):
                    self._send_json({"error": "base_start, base_end, compare_start, and compare_end are required"}, 400)
                    return
                self._send_json(compare_periods(base_start, base_end, compare_start, compare_end, symbol=symbol or None))
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path.startswith("/api/strategy-metrics/export"):
            try:
                from tradegumi.strategy_metrics import export_summary
                start = self._get_query_param("start")
                end = self._get_query_param("end")
                symbol = self._get_query_param("symbol")
                strategy = self._get_query_param("strategy")
                signal_type = self._get_query_param("signal_type")
                decision = self._get_query_param("decision")
                first_blocker = self._get_query_param("first_blocker")
                include = (self._get_query_param("include_opportunities") or "false").lower() == "true"
                if not start or not end:
                    self._send_json({"error": "start and end are required"}, 400)
                    return
                self._send_json(export_summary(
                    start,
                    end,
                    symbol=symbol or None,
                    strategy=strategy or None,
                    signal_type=signal_type or None,
                    decision=decision or None,
                    first_blocker=first_blocker or None,
                    include_opportunities=include,
                ))
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path.startswith("/api/strategy-metrics/criteria/"):
            try:
                from tradegumi.strategy_metrics import get_criterion_detail
                criterion_name = path.split("/api/strategy-metrics/criteria/")[1]
                start = self._get_query_param("start")
                end = self._get_query_param("end")
                symbol = self._get_query_param("symbol")
                decision = self._get_query_param("decision")
                near_miss_param = self._get_query_param("near_miss")
                first_blocker = self._get_query_param("first_blocker")
                limit = int(self._get_query_param("limit") or 50)
                offset = int(self._get_query_param("offset") or 0)
                near_miss = None
                if near_miss_param is not None:
                    near_miss = near_miss_param.lower() == "true"
                if not start or not end:
                    self._send_json({"error": "start and end are required"}, 400)
                    return
                self._send_json(get_criterion_detail(
                    start,
                    end,
                    criterion_name,
                    symbol=symbol or None,
                    decision=decision or None,
                    near_miss=near_miss,
                    first_blocker=first_blocker or None,
                    limit=limit,
                    offset=offset,
                ))
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path.startswith("/api/strategy-metrics/criteria"):
            try:
                from tradegumi.strategy_metrics import get_criteria_list
                start = self._get_query_param("start")
                end = self._get_query_param("end")
                symbol = self._get_query_param("symbol")
                strategy = self._get_query_param("strategy")
                signal_type = self._get_query_param("signal_type")
                decision = self._get_query_param("decision")
                first_blocker = self._get_query_param("first_blocker")
                if not start or not end:
                    self._send_json({"error": "start and end are required"}, 400)
                    return
                self._send_json(get_criteria_list(
                    start,
                    end,
                    symbol=symbol or None,
                    strategy=strategy or None,
                    signal_type=signal_type or None,
                    decision=decision or None,
                    first_blocker=first_blocker or None,
                ))
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path == "/api/data/journal":
            from tradegumi.journal import read_journal
            self._send_json(read_journal())
            return

        if path == "/api/journal/export":
            if not self._require_auth():
                return
            try:
                from tradegumi.journal import SignalJournalExportSelection, build_journal_export
                selection = SignalJournalExportSelection(
                    grade=self._get_query_param("grade"),
                    start=self._get_query_param("start"),
                    end=self._get_query_param("end"),
                    symbol=self._get_query_param("symbol"),
                    status=self._get_query_param("status"),
                    final_decision=self._get_query_param("final_decision"),
                    strategy=self._get_query_param("strategy"),
                    mode=self._get_query_param("mode"),
                    graded_state=self._get_query_param("graded_state"),
                )
                export = build_journal_export(selection)
                if export.record_count == 0:
                    self._send_json({"error": "No Signal Journal records match the selected export range."}, 404)
                    return
                self._send_text(
                    export.csv_text,
                    export.content_type,
                    extra_headers={"Content-Disposition": export.content_disposition},
                )
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path == "/api/data/trade_correlations":
            f = DATA_DIR / "trade_correlations.json"
            if f.exists():
                try:
                    self._send_json(json.loads(f.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    self._send_json([])
            else:
                self._send_json([])
            return

        # ── Live API endpoints (require Oanda client) ──
        if path == "/api/prices":
            from tradegumi.price_observations import DEFAULT_PRICE_HISTORY
            symbols = [s.strip().upper() for s in (self._get_query_param("symbols") or "").split(",") if s.strip()]
            observations = DEFAULT_PRICE_HISTORY.latest_many(symbols).values() if symbols else []
            self._send_json([observation.to_dict() for observation in observations])
            return

        if path == "/api/positions":
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

        if path == "/api/trades/history":
            if not self._require_auth():
                return
            try:
                from tradegumi.manual_trades import get_dashboard_trade_history
                count = int(self._get_query_param("count") or self._get_query_param("limit") or 50)
                source_trades = self._source_trade_history(count=max(count, 1000))
                history_params = {
                    "bot_mode": config.TRADEGUMI_MODE,
                    "symbol": self._get_query_param("symbol") or None,
                    "tag": self._get_query_param("tag") or None,
                    "start_date": self._get_query_param("start_date") or None,
                    "end_date": self._get_query_param("end_date") or None,
                    "count": count,
                }
                try:
                    history = get_dashboard_trade_history(source_trades=source_trades, **history_params)
                except Exception as merge_error:
                    log.warning("API: source trade history could not be merged for dashboard: %s", merge_error)
                    history = get_dashboard_trade_history(source_trades=[], **history_params)
                self._send_json(history)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path.startswith("/api/trades") and not path.startswith("/api/trades/manual"):
            client = get_runtime_state().get("client")
            if not client:
                self._send_json({"error": "client not available"}, 503)
                return
            # Parse count from query string
            count = 50
            count_param = self._get_query_param("count")
            if count_param:
                count = int(count_param)
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
        if path == "/api/trades/manual":
            if not self._require_auth():
                return
            # GET /api/trades/manual — list manual trades with filters
            try:
                from tradegumi.manual_trades import get_all_trades
                symbol = self._get_query_param("symbol")
                status = self._get_query_param("status")
                start_date = self._get_query_param("start_date")
                end_date = self._get_query_param("end_date")
                tag = self._get_query_param("tag")
                limit = int(self._get_query_param("limit") or 100)
                source_trades = self._source_trade_history(count=max(limit, 1000))
                
                trades = get_all_trades(
                    symbol=symbol or None,
                    status=status or None,
                    start_date=start_date or None,
                    end_date=end_date or None,
                    tag=tag or None,
                    limit=limit,
                    bot_mode=config.TRADEGUMI_MODE,
                    source_trades=source_trades,
                )
                self._send_json(trades)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path == "/api/trades/manual/export":
            if not self._require_auth():
                return
            try:
                from tradegumi.manual_trades import export_agent_data
                limit = int(self._get_query_param("limit") or 1000)
                source_trades = self._source_trade_history(count=max(limit, 1000))
                self._send_json(export_agent_data(
                    source_trades=source_trades,
                    bot_mode=config.TRADEGUMI_MODE,
                    symbol=self._get_query_param("symbol") or None,
                    status=self._get_query_param("status") or None,
                    tag=self._get_query_param("tag") or None,
                    start_date=self._get_query_param("start_date") or None,
                    end_date=self._get_query_param("end_date") or None,
                    limit=limit,
                ))
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path == "/api/trades/manual/stats":
            if not self._require_auth():
                return
            # GET /api/trades/manual/stats — summary statistics
            try:
                from tradegumi.manual_trades import get_summary_stats
                source_trades = self._source_trade_history(count=1000)
                self._send_json(get_summary_stats(
                    source_trades=source_trades,
                    bot_mode=config.TRADEGUMI_MODE,
                ))
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        self._send_json({"error": "not found"}, 404)

    def do_PUT(self):
        body = self._read_body()
        path = self._route_path()
        
        if path.startswith("/api/trades/manual/"):
            # PUT /api/trades/manual/:id — update trade
            if not self._require_auth():
                return
            parts = path.split("/")
            if len(parts) >= 5:
                trade_identity = unquote(parts[4])
                try:
                    from tradegumi.manual_trades import (
                        TradeNotFoundError,
                        TradePermissionError,
                        update_trade_record,
                    )
                    updated = update_trade_record(
                        trade_identity,
                        body,
                        bot_mode=config.TRADEGUMI_MODE,
                        source_trades=self._source_trade_history(count=1000),
                    )
                    self._send_json(updated)
                except TradePermissionError as e:
                    self._send_json({"error": str(e)}, 403)
                except TradeNotFoundError as e:
                    self._send_json({"error": str(e)}, 404)
                except ValueError as e:
                    self._send_json({"error": str(e)}, 400)
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
            else:
                self._send_json({"error": "not found"}, 404)
            return
        
        self._send_json({"error": "Method not allowed"}, 405)

    def do_DELETE(self):
        path = self._route_path()
        if path == "/api/journal":
            if not self._require_auth():
                return
            try:
                from tradegumi.journal import purge_journal_entries
                self._send_json(purge_journal_entries(self._get_query_param("grade")))
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path.startswith("/api/trades/manual/"):
            # DELETE /api/trades/manual/:id — delete trade
            if not self._require_auth():
                return
            parts = path.split("/")
            if len(parts) >= 5:
                trade_identity = unquote(parts[4])
                try:
                    from tradegumi.manual_trades import (
                        TradeNotFoundError,
                        TradePermissionError,
                        delete_trade_record,
                    )
                    delete_trade_record(trade_identity, bot_mode=config.TRADEGUMI_MODE)
                    self._send_json({"ok": True})
                except TradePermissionError as e:
                    self._send_json({"error": str(e)}, 403)
                except TradeNotFoundError as e:
                    self._send_json({"error": str(e)}, 404)
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
            else:
                self._send_json({"error": "not found"}, 404)
            return
        
        self._send_json({"error": "Method not allowed"}, 405)

    # ── POST endpoints ────────────────────────────────────────────────────

    def do_POST(self):
        body = self._read_body()
        path = self._route_path()

        if path == "/api/config/mode":
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

        elif path == "/api/config/challenge_type":
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

        elif path == "/api/config/program":
            program = body.get("program", "").lower()
            if program not in ("challenge", "instant"):
                self._send_json({"error": "invalid program. Use: challenge, instant"}, 400)
                return
            config.CTI_PROGRAM = program
            _update_env("CTI_PROGRAM", program)
            # If instant, phase doesn't matter
            log.info("API: Program changed to %s", program)
            self._send_json({"program": config.CTI_PROGRAM, "phase": config.CTI_PHASE})

        elif path == "/api/config/phase":
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

        elif path == "/api/journal/grade":
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

        elif path == "/api/journal/invalidate":
            signal_id = body.get("signal_id", "").strip()
            notes = body.get("notes", "").strip()
            if not signal_id:
                self._send_json({"error": "signal_id is required"}, 400)
                return
            from tradegumi.journal import invalidate_signal
            ok = invalidate_signal(signal_id, notes)
            if ok:
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Signal not found"}, 404)

        elif path == "/api/journal/notes":
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

        elif path == "/api/journal/reset":
            signal_id = body.get("signal_id", "").strip()
            if not signal_id:
                self._send_json({"error": "signal_id is required"}, 400)
                return
            from tradegumi.journal import reset_signal_to_pending
            ok = reset_signal_to_pending(signal_id)
            if ok:
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Signal not found"}, 404)

        elif path == "/api/trades/manual":
            # POST /api/trades/manual — create new manual trade
            if not self._require_auth():
                return
            try:
                from tradegumi.manual_trades import TradePermissionError, create_trade
                symbol = body.get("symbol", "").strip().upper()
                direction = body.get("direction", "").lower()
                entry_price = float(body.get("entry_price", 0))
                exit_price = body.get("exit_price")
                if exit_price is not None:
                    exit_price = float(exit_price)
                entry_time = body.get("entry_time", manual_now_iso())
                exit_time = body.get("exit_time")
                notes = body.get("notes", "")
                tags = body.get("tags", [])
                volume = body.get("volume")
                if volume is not None:
                    volume = float(volume)
                fees = float(body.get("fees", 0) or 0)
                
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
                    notes=notes,
                    tags=tags,
                    volume=volume,
                    fees=fees,
                    bot_mode=config.TRADEGUMI_MODE,
                )
                self._send_json(trade, status=201)
            except TradePermissionError as e:
                self._send_json({"error": str(e)}, 403)
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        elif path.startswith("/api/trades/manual/"):
            # PUT/DELETE are handled by do_PUT/do_DELETE
            self._send_json({"error": "Method not allowed — use PUT or DELETE"}, 405)
            return

        elif path == "/api/action/rescan":
            # Trigger an immediate re-scan
            state = get_runtime_state()
            state["force_rescan"] = True
            set_runtime_state(state)
            log.info("API: Re-scan triggered via API")
            self._send_json({"status": "rescan_triggered"})

        elif path == "/api/action/restart":
            # Signal main loop to restart (set flag)
            state = get_runtime_state()
            state["restart_requested"] = True
            set_runtime_state(state)
            log.info("API: Restart requested via API")
            self._send_json({"status": "restart_requested"})

        elif path == "/api/purge":
            if not self._require_auth():
                return
            targets = body.get("targets")
            if targets is not None and not isinstance(targets, list):
                self._send_json({"error": "targets must be a list or omitted"}, 400)
                return
            from tradegumi.purge import purge_all
            try:
                results = purge_all(targets=targets)
                log.info("API: Purge executed — targets=%s, results=%s", targets, results)
                self._send_json({"ok": True, "results": results})
            except Exception as e:
                log.error("API: Purge failed: %s", e)
                self._send_json({"error": str(e)}, 500)

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

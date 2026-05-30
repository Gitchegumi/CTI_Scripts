"""TradeGumi main entry point.

Mode switch:
  alert_only — signal engine + Discord only, no execution
  demo       — signal engine + Oanda execution
  live       — signal engine + MatchTrader (Stage 2, blocked for now)

Main loop checks each symbol on the watchlist every 60s during trading hours.
Trailing SL runs as a co-routine in the same loop.
"""
import argparse
import atexit
import json
import logging as log
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from pytz import timezone

NY_TZ = timezone("America/New_York")
CT_TZ = timezone("America/Chicago")

# Setup paths so tradegumi is importable
sys.path.insert(0, str(Path(__file__).parent.parent))  # src/tradegumi → src/

from tradegumi import config
from tradegumi.api.oanda_client import OandaClient
from tradegumi.api.matchtrader_client import MatchTraderClient
from tradegumi.api.base_client import ExecutionClient, OrderRequest
from tradegumi.signal_engine import SignalEngine
from tradegumi.strategy_metrics import (
    CriterionResult,
    EvaluatedOpportunity,
    get_summary,
    record_opportunity,
    write_state_snapshot,
)
from tradegumi.risk import calc_lot_size, can_open_position
from tradegumi.session_rules import is_market_open, is_trading_open, is_swap_blackout
from tradegumi.alerts import post_signal, post_watchlist, record_trade_correlation
from tradegumi.trailing_sl import TrailingSLManager
from tradegumi.pre_session_scanner import run_scan, load_watchlist, load_watchlist_with_scores, format_watchlist_text, format_watchlist_diff
from tradegumi.api_server import start_api_server, set_runtime_state, get_runtime_state
from tradegumi.market_data import (
    MODE_STREAMING,
    ObservationDispatcher,
    PollingMarketDataProvider,
    STATUS_RUNNING,
    create_market_data_provider,
)
from tradegumi.price_observations import DEFAULT_PRICE_HISTORY
from tradegumi.signal_outcomes import evaluate_price_observation
from tradegumi.callback import (
    send_signal_callback, send_rescan_callback, send_mode_change_callback,
    send_trade_callback, send_status_callback, send_closed_market_callback,
)


@dataclass
class LoopPerfStats:
    """Lightweight rolling performance counters for the main loop."""

    interval_seconds: float
    started_at: float = field(default_factory=time.monotonic)
    loop_count: int = 0
    price_fetch_total: float = 0.0
    price_fetch_count: int = 0
    journal_eval_total: float = 0.0
    journal_eval_count: int = 0
    signal_pass_total: float = 0.0
    signal_pass_count: int = 0
    unresolved_evaluated: int = 0
    symbols_priced: int = 0
    symbols_signal_checked: int = 0
    slowest_symbol: Optional[str] = None
    slowest_symbol_seconds: float = 0.0

    def add(self, name: str, seconds: float, count: int = 1) -> None:
        if name == "price_fetch":
            self.price_fetch_total += seconds
            self.price_fetch_count += count
        elif name == "journal_eval":
            self.journal_eval_total += seconds
            self.journal_eval_count += count
        elif name == "signal_pass":
            self.signal_pass_total += seconds
            self.signal_pass_count += count

    def note_slowest_symbol(self, symbol: str, seconds: float) -> None:
        if seconds > self.slowest_symbol_seconds:
            self.slowest_symbol = symbol
            self.slowest_symbol_seconds = seconds

    def due(self, now: float) -> bool:
        return now - self.started_at >= self.interval_seconds

    def reset(self, now: float) -> None:
        interval = self.interval_seconds
        self.__dict__.update(LoopPerfStats(interval).__dict__)
        self.started_at = now

    def log_summary(self) -> None:
        def avg(total: float, count: int) -> float:
            return (total / count) if count else 0.0

        log.info(
            "Perf summary: loops=%s avg_price_fetch=%.3fs avg_journal_eval=%.4fs "
            "avg_signal_pass=%.3fs slowest_symbol=%s(%.3fs) unresolved_eval=%s "
            "priced=%s signal_checked=%s",
            self.loop_count,
            avg(self.price_fetch_total, self.price_fetch_count),
            avg(self.journal_eval_total, self.journal_eval_count),
            avg(self.signal_pass_total, self.signal_pass_count),
            self.slowest_symbol or "-",
            self.slowest_symbol_seconds,
            self.unresolved_evaluated,
            self.symbols_priced,
            self.symbols_signal_checked,
        )


@dataclass
class WatchlistCache:
    data: dict = field(default_factory=dict)
    scan_symbols: list[str] = field(default_factory=list)
    loaded_at: float = 0.0

    def refresh(self, available: set[str], perf: Optional[LoopPerfStats] = None) -> None:
        started = time.perf_counter()
        self.data = load_watchlist_with_scores()
        if perf:
            log.debug("Perf watchlist loading %.4fs", time.perf_counter() - started)
        started = time.perf_counter()
        self.scan_symbols = [
            s for s in self.data
            if s in available and s not in config.UNAVAILABLE_INSTRUMENTS
        ]
        if perf:
            log.debug("Perf scan_symbols construction %.4fs symbols=%s", time.perf_counter() - started, len(self.scan_symbols))
        self.loaded_at = time.time()

    def maybe_refresh(self, available: set[str], fallback_seconds: float, perf: Optional[LoopPerfStats] = None) -> None:
        if not self.data or time.time() - self.loaded_at >= fallback_seconds:
            self.refresh(available, perf)


def _loop_state_payload(mode: str, loop_state: list[dict]) -> dict:
    return {
        "timestamp": datetime.now(NY_TZ).isoformat(),
        "mode": mode,
        "provider": "Oanda" if mode != "live" else "MatchTrader",
        "symbols": loop_state,
    }


def _latest_prices(symbols: list[str]) -> dict[str, dict]:
    """Return latest shared observation prices keyed by symbol."""
    prices: dict[str, dict] = {}
    for symbol, observation in DEFAULT_PRICE_HISTORY.latest_many(symbols).items():
        bid = observation.bid
        ask = observation.ask
        spread = round(ask - bid, 6) if bid is not None and ask is not None else None
        prices[symbol] = {"bid": bid, "ask": ask, "spread": spread}
    return prices


def _should_poll_market_data(market_data_provider) -> bool:
    """Return True when the main loop should use REST polling.

    Decision is based purely on provider runtime state:
    - Polling provider  → always poll.
    - Streaming provider → poll if status != running or fallback is active.
    """
    if getattr(market_data_provider, "mode", None) != MODE_STREAMING:
        return True
    health = market_data_provider.snapshot_health()
    if health.get("status") != STATUS_RUNNING:
        return True
    if getattr(market_data_provider, "fallback_active", False):
        return True
    return False

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO"):
    log.basicConfig(
        level=getattr(log, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── Mode Guard ────────────────────────────────────────────────────────────────

def confirm_mode(mode: str) -> str:
    """Confirm the active mode at startup. Reads env var, no input() calls."""
    env_mode = config.TRADEGUMI_MODE
    if mode not in ("alert_only", "demo", "live"):
        raise ValueError(f"Invalid mode: {mode}")
    if mode != env_mode:
        log.warning("Mode mismatch: CLI=%s env=TRADEGUMI_MODE=%s — using CLI=%s",
                    mode, env_mode, mode)
    return mode


# ── Client factory ────────────────────────────────────────────────────────────

def make_client(mode: str) -> ExecutionClient:
    """Instantiate the correct ExecutionClient for the mode."""
    if mode == "live":
        return MatchTraderClient()   # will raise NotImplementedError until Stage 2
    return OandaClient()


# ── Instrument availability ───────────────────────────────────────────────────

def check_available_instruments(client: ExecutionClient) -> set[str]:
    """Query Oanda for tradeable instruments and mark unavailable ones.

    Returns set of CTI symbols that are available on this account.
    """
    if not isinstance(client, OandaClient):
        return set(config.EXECUTION_SYMBOLS)

    try:
        data = client._request("GET", f"/v3/accounts/{client.account_id}/instruments")
        oanda_instruments = {i["name"] for i in data.get("instruments", [])}
    except Exception as e:
        log.warning("Failed to fetch available instruments: %s — assuming all available", e)
        return set(config.EXECUTION_SYMBOLS)

    available = set()
    unavailable = []
    for cti_sym in config.EXECUTION_SYMBOLS:
        oanda_sym = config.to_oanda_symbol(cti_sym)
        if oanda_sym in oanda_instruments:
            available.add(cti_sym)
        else:
            unavailable.append(f"{cti_sym} ({oanda_sym})")

    if unavailable:
        log.info("Unavailable instruments (skipping): %s", ", ".join(unavailable))
        config.UNAVAILABLE_INSTRUMENTS = set(config.EXECUTION_SYMBOLS) - available

    return available


# ── Symbol scanning ────────────────────────────────────────────────────────────

def scan_and_alert(client: ExecutionClient, available: set[str] | None = None) -> dict | None:
    """Run the pre-session Layer 1 scanner, post full watchlist to Discord, return result."""
    from tradegumi.session_rules import is_trading_day
    now_ny = datetime.now(NY_TZ)

    if not is_trading_day("EURUSD", when=now_ny):
        day_name = now_ny.strftime("%A")
        log.info("Market closed (%s) — sending weekend message", day_name)
        post_watchlist(
            f"🌅 **Morning Watchlist**\n"
            f"It's {day_name} — markets are closed.\n"
            f"All quiet here. Enjoy the time off! 🌴",
        )
        return None

    log.info("Running pre-session Layer 1 scan...")
    try:
        result = run_scan(client, available=available)
        text   = format_watchlist_text(result)
        post_watchlist(text, scan_result=result)
        log.info("Pre-session scan complete: Tier1=%s Tier2=%s",
                 result["tier1"], result["tier2"])
        return result
    except Exception as e:
        log.error("Pre-session scan failed: %s", e)
        return None


# ── Per-symbol signal check ────────────────────────────────────────────────────

def check_and_execute(
    engine: SignalEngine,
    client: ExecutionClient,
    symbol: str,
    mode: str,
    trailing_manager: TrailingSLManager,
) -> tuple[str, Optional[str], float, float, float]:
    """Run signal engine for one symbol; execute if allowed.

    Returns (tag, trend, lr_1h, lr_15, lr_5) where tag is a summary like
    'flat', 'U(no_sig)', 'U(conf=0.7)', 'blocked', 'err', 'closed'.
    """
    def persist(opportunity: EvaluatedOpportunity) -> None:
        try:
            record_opportunity(opportunity)
            end = datetime.now(CT_TZ)
            start = end.replace(hour=0, minute=0, second=0, microsecond=0)
            write_state_snapshot(get_summary(start.isoformat(), end.isoformat()))
        except Exception as exc:
            log.warning("%s: failed to persist strategy diagnostic: %s", symbol, exc)

    if not is_trading_open(symbol):
        log.debug("%s: outside trading hours", symbol)
        now = datetime.now(CT_TZ).isoformat()
        persist(EvaluatedOpportunity(
            id=f"{symbol}:{now}",
            evaluated_at=now,
            symbol=symbol,
            mode=mode,
            final_decision="skipped",
            decision_reason="market_closed",
            data_quality_notes=["market closed"],
            threshold_version="session",
        ))
        return "closed", None, 0.0, 0.0, 0.0

    if is_swap_blackout(symbol):
        log.debug("%s: swap rollover blackout — skipping signal check", symbol)
        now = datetime.now(CT_TZ).isoformat()
        persist(EvaluatedOpportunity(
            id=f"{symbol}:{now}",
            evaluated_at=now,
            symbol=symbol,
            mode=mode,
            final_decision="skipped",
            decision_reason="rollover",
            data_quality_notes=["swap rollover blackout"],
            threshold_version="session",
        ))
        return "rollover", None, 0.0, 0.0, 0.0

    try:
        signal_obj, trend, lr_1h, lr_15, lr_5, diagnostic = engine.check_symbol(symbol)
    except Exception as e:
        log.error("%s: signal engine error: %s", symbol, e)
        now = datetime.now(CT_TZ).isoformat()
        persist(EvaluatedOpportunity(
            id=f"{symbol}:{now}",
            evaluated_at=now,
            symbol=symbol,
            mode=mode,
            final_decision="indeterminate",
            decision_reason="engine_error",
            data_complete=False,
            data_quality_notes=[str(e)],
            threshold_version="unknown",
        ))
        return "err", None, 0.0, 0.0, 0.0

    if signal_obj is None:
        persist(diagnostic.to_opportunity(mode))
        # No signal — trend might be flat or no clear direction
        if trend is None:
            return "flat", trend, lr_1h, lr_15, lr_5
        return f"{trend[0]}(no_sig)", trend, lr_1h, lr_15, lr_5

    # ── Lot / Unit sizing (always calculate for alerts, even if blocked) ──────
    try:
        balance = client.get_account_balance()
    except Exception as e:
        log.error("%s: failed to get balance: %s", symbol, e)
        balance = 0.0

    if balance > 0:
        try:
            if isinstance(client, OandaClient) and mode in ("alert_only", "demo"):
                # Oanda: use units (not lots). 500 units = 0.005 lots
                from tradegumi.risk import calc_position_units
                signal_obj.lot_size = calc_position_units(
                    account_balance=balance,
                    entry_price=signal_obj.entry_price,
                    stop_loss_price=signal_obj.stop_loss,
                    symbol=symbol,
                )
            else:
                # MatchTrader (live) or other: use standard lots
                signal_obj.lot_size = calc_lot_size(
                    account_balance=balance,
                    entry_price=signal_obj.entry_price,
                    stop_loss_price=signal_obj.stop_loss,
                    symbol=symbol,
                )
        except Exception as e:
            log.error("%s: lot sizing failed: %s", symbol, e)

    # ── Risk checks ──────────────────────────────────────────────────────────
    can_open, reason = can_open_position(client)
    if not can_open:
        signal_obj.blocked_reason = reason
        opportunity = diagnostic.to_opportunity(mode)
        opportunity.final_decision = "rejected"
        opportunity.decision_reason = "risk_blocked"
        opportunity.criteria.append(CriterionResult(
            criterion_name="risk",
            layer="risk",
            measured_value=reason,
            threshold_value="risk checks pass",
            threshold_operator="boolean",
            passed=False,
            required=True,
            blocked_signal=True,
        ))
        persist(opportunity)
        log.warning("%s: risk-blocked actionable candidate: %s", symbol, reason)
        post_signal(signal_obj)
        send_signal_callback({
            "symbol": signal_obj.symbol,
            "direction": signal_obj.direction,
            "confidence": signal_obj.confidence,
            "strategy": signal_obj.strategy,
            "mode": config.TRADEGUMI_MODE,
            "blocked": reason,
        })
        return f"{signal_obj.direction[0]}(blocked)", trend, lr_1h, lr_15, lr_5

    # Post signal to Discord (alert_only and demo both alert)
    persist(diagnostic.to_opportunity(mode))
    post_signal(signal_obj)
    send_signal_callback({
        "symbol": signal_obj.symbol,
        "direction": signal_obj.direction,
        "confidence": signal_obj.confidence,
        "strategy": signal_obj.strategy,
        "lr_1h": lr_1h,
        "lr_15": lr_15,
        "lr_5": lr_5,
        "trend": trend,
        "mode": config.TRADEGUMI_MODE,
        "blocked": getattr(signal_obj, 'blocked_reason', None),
    })
    tag = f"{signal_obj.direction[0]}(conf={signal_obj.confidence:.2f})"

    # Execute only in demo/live
    if mode in ("demo", "live"):
        order = OrderRequest(
            symbol=symbol,
            side=signal_obj.direction,
            volume=signal_obj.lot_size,
            stop_loss=signal_obj.stop_loss,
            take_profit=signal_obj.take_profit,
        )
        try:
            pos_id = client.place_order(order)
            log.info("%s: order placed id=%s lots=%.2f",
                     symbol, pos_id, signal_obj.lot_size)
            record_trade_correlation(
                trade_id=pos_id,
                symbol=symbol,
                direction=signal_obj.direction,
                trade_time=datetime.now(NY_TZ),
            )
            # Seed trailing SL manager with the new position
            pos = client.get_position(pos_id)
            trailing_manager.init_position(pos)
        except Exception as e:
            log.error("%s: order failed: %s", symbol, e)

    return tag, trend, lr_1h, lr_15, lr_5


# ── Main loop ─────────────────────────────────────────────────────────────────

def run(mode: str):
    """Main trading loop."""
    log.info("TradeGumi starting in %s mode", mode)
    config.validate_config()

    client = make_client(mode)

    # Check which instruments are actually available on this Oanda account
    available = check_available_instruments(client)

    engine = SignalEngine(client, watchlist=load_watchlist())
    trailing_manager = TrailingSLManager(client)

    log.info("Connected to Oanda — account=%s", config.OANDA_ACCOUNT_ID)

    # Start API server for dashboard
    api_server = start_api_server()
    set_runtime_state({"running": True, "loop_count": 0, "client": client})

    # Start Discord bot (DM alerts + grade buttons); falls back to webhook if unconfigured
    from tradegumi.discord_bot import start_bot_thread, wait_until_ready
    start_bot_thread()
    wait_until_ready(timeout=20.0)  # ensure bot is ready before first scan DM

    last_scan_result = scan_and_alert(client, available=available)

    # Pre-session scan schedule: 06:30 CT (America/Chicago) every trading day
    SCAN_HOUR_CT = 2
    SCAN_MINUTE_CT = 0
    last_scan_date = None
    last_closed_msg_date = None  # Track when we last sent the closed-market message

    RESCAN_INTERVAL = 30 * 60  # 30 minutes in seconds
    last_rescan_epoch = 0.0

    price_poll_seconds = max(0.1, float(config.TRADEGUMI_PRICE_POLL_SECONDS))
    signal_engine_seconds = max(0.1, float(config.TRADEGUMI_SIGNAL_ENGINE_SECONDS))
    loop_state_write_seconds = max(0.1, float(config.TRADEGUMI_LOOP_STATE_WRITE_SECONDS))
    watchlist_reload_seconds = max(1.0, float(config.TRADEGUMI_WATCHLIST_RELOAD_SECONDS))
    perf_log_seconds = max(1.0, float(config.TRADEGUMI_PERF_LOG_SECONDS))
    perf_stats = LoopPerfStats(perf_log_seconds)
    perf_enabled = bool(config.TRADEGUMI_PERF_ENABLED)
    watchlist_cache = WatchlistCache()
    watchlist_cache.refresh(available, perf_stats if perf_enabled else None)
    def timed_evaluate_price_observation(observation):
        """Evaluate journal outcomes while preserving loop performance counters."""
        started = time.perf_counter()
        summary = evaluate_price_observation(observation)
        elapsed = time.perf_counter() - started
        perf_stats.add("journal_eval", elapsed)
        perf_stats.unresolved_evaluated += summary.evaluated_count
        log.debug(
            "Perf evaluate_price_observation %.4fs symbol=%s evaluated=%s updated=%s",
            elapsed,
            observation.symbol,
            summary.evaluated_count,
            len(summary.updated),
        )
        return summary

    dispatcher = ObservationDispatcher(evaluator=timed_evaluate_price_observation)
    market_data_provider = create_market_data_provider(client, dispatcher)
    polling_provider = (
        market_data_provider
        if isinstance(market_data_provider, PollingMarketDataProvider)
        else PollingMarketDataProvider(client, dispatcher, configured_mode=config.TRADEGUMI_MARKET_DATA_MODE)
    )
    market_data_provider.start(watchlist_cache.scan_symbols)
    atexit.register(market_data_provider.stop)

    log.info("Entering main loop — signal engine every 5s, price ticker every 1s")
    log.info(
        "Active intervals: price_poll=%.1fs signal_engine=%.1fs loop_state_write=%.1fs "
        "watchlist_reload=%.1fs perf_log=%.1fs perf_enabled=%s",
        price_poll_seconds,
        signal_engine_seconds,
        loop_state_write_seconds,
        watchlist_reload_seconds,
        perf_log_seconds,
        perf_enabled,
    )
    log.info(
        "Market data: mode=%s provider=%s reconnect=%.1fs heartbeat_timeout=%.1fs "
        "backoff_max=%.1fs max_reconnect_attempts=%s",
        config.TRADEGUMI_MARKET_DATA_MODE,
        getattr(market_data_provider, "name", "unknown"),
        config.TRADEGUMI_STREAM_RECONNECT_SECONDS,
        config.TRADEGUMI_STREAM_HEARTBEAT_TIMEOUT_SECONDS,
        config.TRADEGUMI_STREAM_BACKOFF_MAX_SECONDS,
        config.TRADEGUMI_STREAM_MAX_RECONNECT_ATTEMPTS,
    )
    log.info("Watchlist re-scan every 30 minutes during market hours")
    log.info("Scheduled full re-scan at 02:00 ET (03:00 CT)")

    # Track last signal engine run for 5s cadence
    last_signal_run = 0.0
    last_price_poll = 0.0
    last_loop_state_write = 0.0
    last_loop_state_body = ""
    # Cache for price data and loop state between signal-engine passes.
    cached_loop_state: list[dict] = []

    while True:
        now_ct = datetime.now(CT_TZ)
        now_ny = datetime.now(NY_TZ)
        now_epoch = time.time()
        log.debug("Loop iteration at %s", now_ct.isoformat())

        # ── Scheduled watchlist re-scan (every 30 min during market hours) ──
        today_str = now_ct.strftime("%Y-%m-%d")
        is_full_rescan = (now_ct.hour == SCAN_HOUR_CT and now_ct.minute == SCAN_MINUTE_CT and today_str != last_scan_date)
        is_periodic_rescan = (now_epoch - last_rescan_epoch >= RESCAN_INTERVAL)
        any_market_open = any(is_market_open(s) for s in available - config.UNAVAILABLE_INSTRUMENTS)
        # Check for API-triggered rescan
        rt_state = get_runtime_state()
        is_api_rescan = rt_state.get("force_rescan", False)
        if is_api_rescan:
            set_runtime_state({**rt_state, "force_rescan": False})

        if (is_full_rescan or is_api_rescan or (is_periodic_rescan and any_market_open)):
            try:
                if is_full_rescan:
                    # 2am scheduled scan — post full morning watchlist to Discord
                    log.info("Full re-scan triggered at %s", now_ny.strftime("%H:%M ET"))
                    available = check_available_instruments(client)
                    last_scan_result = scan_and_alert(client, available=available)
                    last_scan_date = today_str
                else:
                    # Periodic (30 min) or API-triggered — update tier list silently,
                    # post only what changed since the last scan
                    if is_api_rescan:
                        log.info("API re-scan triggered at %s", now_ny.strftime("%H:%M ET"))
                        available = check_available_instruments(client)
                    else:
                        log.info("Periodic re-scan (30 min) at %s", now_ny.strftime("%H:%M ET"))

                    new_result = run_scan(client, available=available)

                    if last_scan_result is not None:
                        diff = format_watchlist_diff(last_scan_result, new_result)
                        if diff:
                            post_watchlist(diff, title="📊 Watchlist Update — TradeGumi")

                    last_scan_result = new_result

                engine = SignalEngine(client, watchlist=load_watchlist())
                watchlist_cache.refresh(available, perf_stats if perf_enabled else None)
                market_data_provider.resubscribe(
                    watchlist_cache.scan_symbols,
                    reason="full_rescan" if is_full_rescan else ("api_rescan" if is_api_rescan else "periodic_rescan"),
                )
                polling_provider.resubscribe(watchlist_cache.scan_symbols, reason="rescan")
                last_rescan_epoch = now_epoch
                log.info("Re-scan complete — watchlist refreshed")
                send_rescan_callback({"trigger": "full" if is_full_rescan or is_api_rescan else "periodic"})
            except Exception as e:
                log.error("Re-scan failed: %s", e)

        # ── Price ticker (every 1s) ──────────────────────────────────────────
        perf_stats.loop_count += 1
        previous_scan_symbols = tuple(watchlist_cache.scan_symbols)
        watchlist_cache.maybe_refresh(available, watchlist_reload_seconds, perf_stats if perf_enabled else None)
        watchlist_data = watchlist_cache.data
        scan_symbols = watchlist_cache.scan_symbols
        if tuple(scan_symbols) != previous_scan_symbols:
            market_data_provider.resubscribe(scan_symbols, reason="watchlist_reload")
            polling_provider.resubscribe(scan_symbols, reason="watchlist_reload")

        prices = _latest_prices(scan_symbols)
        if now_epoch - last_price_poll >= price_poll_seconds:
            last_price_poll = now_epoch
            if _should_poll_market_data(market_data_provider):
                try:
                    started = time.perf_counter()
                    observations = polling_provider.poll_once(scan_symbols)
                    elapsed = time.perf_counter() - started
                    perf_stats.add("price_fetch", elapsed)
                    perf_stats.symbols_priced += len(observations)
                    log.debug("Perf market_data.poll_once %.4fs symbols=%s", elapsed, len(scan_symbols))
                except Exception as e:
                    log.debug("Price fetch failed: %s", e)
            prices = _latest_prices(scan_symbols)

        # ── Signal engine (every 5s) ─────────────────────────────────────────
        if now_epoch - last_signal_run >= signal_engine_seconds:
            last_signal_run = now_epoch
            signal_pass_started = time.perf_counter()

            # Run trailing SL
            try:
                started = time.perf_counter()
                trailing_manager.run_once()
                log.debug("Perf trailing_manager.run_once %.4fs", time.perf_counter() - started)
            except Exception as e:
                log.error("TrailingSL error: %s", e)

            # Check each symbol
            loop_summary = []
            loop_state = []
            for symbol in scan_symbols:
                started = time.perf_counter()
                tag, trend, lr_1h, lr_15, lr_5 = check_and_execute(engine, client, symbol, mode, trailing_manager)
                elapsed = time.perf_counter() - started
                perf_stats.symbols_signal_checked += 1
                perf_stats.note_slowest_symbol(symbol, elapsed)
                log.debug("Perf engine.check_symbol %.4fs symbol=%s", elapsed, symbol)
                score = watchlist_data[symbol]["score"]
                tier = watchlist_data[symbol]["tier"]
                loop_summary.append((symbol, tag, tier, score))
                state_entry = {
                    "symbol": symbol,
                    "state": tag,
                    "trend": tag if tag in ("closed", "rollover") else (trend or "flat"),
                    "lr_1h": round(lr_1h, 6) if lr_1h else 0.0,
                    "lr_15": round(lr_15, 6) if lr_15 else 0.0,
                    "lr_5": round(lr_5, 6) if lr_5 else 0.0,
                    "score": round(score, 3),
                    "tier": tier,
                }
                # Merge live price into state
                if symbol in prices:
                    state_entry["bid"] = prices[symbol]["bid"]
                    state_entry["ask"] = prices[symbol]["ask"]
                    state_entry["spread"] = prices[symbol]["spread"]
                loop_state.append(state_entry)

            # Sort by score descending — most relevant first
            loop_summary.sort(key=lambda x: x[3], reverse=True)
            log.info("Loop: %s", " | ".join(
                f"{s}={tag}" for s, tag, _, _ in loop_summary
            ))

            cached_loop_state = loop_state
            signal_elapsed = time.perf_counter() - signal_pass_started
            perf_stats.add("signal_pass", signal_elapsed)
            log.debug("Perf signal engine pass %.4fs symbols=%s", signal_elapsed, len(scan_symbols))
        else:
            # Between signal runs, just update prices in cached state
            loop_state = []
            for entry in cached_loop_state:
                updated = dict(entry)
                sym = updated["symbol"]
                if sym in prices:
                    updated["bid"] = prices[sym]["bid"]
                    updated["ask"] = prices[sym]["ask"]
                    updated["spread"] = prices[sym]["spread"]
                loop_state.append(updated)

        # ── Closed-market message (once per close period) ───────────────────────
        if loop_state and all(s.get("state") == "closed" for s in loop_state):
            close_key = now_ny.strftime("%Y-%m-%d")  # Once per calendar day
            if close_key != last_closed_msg_date:
                from tradegumi.session_rules import is_trading_day
                if not is_trading_day("EURUSD", when=now_ny):
                    # Weekend
                    day_name = now_ny.strftime("%A")
                    log.info("Market closed (weekend — %s) — sending closed message", day_name)
                    msg = (
                        f"🌅 **Morning Watchlist**\n"
                        f"It's {day_name} — markets are closed.\n"
                        f"All quiet here. Enjoy the time off! 🌴"
                    )
                    post_watchlist(msg)
                    send_closed_market_callback(day_name, msg)
                else:
                    # Weekday but after hours (Fri evening, etc.)
                    day_name = now_ny.strftime("%A")
                    log.info("Market closed (after hours — %s) — sending closed message", day_name)
                    msg = (
                        f"🌅 **Morning Watchlist**\n"
                        f"It's {day_name} evening — markets are closed for the night.\n"
                        f"See you at the next session open! 🌙"
                    )
                    post_watchlist(msg)
                    send_closed_market_callback(day_name, msg)
                last_closed_msg_date = close_key

        # ── Write loop state (every 1s) ──────────────────────────────────────
        try:
            started = time.perf_counter()
            payload = _loop_state_payload(mode, loop_state)
            market_health = market_data_provider.snapshot_health()
            set_runtime_state({
                **get_runtime_state(),
                "loop_count": perf_stats.loop_count,
                "loop_state": payload,
                "market_data": market_health,
            })
            log.debug("Perf dashboard/API state update work %.4fs", time.perf_counter() - started)

            payload_for_change = {k: v for k, v in payload.items() if k != "timestamp"}
            body_for_change = json.dumps(payload_for_change, sort_keys=True, separators=(",", ":"), default=str)
            should_write_state = (
                now_epoch - last_loop_state_write >= loop_state_write_seconds
                or body_for_change != last_loop_state_body
            )
            if should_write_state:
                started = time.perf_counter()
                state_file = Path(__file__).parent / "data" / "loop_state.json"
                state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(state_file, "w") as f:
                    json.dump(payload, f, separators=(",", ":"), default=str)
                last_loop_state_write = now_epoch
                last_loop_state_body = body_for_change
                log.debug("Perf loop_state.json write %.4fs", time.perf_counter() - started)
        except Exception as e:
            log.warning("Failed to write loop_state.json: %s", e)

        if perf_enabled and perf_stats.due(time.monotonic()):
            perf_stats.log_summary()
            market_health = market_data_provider.snapshot_health()
            log.info(
                "Market data summary: mode=%s configured=%s provider=%s symbols=%s "
                "observations_per_minute=%s reconnects=%s fallback=%s heartbeat_age=%s",
                market_health.get("active_mode"),
                market_health.get("configured_mode"),
                market_health.get("provider"),
                market_health.get("active_symbol_count"),
                market_health.get("observations_per_minute"),
                market_health.get("reconnect_count"),
                market_health.get("fallback_active"),
                market_health.get("last_heartbeat_age_seconds"),
            )
            perf_stats.reset(time.monotonic())

        # Sleep until next second boundary
        now_ct = datetime.now(CT_TZ)
        sleep_sec = price_poll_seconds - (now_ct.microsecond / 1_000_000)
        time.sleep(max(0.1, sleep_sec))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TradeGumi — CTI Signal Engine")
    parser.add_argument(
        "--mode", "-m",
        choices=["alert_only", "demo", "live"],
        default=config.TRADEGUMI_MODE,
        help="Execution mode (default: from TRADEGUMI_MODE env var)",
    )
    parser.add_argument(
        "--scan-only", "-s",
        action="store_true",
        help="Run pre-session scan only, then exit",
    )
    parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    mode = confirm_mode(args.mode)
    client = make_client(mode)

    if args.scan_only:
        available = check_available_instruments(client)
        scan_and_alert(client, available=available)
        return

    # Graceful shutdown on SIGINT/SIGTERM
    def shutdown(signum, frame):
        log.warning("Shutdown signal received — exiting main loop")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    run(mode)


if __name__ == "__main__":
    main()

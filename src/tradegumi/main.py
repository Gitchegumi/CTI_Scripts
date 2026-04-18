"""TradeGumi main entry point.

Mode switch:
  alert_only — signal engine + Discord only, no execution
  demo       — signal engine + Oanda execution
  live       — signal engine + MatchTrader (Stage 2, blocked for now)

Main loop checks each symbol on the watchlist every 60s during trading hours.
Trailing SL runs as a co-routine in the same loop.
"""
import argparse
import json
import logging as log
import signal
import sys
import time
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
from tradegumi.risk import calc_lot_size, can_open_position
from tradegumi.session_rules import is_market_open
from tradegumi.alerts import post_signal, post_watchlist
from tradegumi.trailing_sl import TrailingSLManager
from tradegumi.pre_session_scanner import run_scan, load_watchlist, load_watchlist_with_scores, format_watchlist_text
from tradegumi.api_server import start_api_server, set_runtime_state, get_runtime_state
from tradegumi.callback import (
    send_signal_callback, send_rescan_callback, send_mode_change_callback,
    send_trade_callback, send_status_callback, send_closed_market_callback,
)

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

def scan_and_alert(client: ExecutionClient, available: set[str] | None = None) -> None:
    """Run the pre-session Layer 1 scanner and post watchlist to Discord."""
    from tradegumi.session_rules import is_trading_day
    now_ny = datetime.now(NY_TZ)

    # Weekend / holiday check
    if not is_trading_day("EURUSD", when=now_ny):
        day_name = now_ny.strftime("%A")
        log.info("Market closed (%s) — sending weekend message", day_name)
        post_watchlist(
            f"🌅 **Morning Watchlist**\n"
            f"It's {day_name} — markets are closed.\n"
            f"All quiet here. Enjoy the time off! 🌴",
        )
        return

    log.info("Running pre-session Layer 1 scan...")
    try:
        result = run_scan(client, available=available)
        text   = format_watchlist_text(result)
        post_watchlist(text, scan_result=result)
        log.info("Pre-session scan complete: Tier1=%s Tier2=%s",
                 result["tier1"], result["tier2"])
    except Exception as e:
        log.error("Pre-session scan failed: %s", e)


# ── Per-symbol signal check ────────────────────────────────────────────────────

def check_and_execute(
    engine: SignalEngine,
    client: ExecutionClient,
    symbol: str,
    mode: str,
    trailing_manager: TrailingSLManager,
) -> tuple[str, Optional[str], float, float]:
    """Run signal engine for one symbol; execute if allowed.

    Returns (tag, trend, lr_15, lr_5) where tag is a summary like
    'flat', 'U(no_sig)', 'U(conf=0.7)', 'blocked', 'err', 'closed'.
    """
    if not is_market_open(symbol):
        log.debug("%s: outside trading hours", symbol)
        return "closed", None, 0.0, 0.0

    try:
        signal_obj, trend, lr_15, lr_5 = engine.check_symbol(symbol)
    except Exception as e:
        log.error("%s: signal engine error: %s", symbol, e)
        return "err", None, 0.0, 0.0

    if signal_obj is None:
        # No signal — trend might be flat or no clear direction
        if trend is None:
            return "flat", trend, lr_15, lr_5
        return f"{trend[0]}(no_sig)", trend, lr_15, lr_5

    # ── Lot sizing (always calculate for alerts, even if blocked) ──────
    try:
        balance = client.get_account_balance()
    except Exception as e:
        log.error("%s: failed to get balance: %s", symbol, e)
        balance = 0.0

    if balance > 0:
        try:
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
        post_signal(signal_obj)
        send_signal_callback({
            "symbol": signal_obj.symbol,
            "direction": signal_obj.direction,
            "confidence": signal_obj.confidence,
            "strategy": signal_obj.strategy,
            "mode": config.TRADEGUMI_MODE,
            "blocked": reason,
        })
        return f"{signal_obj.direction[0]}(blocked)", trend, lr_15, lr_5

    # Post signal to Discord (alert_only and demo both alert)
    post_signal(signal_obj)
    send_signal_callback({
        "symbol": signal_obj.symbol,
        "direction": signal_obj.direction,
        "confidence": signal_obj.confidence,
        "strategy": signal_obj.strategy,
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
            # Seed trailing SL manager with the new position
            pos = client.get_position(pos_id)
            trailing_manager.init_position(pos)
        except Exception as e:
            log.error("%s: order failed: %s", symbol, e)

    return tag, trend, lr_15, lr_5


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

    scan_and_alert(client, available=available)

    # Pre-session scan schedule: 06:30 CT (America/Chicago) every trading day
    SCAN_HOUR_CT = 2
    SCAN_MINUTE_CT = 0
    last_scan_date = None
    last_closed_msg_date = None  # Track when we last sent the closed-market message

    RESCAN_INTERVAL = 30 * 60  # 30 minutes in seconds
    last_rescan_epoch = 0.0

    log.info("Entering main loop — signal engine every 5s, price ticker every 1s")
    log.info("Watchlist re-scan every 30 minutes during market hours")
    log.info("Scheduled full re-scan at 02:00 ET (03:00 CT)")

    # Track last signal engine run for 5s cadence
    last_signal_run = 0.0
    # Cache for price data and loop state (written every 1s by price ticker)
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
                if is_full_rescan or is_api_rescan:
                    log.info("Full re-scan triggered at %s", now_ny.strftime("%H:%M ET"))
                    available = check_available_instruments(client)
                else:
                    log.info("Periodic re-scan (30 min) at %s", now_ny.strftime("%H:%M ET"))

                from tradegumi.pre_session_scanner import run_scan
                run_scan(client, available=available)  # saves watchlist.json
                engine = SignalEngine(client, watchlist=load_watchlist())
                last_rescan_epoch = now_epoch

                if is_full_rescan:
                    last_scan_date = today_str
                log.info("Re-scan complete — watchlist refreshed")
                send_rescan_callback({"trigger": "full" if is_full_rescan or is_api_rescan else "periodic"})
            except Exception as e:
                log.error("Re-scan failed: %s", e)

        # ── Price ticker (every 1s) ──────────────────────────────────────────
        watchlist_data = load_watchlist_with_scores()
        scan_symbols = [s for s in watchlist_data if s in available and s not in config.UNAVAILABLE_INSTRUMENTS]

        prices = {}
        try:
            ticks = client.get_pricing(scan_symbols)
            prices = {t.symbol: {"bid": t.bid, "ask": t.ask, "spread": t.spread} for t in ticks}
        except Exception as e:
            log.debug("Price fetch failed: %s", e)

        # ── Signal engine (every 5s) ─────────────────────────────────────────
        if now_epoch - last_signal_run >= 5.0:
            last_signal_run = now_epoch

            # Run trailing SL
            try:
                trailing_manager.run_once()
            except Exception as e:
                log.error("TrailingSL error: %s", e)

            # Check each symbol
            loop_summary = []
            loop_state = []
            for symbol in scan_symbols:
                tag, trend, lr_15, lr_5 = check_and_execute(engine, client, symbol, mode, trailing_manager)
                score = watchlist_data[symbol]["score"]
                tier = watchlist_data[symbol]["tier"]
                loop_summary.append((symbol, tag, tier, score))
                state_entry = {
                    "symbol": symbol,
                    "state": tag,
                    "trend": (trend or "flat") if tag != "closed" else "closed",
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
            state_file = Path(__file__).parent / "data" / "loop_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "timestamp": datetime.now(NY_TZ).isoformat(),
                "mode": mode,
                "provider": "Oanda" if mode != "live" else "MatchTrader",
                "symbols": loop_state,
            }
            with open(state_file, "w") as f:
                json.dump(payload, f, indent=2, default=str)
        except Exception as e:
            log.warning("Failed to write loop_state.json: %s", e)

        # Sleep until next second boundary
        now_ct = datetime.now(CT_TZ)
        sleep_sec = 1.0 - (now_ct.microsecond / 1_000_000)
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
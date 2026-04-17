"""TradeGumi main entry point.

Mode switch:
  alert_only — signal engine + Discord only, no execution
  demo       — signal engine + Oanda execution
  live       — signal engine + MatchTrader (Stage 2, blocked for now)

Main loop checks each symbol on the watchlist every 60s during trading hours.
Trailing SL runs as a co-routine in the same loop.
"""
import argparse
import logging as log
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

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
from tradegumi.pre_session_scanner import run_scan, load_watchlist, format_watchlist_text

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
    log.info("Running pre-session Layer 1 scan...")
    try:
        result = run_scan(client, available=available)
        text   = format_watchlist_text(result)
        # Pass JSON file path so Discord attaches it as a file
        from tradegumi.pre_session_scanner import WATCHLIST_FILE
        post_watchlist(text, json_path=str(WATCHLIST_FILE))
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
) -> str:
    """Run signal engine for one symbol; execute if allowed.

    Returns a summary tag like 'flat', 'U(no_sig)', 'U(conf=0.7)', 'blocked', 'err'.
    """
    if not is_market_open(symbol):
        log.debug("%s: outside trading hours", symbol)
        return "closed"

    try:
        signal_obj = engine.check_symbol(symbol)
    except Exception as e:
        log.error("%s: signal engine error: %s", symbol, e)
        return "err"

    if signal_obj is None:
        log.debug("%s: no signal", symbol)
        return "flat"

    # ── Risk checks ──────────────────────────────────────────────────────────
    can_open, reason = can_open_position(client)
    if not can_open:
        signal_obj.blocked_reason = reason
        post_signal(signal_obj)
        return f"{signal_obj.direction[0]}(blocked)"

    # Fetch balance for lot sizing
    try:
        balance = client.get_account_balance()
    except Exception as e:
        log.error("%s: failed to get balance: %s", symbol, e)
        return f"{signal_obj.direction[0]}(bal_err)"

    try:
        signal_obj.lot_size = calc_lot_size(
            account_balance=balance,
            entry_price=signal_obj.entry_price,
            stop_loss_price=signal_obj.stop_loss,
            symbol=symbol,
        )
    except Exception as e:
        log.error("%s: lot sizing failed: %s", symbol, e)
        return f"{signal_obj.direction[0]}(lots_err)"

    # Post signal to Discord (alert_only and demo both alert)
    post_signal(signal_obj)
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

    return tag


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

    scan_and_alert(client, available=available)

    # Pre-session scan schedule: 06:30 CT (America/Chicago) every trading day
    SCAN_HOUR_CT = 6
    SCAN_MINUTE_CT = 30
    last_scan_date = None

    log.info("Entering main loop — checking %d available symbols every 60s", len(available))
    log.info("Scheduled daily re-scan at %02d:%02d CT", SCAN_HOUR_CT, SCAN_MINUTE_CT)
    while True:
        now_ct = datetime.now(CT_TZ)
        now_ny = datetime.now(NY_TZ)
        log.debug("Loop iteration at %s", now_ct.isoformat())

        # ── Scheduled daily re-scan ──────────────────────────────────────────
        today_str = now_ct.strftime("%Y-%m-%d")
        if now_ct.hour == SCAN_HOUR_CT and now_ct.minute == SCAN_MINUTE_CT and today_str != last_scan_date:
            log.info("Scheduled re-scan triggered at %s CT", now_ct.strftime("%H:%M"))
            try:
                # Re-check availability in case account instruments changed
                available = check_available_instruments(client)
                scan_and_alert(client, available=available)
                # Refresh engine watchlist from newly saved JSON
                engine = SignalEngine(client, watchlist=load_watchlist())
                last_scan_date = today_str
                log.info("Re-scan complete — watchlist refreshed")
            except Exception as e:
                log.error("Scheduled re-scan failed: %s", e)

        # Run trailing SL on each iteration
        try:
            trailing_manager.run_once()
        except Exception as e:
            log.error("TrailingSL error: %s", e)

        # Check each available symbol in the watchlist
        watchlist = load_watchlist()
        loop_summary = []
        for symbol in available:
            if symbol in config.UNAVAILABLE_INSTRUMENTS:
                continue
            tag = check_and_execute(engine, client, symbol, mode, trailing_manager)
            loop_summary.append(f"{symbol}={tag}")

        # Per-loop summary at INFO level
        log.info("Loop: %s", " | ".join(loop_summary))

        time.sleep(60)


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
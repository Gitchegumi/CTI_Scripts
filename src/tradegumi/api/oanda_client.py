"""Oanda v20 REST client implementation of ExecutionClient."""
import logging as log
import time

import requests
from typing import Optional
from decimal import Decimal

from tradegumi.api.base_client import (
    ExecutionClient, Candle, Position, OrderRequest, PriceTick, ProviderRequestError, TradeHistory
)
from tradegumi import config

log = log.getLogger(__name__)


class OandaClient(ExecutionClient):
    """Thin Oanda v20 REST wrapper.

    Handles instrument format conversion (EURUSD ↔ EUR_USD) internally.
    """

    REQUEST_TIMEOUT_SECONDS = 10
    MAX_REQUEST_ATTEMPTS = 3
    RETRY_BACKOFF_SECONDS = 0.25
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: Optional[str] = None,
        account_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or config.OANDA_API_KEY
        self.account_id = account_id or config.OANDA_ACCOUNT_ID
        self.base_url = (base_url or config.OANDA_BASE_URL).rstrip("/")
        self.stream_url = config.OANDA_STREAM_URL.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _to_oanda(self, symbol: str) -> str:
        """EURUSD → EUR_USD, US500 → USD_SPX500"""
        return config.to_oanda_symbol(symbol)

    def _from_oanda(self, oanda_sym: str) -> str:
        """EUR_USD → EURUSD, USD_SPX500 → US500"""
        return config.from_oanda_symbol(oanda_sym)

    def _url_for_path(self, path: str) -> str:
        """Build a normalized REST URL for an Oanda v20 path."""
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{normalized_path}"

    def _error_type_for_status(self, status_code: Optional[int], operation: str) -> str:
        """Return a stable diagnostic category for an Oanda request failure."""
        if status_code == 429:
            return "oanda_rate_limited"
        if status_code == 504:
            return "oanda_gateway_timeout"
        if operation == "candle_fetch":
            return "oanda_candle_fetch_failed"
        return "oanda_request_failed"

    def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str = "oanda_request",
        instrument: Optional[str] = None,
        granularity: Optional[str] = None,
        **kwargs,
    ):
        """Make an authenticated Oanda v20 request with timeout and retry context."""
        path = path if path.startswith("/") else f"/{path}"
        url = self._url_for_path(path)
        timeout = kwargs.pop("timeout", self.REQUEST_TIMEOUT_SECONDS)
        max_attempts = self.MAX_REQUEST_ATTEMPTS
        last_error: Optional[ProviderRequestError] = None

        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._session.request(method, url, timeout=timeout, **kwargs)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = ProviderRequestError(
                    f"Oanda {operation} failed: {exc.__class__.__name__}",
                    provider="oanda",
                    method=method,
                    path=path,
                    operation=operation,
                    instrument=instrument,
                    granularity=granularity,
                    attempts=attempt,
                    max_attempts=max_attempts,
                    retryable=True,
                    error_type=self._error_type_for_status(None, operation),
                )
            else:
                if 200 <= resp.status_code < 300:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise ProviderRequestError(
                            f"Oanda {operation} response was not valid JSON",
                            provider="oanda",
                            method=method,
                            path=path,
                            operation=operation,
                            status_code=resp.status_code,
                            instrument=instrument,
                            granularity=granularity,
                            attempts=attempt,
                            max_attempts=max_attempts,
                            retryable=False,
                            error_type="oanda_response_malformed",
                        ) from exc

                retryable = resp.status_code in self.RETRYABLE_STATUS_CODES
                error = ProviderRequestError(
                    f"Oanda {operation} failed with HTTP {resp.status_code}",
                    provider="oanda",
                    method=method,
                    path=path,
                    operation=operation,
                    status_code=resp.status_code,
                    instrument=instrument,
                    granularity=granularity,
                    attempts=attempt,
                    max_attempts=max_attempts,
                    retryable=retryable,
                    error_type=self._error_type_for_status(resp.status_code, operation),
                )
                if not retryable:
                    raise error
                last_error = error

            if attempt < max_attempts:
                log.warning(
                    "Oanda %s retryable failure: method=%s path=%s status=%s attempt=%s/%s instrument=%s granularity=%s",
                    operation,
                    method,
                    path,
                    last_error.status_code if last_error else None,
                    attempt,
                    max_attempts,
                    instrument,
                    granularity,
                )
                time.sleep(self.RETRY_BACKOFF_SECONDS * attempt)

        if last_error:
            raise last_error
        raise ProviderRequestError(
            f"Oanda {operation} failed before a request was completed",
            provider="oanda",
            method=method,
            path=path,
            operation=operation,
            instrument=instrument,
            granularity=granularity,
            attempts=max_attempts,
            max_attempts=max_attempts,
            retryable=True,
            error_type=self._error_type_for_status(None, operation),
        )

    # ── Market Data ──────────────────────────────────────────────────────────

    def get_candles(
        self,
        instrument: str,
        granularity: str = "M5",
        count: int = 100,
    ) -> list[Candle]:
        """Fetch candles from Oanda v20 REST.

        Args:
            instrument: Generic symbol "EURUSD"
            granularity: Oanda granularity "M5", "M15", "H1"
            count: Number of candles

        Returns:
            list[Candle] ordered oldest-first
        """
        oanda_inst = self._to_oanda(instrument)
        path = f"/v3/instruments/{oanda_inst}/candles"
        params = {"granularity": granularity, "count": count, "price": "M"}
        data = self._request(
            "GET",
            path,
            operation="candle_fetch",
            instrument=oanda_inst,
            granularity=granularity,
            params=params,
        )
        if not isinstance(data.get("candles"), list):
            raise ProviderRequestError(
                "Oanda candle response missing candles array",
                provider="oanda",
                method="GET",
                path=path,
                operation="candle_fetch",
                instrument=oanda_inst,
                granularity=granularity,
                attempts=1,
                max_attempts=self.MAX_REQUEST_ATTEMPTS,
                retryable=False,
                error_type="oanda_response_malformed",
            )
        candles = []
        for c in data.get("candles", []):
            mid = c.get("mid", {})
            if not all(key in mid for key in ("o", "h", "l", "c")):
                raise ProviderRequestError(
                    "Oanda candle response missing midpoint OHLC data",
                    provider="oanda",
                    method="GET",
                    path=path,
                    operation="candle_fetch",
                    instrument=oanda_inst,
                    granularity=granularity,
                    attempts=1,
                    max_attempts=self.MAX_REQUEST_ATTEMPTS,
                    retryable=False,
                    error_type="oanda_response_malformed",
                )
            candles.append(Candle(
                t=c["time"],
                o=float(mid["o"]),
                h=float(mid["h"]),
                l=float(mid["l"]),
                c=float(mid["c"]),
                s=c.get("volume"),
                complete=bool(c.get("complete", True)),
            ))
        return candles

    def get_pricing(self, instruments: list[str]) -> list[PriceTick]:
        """Fetch current bid/ask for multiple instruments in one API call.

        Uses Oanda's batch pricing endpoint.
        """
        oanda_syms = [self._to_oanda(s) for s in instruments]
        params = {"instruments": ",".join(oanda_syms)}
        data = self._request("GET", f"/v3/accounts/{self.account_id}/pricing", params=params)
        ticks = []
        for p in data.get("prices", []):
            sym = self._from_oanda(p["instrument"])
            bid = float(p["bids"][0]["price"]) if p.get("bids") else 0.0
            ask = float(p["asks"][0]["price"]) if p.get("asks") else 0.0
            ticks.append(PriceTick(
                symbol=sym,
                bid=bid,
                ask=ask,
                spread=round(ask - bid, 6),
                timestamp=p["time"],
            ))
        return ticks

    def get_account_balance(self) -> float:
        """Return account balance."""
        data = self._request("GET", f"/v3/accounts/{self.account_id}/summary")
        return float(data["account"]["balance"])

    def get_account_instruments(self) -> list[dict]:
        """Return instruments available to the configured Oanda account."""
        data = self._request("GET", f"/v3/accounts/{self.account_id}/instruments")
        return list(data.get("instruments", []))

    def get_open_positions(self) -> list[Position]:
        """Return list of open positions from Oanda with live pricing and SL/TP."""
        # Fetch positions
        data = self._request("GET", f"/v3/accounts/{self.account_id}/openPositions")
        # Fetch open trades for SL/TP details
        trades_data = self._request("GET", f"/v3/accounts/{self.account_id}/openTrades")
        # Build lookup: instrument -> {sl, tp}
        trade_details: dict[str, dict] = {}
        for t in trades_data.get("trades", []):
            inst = t.get("instrument", "")
            sl = None
            tp = None
            if t.get("stopLossOrder"):
                sl = float(t["stopLossOrder"].get("price", "0") or "0")
            if t.get("takeProfitOrder"):
                tp = float(t["takeProfitOrder"].get("price", "0") or "0")
            trade_details[inst] = {"sl": sl, "tp": tp}

        # Fetch live pricing for all instruments
        instruments = [p["instrument"] for p in data.get("positions", [])]
        pricing_map: dict[str, float] = {}
        if instruments:
            prices = self.get_pricing([self._from_oanda(i) for i in instruments])
            for tick in prices:
                pricing_map[self._to_oanda(tick.symbol)] = tick.bid

        positions = []
        for p in data.get("positions", []):
            inst = p["instrument"]
            long_units = float(p.get("long", {}).get("units", "0") or "0")
            short_units = float(p.get("short", {}).get("units", "0") or "0")
            side = "BUY" if long_units > 0 else "SELL"
            volume = abs(long_units) if long_units > 0 else abs(short_units)
            avg_price = float(p.get("long", {}).get("averagePrice", "0") or "0") if long_units > 0 else float(p.get("short", {}).get("averagePrice", "0") or "0")
            unrealized = float(p.get("unrealizedPL", "0") or "0")
            details = trade_details.get(inst, {})
            pos = Position(
                id=inst.replace("_", ""),
                symbol=self._from_oanda(inst),
                side=side,
                volume=volume,
                open_price=avg_price,
                current_price=pricing_map.get(inst, avg_price),
                stop_loss=details.get("sl"),
                take_profit=details.get("tp"),
                unrealized_pl=unrealized,
                net_profit=float(p.get("pl", "0") or "0"),
            )
            positions.append(pos)
        return positions

    def get_trade_history(self, count: int = 50) -> list[TradeHistory]:
        """Return recent closed trades from Oanda."""
        safe_count = max(1, min(int(count), 500))
        params = {"count": safe_count, "state": "CLOSED"}
        data = self._request("GET", f"/v3/accounts/{self.account_id}/trades", params=params)
        trades = []
        for t in data.get("trades", []):
            trade = TradeHistory(
                id=str(t.get("id", "")),
                symbol=self._from_oanda(t.get("instrument", "")),
                side="BUY" if float(t.get("initialUnits", "0") or "0") > 0 else "SELL",
                volume=abs(float(t.get("initialUnits", "0") or "0")),
                open_price=float(t.get("price", "0") or "0"),
                close_price=float(t.get("averageClosePrice", "0") or "0"),
                open_time=t.get("openTime", ""),
                close_time=t.get("closeTime", ""),
                realized_pl=float(t.get("realizedPL", "0") or "0"),
                financing=float(t.get("financing", "0") or "0"),
                pnl=float(t.get("realizedPL", "0") or "0") + float(t.get("financing", "0") or "0"),
            )
            trades.append(trade)
        return trades

    def get_position(self, position_id: str) -> Position:
        """Fetch a single position by ID."""
        oanda_inst = self._to_oanda(position_id)
        data = self._request("GET", f"/v3/accounts/{self.account_id}/positions/{oanda_inst}")
        p = data["position"]
        return Position(
            id=position_id,
            symbol=self._from_oanda(p["instrument"]),
            side="BUY" if float(p.get("longValueUnits", 0)) > 0 else "SELL",
            volume=float(p.get("longValueUnits") or p.get("shortValueUnits") or 0),
            open_price=float(p.get("averageLongPrice") or p.get("averageShortPrice") or 0),
            current_price=0,
            stop_loss=None,
            take_profit=None,
            unrealized_pl=float(p.get("unrealizedPL", 0) or 0),
            net_profit=float(p.get("pl", 0) or 0),
        )

    # ── Execution ───────────────────────────────────────────────────────────

    def place_order(self, order: OrderRequest) -> str:
        """Place a market order.

        For alert_only / demo: order.volume is already in Oanda units (not lots).
        For live: order.volume is in lots and gets converted to units.
        """
        oanda_inst = self._to_oanda(order.symbol)
        # Oanda expects units. In alert_only/demo, volume is already units.
        # In live mode (MatchTrader), volume is lots and would be converted
        # here — but live mode uses MatchTrader, not Oanda.
        if config.TRADEGUMI_MODE in ("alert_only", "demo"):
            raw_units = round(order.volume)
        else:
            # Fallback: treat as lots (100k per lot)
            raw_units = round(order.volume * 100_000)
        units = raw_units if order.side == "BUY" else -raw_units

        body = {
            "order": {
                "type": "MARKET",
                "instrument": oanda_inst,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }

        if order.stop_loss:
            body["order"]["stopLossOnFill"] = {"price": str(order.stop_loss)}
        if order.take_profit:
            body["order"]["takeProfitOnFill"] = {"price": str(order.take_profit)}

        data = self._request(
            "POST",
            f"/v3/accounts/{self.account_id}/orders",
            json=body,
        )
        return self._parse_order_create_id(data)

    def _parse_order_create_id(self, data: dict) -> str:
        """Return the best available identifier from an Oanda order transaction response."""
        for key in ("orderFillTransaction", "orderCreateTransaction", "orderCancelTransaction", "orderRejectTransaction"):
            transaction = data.get(key)
            if isinstance(transaction, dict) and transaction.get("id"):
                return str(transaction["id"])
        related = data.get("relatedTransactionIDs")
        if related:
            return str(related[0])
        if data.get("lastTransactionID"):
            return str(data["lastTransactionID"])
        raise ProviderRequestError(
            "Oanda order creation response missing transaction identifiers",
            provider="oanda",
            method="POST",
            path=f"/v3/accounts/{self.account_id}/orders",
            operation="order_create",
            attempts=1,
            max_attempts=self.MAX_REQUEST_ATTEMPTS,
            retryable=False,
            error_type="oanda_response_malformed",
        )

    def close_position(self, position_id: str, units: Optional[float] = None):
        """Close a position (full close if units is None)."""
        body = {}
        if units is not None:
            body["units"] = str(int(units))

        self._request(
            "PUT",
            f"/v3/accounts/{self.account_id}/positions/{self._to_oanda(position_id)}/close",
            json=body,
        )

    def modify_sl_tp(self, position_id: str, stop_loss: Optional[float] = None, take_profit: Optional[float] = None):
        """Update SL and/or TP on an open position."""
        body = {}
        if stop_loss is not None:
            body["stopLoss"] = {"price": str(stop_loss)}
        if take_profit is not None:
            body["takeProfit"] = {"price": str(take_profit)}
        if not body:
            return

        self._request(
            "PUT",
            f"/v3/accounts/{self.account_id}/trades/{position_id}/orders",
            json=body,
        )

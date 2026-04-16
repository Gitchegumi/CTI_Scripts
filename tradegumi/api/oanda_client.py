"""Oanda v20 REST client implementation of ExecutionClient."""
import requests
from typing import Optional
from decimal import Decimal

from tradegumi.api.base_client import (
    ExecutionClient, Candle, Position, OrderRequest
)
from tradegumi import config


class OandaClient(ExecutionClient):
    """Thin Oanda v20 REST wrapper.

    Handles instrument format conversion (EURUSD ↔ EUR_USD) internally.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        account_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or config.OANDA_API_KEY
        self.account_id = account_id or config.OANDA_ACCOUNT_ID
        self.base_url = base_url or config.OANDA_BASE_URL
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _to_oanda(self, symbol: str) -> str:
        """EURUSD → EUR_USD"""
        return symbol[:3] + "_" + symbol[3:]

    def _from_oanda(self, oanda_sym: str) -> str:
        """EUR_USD → EURUSD"""
        return oanda_sym.replace("_", "")

    def _request(self, method: str, path: str, **kwargs):
        """Make an authenticated request to Oanda v20."""
        url = f"{self.base_url}{path}"
        resp = self._session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()

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
        params = {"granularity": granularity, "count": count}
        data = self._request("GET", f"/v3/instruments/{oanda_inst}/candles", params=params)
        candles = []
        for c in data.get("candles", []):
            mid = c.get("mid", {})
            candles.append(Candle(
                t=c["time"],
                o=float(mid["o"]),
                h=float(mid["h"]),
                l=float(mid["l"]),
                c=float(mid["c"]),
                s=c.get("volume"),
            ))
        return candles

    def get_account_balance(self) -> float:
        """Return account balance."""
        data = self._request("GET", f"/v3/accounts/{self.account_id}/summary")
        return float(data["account"]["balance"])

    def get_open_positions(self) -> list[Position]:
        """Return list of open positions."""
        data = self._request("GET", f"/v3/accounts/{self.account_id}/openPositions")
        positions = []
        for p in data.get("positions", []):
            long_trade = p.get("longValueUnits", "0")
            short_trade = p.get("shortValueUnits", "0")
            side = "BUY" if long_trade not in ("0", None, "") else "SELL"
            pos = Position(
                id=p["id"],
                symbol=self._from_oanda(p["instrument"]),
                side=side,
                volume=float(p.get("longValueUnits", p["shortValueUnits"]) or 0),
                open_price=float(p.get("averageLongPrice", p["averageShortPrice"]) or 0),
                current_price=float(p.get("midMarketQuote", 0) or 0),
                stop_loss=None,
                take_profit=None,
                unrealized_pl=float(p.get("unrealizedPL", 0) or 0),
                net_profit=float(p.get("pl", 0) or 0),
            )
            positions.append(pos)
        return positions

    def get_position(self, position_id: str) -> Position:
        """Fetch a single position by ID."""
        data = self._request("GET", f"/v3/accounts/{self.account_id}/openPositions/{position_id}")
        p = data["position"]
        return Position(
            id=position_id,
            symbol=self._from_oanda(p["instrument"]),
            side="BUY" if float(p.get("longValueUnits", 0)) > 0 else "SELL",
            volume=float(p.get("longValueUnits", p["shortValueUnits"]) or 0),
            open_price=float(p.get("averageLongPrice", p["averageShortPrice"]) or 0),
            current_price=0,
            stop_loss=None,
            take_profit=None,
            unrealized_pl=float(p.get("unrealizedPL", 0) or 0),
            net_profit=float(p.get("pl", 0) or 0),
        )

    # ── Execution ───────────────────────────────────────────────────────────

    def place_order(self, order: OrderRequest) -> str:
        """Place a market order.

        Returns the trade/opened position id.
        """
        oanda_inst = self._to_oanda(order.symbol)
        units = order.volume if order.side == "BUY" else -order.volume

        body = {
            "order": {
                "type": "MARKET",
                "instrument": oanda_inst,
                "units": str(int(units)) if abs(units) >= 1 else str(units),
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
        return str(data["order"]["id"])

    def close_position(self, position_id: str, units: Optional[float] = None):
        """Close a position (full close if units is None)."""
        body = {}
        if units is not None:
            body["units"] = str(int(units))

        self._request(
            "PUT",
            f"/v3/accounts/{self.account_id}/positions/{position_id}/close",
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
            f"/v3/accounts/{self.account_id}/orders/{position_id}/orders",
            json=body,
        )
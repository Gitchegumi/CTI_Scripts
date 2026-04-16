"""MatchTrader REST client stub — Stage 2 swap-in."""
from typing import Optional
from tradegumi.api.base_client import (
    ExecutionClient, Candle, Position, OrderRequest
)


class MatchTraderClient(ExecutionClient):
    """MatchTrader implementation of ExecutionClient.

    Stage 2 — not yet wired up. Stub exists so signal logic never touches it directly.
    """

    def __init__(self, **kwargs):
        raise NotImplementedError("MatchTrader client is not yet implemented — Stage 2")

    def get_candles(self, instrument, granularity, count):
        raise NotImplementedError

    def get_account_balance(self) -> float:
        raise NotImplementedError

    def get_open_positions(self) -> list[Position]:
        raise NotImplementedError

    def place_order(self, order: OrderRequest) -> str:
        raise NotImplementedError

    def close_position(self, position_id: str, units: Optional[float] = None):
        raise NotImplementedError

    def modify_sl_tp(self, position_id: str, stop_loss: Optional[float], take_profit: Optional[float]):
        raise NotImplementedError

    def get_position(self, position_id: str) -> Position:
        raise NotImplementedError
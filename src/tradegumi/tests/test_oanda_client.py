"""Unit tests for the Oanda v20 REST client contract."""

import pytest
import requests

from tradegumi.api.base_client import OrderRequest, ProviderRequestError
from tradegumi.api.oanda_client import OandaClient


class FakeResponse:
    """Small requests.Response stand-in for Oanda client tests."""

    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


class FakeSession:
    """Session test double that records requests and returns queued responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def client_with_session(responses, *, base_url="https://api-fxpractice.oanda.com/"):
    client = OandaClient(api_key="token", account_id="abc", base_url=base_url)
    client._session = FakeSession(responses)
    client.RETRY_BACKOFF_SECONDS = 0
    return client


def test_url_normalization_removes_trailing_slash():
    client = client_with_session([])

    assert client.base_url == "https://api-fxpractice.oanda.com"
    assert client._url_for_path("/v3/accounts/abc/summary") == "https://api-fxpractice.oanda.com/v3/accounts/abc/summary"


def test_get_candles_uses_midpoint_price_and_preserves_complete():
    client = client_with_session([
        FakeResponse(200, {
            "candles": [
                {
                    "time": "2026-05-07T10:00:00Z",
                    "complete": False,
                    "volume": 12,
                    "mid": {"o": "1.1", "h": "1.2", "l": "1.0", "c": "1.15"},
                }
            ]
        })
    ])

    candles = client.get_candles("EURUSD", "M5", 1)

    assert candles[0].complete is False
    method, url, kwargs = client._session.calls[0]
    assert method == "GET"
    assert url == "https://api-fxpractice.oanda.com/v3/instruments/EUR_USD/candles"
    assert kwargs["params"]["price"] == "M"
    assert kwargs["timeout"] == client.REQUEST_TIMEOUT_SECONDS


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_statuses_are_retried(status):
    client = client_with_session([
        FakeResponse(status, {"errorMessage": "temporary"}),
        FakeResponse(200, {"ok": True}),
    ])

    data = client._request("GET", "/v3/accounts/abc/summary", operation="account_summary")

    assert data == {"ok": True}
    assert len(client._session.calls) == 2


def test_504_exhaustion_raises_gateway_timeout_context():
    client = client_with_session([
        FakeResponse(504),
        FakeResponse(504),
        FakeResponse(504),
    ])

    with pytest.raises(ProviderRequestError) as exc_info:
        client.get_candles("EURUSD", "M5", 100)

    exc = exc_info.value
    assert exc.error_type == "oanda_gateway_timeout"
    assert exc.status_code == 504
    assert exc.instrument == "EUR_USD"
    assert exc.granularity == "M5"
    assert exc.attempts == client.MAX_REQUEST_ATTEMPTS


def test_non_retryable_client_error_fails_immediately():
    client = client_with_session([FakeResponse(401)])

    with pytest.raises(ProviderRequestError) as exc_info:
        client._request("GET", "/v3/accounts/abc/summary", operation="account_summary")

    assert exc_info.value.status_code == 401
    assert exc_info.value.retryable is False
    assert len(client._session.calls) == 1


def test_network_timeout_is_retried():
    client = client_with_session([
        requests.Timeout("slow"),
        FakeResponse(200, {"ok": True}),
    ])

    data = client._request("GET", "/v3/accounts/abc/summary", operation="account_summary")

    assert data == {"ok": True}
    assert len(client._session.calls) == 2


def test_malformed_candle_response_raises_provider_error():
    client = client_with_session([FakeResponse(200, {"candles": [{"time": "2026-05-07T10:00:00Z", "mid": {}}]})])

    with pytest.raises(ProviderRequestError) as exc_info:
        client.get_candles("EURUSD", "M5", 1)

    assert exc_info.value.error_type == "oanda_response_malformed"


def test_documented_endpoint_paths_are_used():
    client = client_with_session([
        FakeResponse(200, {"prices": []}),
        FakeResponse(200, {"account": {"balance": "100000"}}),
        FakeResponse(200, {"instruments": []}),
        FakeResponse(200, {"positions": []}),
        FakeResponse(200, {"trades": []}),
        FakeResponse(200, {"position": {"instrument": "EUR_USD", "longValueUnits": "1", "averageLongPrice": "1.1"}}),
        FakeResponse(200, {}),
        FakeResponse(200, {}),
        FakeResponse(200, {"orderCreateTransaction": {"id": "42"}}),
    ])

    client.get_pricing(["EURUSD"])
    client.get_account_balance()
    client.get_account_instruments()
    client.get_open_positions()
    client.get_position("EURUSD")
    client.close_position("EURUSD")
    client.modify_sl_tp("123", stop_loss=1.0)
    client.place_order(OrderRequest(symbol="EURUSD", side="BUY", volume=1))

    paths = [call[1].removeprefix(client.base_url) for call in client._session.calls]
    assert "/v3/accounts/abc/pricing" in paths
    assert "/v3/accounts/abc/summary" in paths
    assert "/v3/accounts/abc/instruments" in paths
    assert "/v3/accounts/abc/openPositions" in paths
    assert "/v3/accounts/abc/openTrades" in paths
    assert "/v3/accounts/abc/positions/EUR_USD" in paths
    assert "/v3/accounts/abc/positions/EUR_USD/close" in paths
    assert "/v3/accounts/abc/trades/123/orders" in paths
    assert "/v3/accounts/abc/orders" in paths


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"orderFillTransaction": {"id": "11"}, "orderCreateTransaction": {"id": "10"}}, "11"),
        ({"orderCreateTransaction": {"id": "10"}}, "10"),
        ({"orderCancelTransaction": {"id": "12"}}, "12"),
        ({"orderRejectTransaction": {"id": "13"}}, "13"),
        ({"relatedTransactionIDs": ["14"], "lastTransactionID": "15"}, "14"),
        ({"lastTransactionID": "15"}, "15"),
    ],
)
def test_transaction_based_order_create_parser(payload, expected):
    client = client_with_session([])

    assert client._parse_order_create_id(payload) == expected

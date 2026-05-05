"""Unit tests for the Oanda execution client."""

from tradegumi.api.oanda_client import OandaClient


def test_trade_history_clamps_count_to_oanda_limit():
    client = OandaClient(api_key="token", account_id="acct", base_url="https://example.test")
    captured = {}

    def fake_request(method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["params"] = kwargs["params"]
        return {"trades": []}

    client._request = fake_request

    assert client.get_trade_history(count=1000) == []
    assert captured["method"] == "GET"
    assert captured["path"] == "/v3/accounts/acct/trades"
    assert captured["params"] == {"count": 500, "state": "CLOSED"}

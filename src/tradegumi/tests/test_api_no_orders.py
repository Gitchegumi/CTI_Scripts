"""Guard tests: the API never places broker orders (Constitution III, FR-004)."""

import pathlib

import pytest

# Method names that would place/modify/close broker orders. The API must never
# call these; only read methods are permitted.
ORDER_METHODS = (
    "place_order",
    "create_order",
    "submit_order",
    "open_position",
    "close_position",
    "close_trade",
    "modify_order",
    "cancel_order",
    "place_market_order",
)

API_DIR = pathlib.Path(__file__).resolve().parent.parent / "api"


def test_route_and_dep_sources_contain_no_order_calls():
    sources = list((API_DIR / "routes").glob("*.py")) + [API_DIR / "deps.py"]
    offenders = []
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for method in ORDER_METHODS:
            if f".{method}(" in text:
                offenders.append(f"{path.name}: {method}")
    assert not offenders, f"order-placement calls found in API: {offenders}"


def test_no_route_path_implies_order_placement():
    from fastapi.routing import APIRoute
    from tradegumi.api_app import create_app
    app = create_app()
    suspicious = [
        r.path for r in app.routes
        if isinstance(r, APIRoute) and ("order" in r.path or "/place" in r.path)
    ]
    assert suspicious == []


@pytest.fixture(autouse=True)
def _auth_off(no_auth):
    return no_auth


def test_positions_only_calls_read_method(client, monkeypatch):
    calls = []

    class RecordingClient:
        def get_open_positions(self):
            calls.append("get_open_positions")
            return []

        def __getattr__(self, name):
            # Any unexpected (e.g. order-placement) attribute access is recorded.
            calls.append(name)
            return lambda *a, **k: None

    monkeypatch.setattr(
        "tradegumi.api.routes.trades.get_api_execution_client", lambda: RecordingClient()
    )
    resp = client.get("/api/positions")
    assert resp.status_code == 200
    assert calls == ["get_open_positions"]
    for method in ORDER_METHODS:
        assert method not in calls

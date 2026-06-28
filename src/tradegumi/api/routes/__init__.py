"""Per-concern FastAPI routers for the TradeGumi API service.

Each module owns one slice of the public API surface (status, data, journal,
trades, config/actions, strategy metrics). The app factory in
``tradegumi.api_app`` mounts them; shared cross-cutting concerns (Postgres,
Redis, auth, the read-only execution client) come from
``tradegumi.api.deps``.
"""

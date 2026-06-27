"""WebSocket route handler for /ws/stream endpoint.

Single multiplexed endpoint with channel-based subscriptions.
Supports optional API key auth, connection tracking, and Prometheus metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect

from backend.app.api.ws.manager import ws_manager
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

log = get_logger("conflu.api.ws.handler")

ws_router = APIRouter()

# Lazy Prometheus metrics - initialize at module level with duplicate protection
_ws_messages_total: Any = None
_ws_errors_total: Any = None

try:
    from prometheus_client import REGISTRY, Counter

    # Check if metrics already exist in registry to avoid duplicate registration on reload
    if "ws_messages_total" not in REGISTRY._names_to_collectors:
        _ws_messages_total = Counter("ws_messages_total", "Total WebSocket messages", labelnames=("channel_type",))
    else:
        # Get existing collector
        for collector in REGISTRY._collector_to_names:
            if "ws_messages_total" in REGISTRY._collector_to_names[collector]:
                _ws_messages_total = collector
                break

    if "ws_errors_total" not in REGISTRY._names_to_collectors:
        _ws_errors_total = Counter("ws_errors_total", "Total WebSocket errors", labelnames=("error_type",))
    else:
        for collector in REGISTRY._collector_to_names:
            if "ws_errors_total" in REGISTRY._collector_to_names[collector]:
                _ws_errors_total = collector
                break

except ImportError:
    _ws_messages_total = None
    _ws_errors_total = None


def _get_ws_metrics() -> tuple[Any, Any]:
    """Get Prometheus WS metrics (already initialized at module level)."""
    return _ws_messages_total, _ws_errors_total


@ws_router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket) -> None:
    """Unified WebSocket endpoint for all real-time streaming.

    Channel types:
    - price:{symbol}          — Real-time price updates
    - indicator:{symbol}:{name} — Indicator value updates
    - signal:{symbol}         — Screener signal updates
    - screener:{name}         — Screener run results
    - risk:{portfolio}        — Risk metric updates
    - backtest:{run_id}       — Backtest progress updates
    """
    ws_id = str(uuid4())
    ws_messages, ws_errors = _get_ws_metrics()

    try:
        await websocket.accept()
        log.info("ws_connection_accepted", connection_id=ws_id)

        # ── Optional Auth ──
        try:
            initial = await websocket.receive_json()
            if initial.get("type") == "auth" and settings.api.api_keys:
                key = initial.get("api_key", "")
                if key not in settings.api.api_keys:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "AUTH_FAILED",
                            "message": "Invalid API key",
                        }
                    )
                    await websocket.close(code=4001)
                    return
        except Exception:
            # If not an auth message, treat as normal subscription
            pass

        # ── Connected Confirmation ──
        await websocket.send_json(
            {
                "type": "connected",
                "connection_id": ws_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "server_version": "0.2.0",
            }
        )

        # ── Register ──
        await ws_manager.register(ws_id, websocket)

        # ── Main Event Loop ──
        while True:
            data = await websocket.receive_json()
            if ws_messages is not None:
                channels = data.get("channels")
                channel_type = channels[0] if isinstance(channels, list) else "unknown"
                ws_messages.labels(channel_type=channel_type).inc()
            await ws_manager.handle_message(ws_id, websocket, data)

    except WebSocketDisconnect:
        ws_manager.disconnect(ws_id)
        log.info("ws_client_disconnected", connection_id=ws_id)
    except Exception:
        log.exception("ws_error", connection_id=ws_id)
        if ws_errors is not None:
            ws_errors.labels(error_type="unhandled").inc()
        from contextlib import suppress

        with suppress(Exception):
            await websocket.close(code=1011)


def register_ws_routes(app: FastAPI) -> None:
    """Include the WebSocket router on the FastAPI app.

    Args:
        app: FastAPI application instance.
    """
    app.include_router(ws_router)
    log.info("ws_routes_registered")

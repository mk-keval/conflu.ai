"""Unified WebSocket connection manager for all streaming channels.

Features:
- Single connection pool shared across all channel types
- Channel-based subscriptions (subscribe/unsubscribe on-the-fly)
- Per-connection sequence numbering
- History buffer for reconnection replay
- Background update loops (on-demand: only when clients connected)
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from backend.app.core.logging import get_logger

log = get_logger("conflu.api.ws.manager")

# Lazy import to avoid circular deps
_ws_connections_gauge: Any = None


def _get_ws_gauge() -> Any:
    """Get the Prometheus WS connections gauge (lazy import with duplicate protection)."""
    global _ws_connections_gauge
    if _ws_connections_gauge is None:
        try:
            from prometheus_client import REGISTRY, Gauge

            if "ws_connections_active" not in REGISTRY._names_to_collectors:
                _ws_connections_gauge = Gauge("ws_connections_active", "Active WebSocket connections")
            else:
                # Get existing collector
                for collector in REGISTRY._collector_to_names:
                    if "ws_connections_active" in REGISTRY._collector_to_names[collector]:
                        _ws_connections_gauge = collector
                        break
        except ImportError:
            _ws_connections_gauge = None
    return _ws_connections_gauge


class WebSocketManager:
    """Unified WebSocket connection manager for all streaming channels.

    Single connection pool shared across all channel types.
    Channel-based subscriptions (subscribe/unsubscribe on-the-fly).
    Per-connection sequence numbering.
    History buffer for reconnection replay.
    Background update loops (on-demand: only when clients connected).
    """

    def __init__(self) -> None:
        self._connections: dict[str, Any] = {}
        self._subscriptions: dict[str, set[str]] = defaultdict(set)
        self._channel_subscribers: dict[str, set[str]] = defaultdict(set)
        self._sequences: dict[str, int] = defaultdict(int)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._max_history: int = 100
        self._background_tasks: dict[str, asyncio.Task[Any]] = {}
        self._log = get_logger("conflu.api.ws.manager")

    async def register(self, ws_id: str, websocket: Any) -> None:
        """Register a new WebSocket connection."""
        self._connections[ws_id] = websocket
        gauge = _get_ws_gauge()
        if gauge is not None:
            gauge.inc()
        self._log.info("ws_client_registered", connection_id=ws_id)

    def disconnect(self, ws_id: str) -> None:
        """Remove a WebSocket connection and its subscriptions."""
        # Remove from channel subscribers
        for channel in self._subscriptions.get(ws_id, set()):
            self._channel_subscribers[channel].discard(ws_id)
        # Remove connection
        self._connections.pop(ws_id, None)
        self._subscriptions.pop(ws_id, None)
        self._history.pop(ws_id, None)
        gauge = _get_ws_gauge()
        if gauge is not None:
            gauge.dec()
        self._log.info("ws_client_disconnected", connection_id=ws_id)

    async def handle_message(self, ws_id: str, websocket: Any, data: dict[str, Any]) -> None:
        """Process incoming client message.

        Supported message types:
        - {"type": "subscribe", "channels": [...]}
        - {"type": "unsubscribe", "channels": [...]}
        - {"type": "ping"}
        - {"type": "resync", "last_sequence": N}
        """
        msg_type = data.get("type", "")

        if msg_type == "subscribe":
            channels = data.get("channels", [])
            await self._handle_subscribe(ws_id, channels)

        elif msg_type == "unsubscribe":
            channels = data.get("channels", [])
            await self._handle_unsubscribe(ws_id, channels)

        elif msg_type == "ping":
            with suppress(Exception):
                await websocket.send_json(
                    {
                        "type": "pong",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

        elif msg_type == "resync":
            last_seq = data.get("last_sequence", 0)
            await self._resync(ws_id, websocket, last_seq)

        else:
            self._log.warning("unknown_ws_message", type=msg_type, connection_id=ws_id)

    async def _handle_subscribe(self, ws_id: str, channels: list[str]) -> None:
        """Subscribe a connection to channels."""
        for channel in channels:
            self._subscriptions[ws_id].add(channel)
            self._channel_subscribers[channel].add(ws_id)
        self._log.info("ws_subscribed", connection_id=ws_id, channels=channels)

    async def _handle_unsubscribe(self, ws_id: str, channels: list[str]) -> None:
        """Unsubscribe a connection from channels."""
        for channel in channels:
            self._subscriptions[ws_id].discard(channel)
            self._channel_subscribers[channel].discard(ws_id)

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        """Send a message to all subscribers of a channel."""
        ws_ids = list(self._channel_subscribers.get(channel, set()))
        if not ws_ids:
            return

        # Add sequence number per connection
        disconnected: list[str] = []
        for ws_id in ws_ids:
            self._sequences[ws_id] += 1
            msg = dict(message)
            msg["sequence"] = self._sequences[ws_id]

            # Store in history
            self._history[ws_id].append(msg)
            if len(self._history[ws_id]) > self._max_history:
                self._history[ws_id].pop(0)

            # Send
            ws = self._connections.get(ws_id)
            if ws:
                try:
                    await ws.send_json(msg)
                except Exception:
                    disconnected.append(ws_id)
            else:
                disconnected.append(ws_id)

        for ws_id in disconnected:
            self.disconnect(ws_id)

    async def _resync(self, ws_id: str, websocket: Any, last_sequence: int) -> None:
        """Replay missed messages for reconnecting client."""
        history = self._history.get(ws_id, [])
        if last_sequence < (self._sequences[ws_id] - len(history)):
            # Too many missed — send reconnection guidance
            with suppress(Exception):
                await websocket.send_json(
                    {
                        "type": "resync_required",
                        "message": "Too many messages missed. Reconnect for full state.",
                        "current_sequence": self._sequences[ws_id],
                    }
                )
            return

        missed = [msg for msg in history if msg.get("sequence", 0) > last_sequence]
        for msg in missed:
            try:
                await websocket.send_json(msg)
            except Exception:
                break

    def start_background_tasks(self, _app: Any) -> None:
        """Start background update loops for active channels.

        Launched from FastAPI lifespan startup.
        """
        # Price update loop (default 1s interval per D-07)
        self._background_tasks["price"] = asyncio.create_task(self._price_update_loop())
        # Indicator update loop (default 5s interval per D-07)
        self._background_tasks["indicator"] = asyncio.create_task(self._indicator_update_loop())
        self._log.info("ws_background_tasks_started")

    async def _price_update_loop(self) -> None:
        """Periodic price update broadcast."""
        while True:
            try:
                from backend.app.api.ws.channels import price_update_provider

                # Find all price:* subscriptions
                price_channels = [ch for ch in self._channel_subscribers if ch.startswith("price:")]
                for channel in price_channels:
                    symbol = channel.split(":", 1)[1]
                    data = await price_update_provider(symbol)
                    await self.broadcast(
                        channel,
                        {
                            "type": "price_update",
                            "channel": channel,
                            "data": data,
                        },
                    )
                await asyncio.sleep(1.0)  # 1s interval per D-07
            except asyncio.CancelledError:
                break
            except Exception:
                self._log.exception("price_update_loop_error")
                await asyncio.sleep(5.0)

    async def _indicator_update_loop(self) -> None:
        """Periodic indicator value broadcast (slower interval)."""
        while True:
            try:
                from backend.app.api.ws.channels import indicator_update_provider

                indicator_channels = [ch for ch in self._channel_subscribers if ch.startswith("indicator:")]
                for channel in indicator_channels:
                    parts = channel.split(":")
                    if len(parts) >= 3:
                        _, symbol, indicator = parts[0], parts[1], parts[2]
                        data = await indicator_update_provider(symbol, indicator)
                        await self.broadcast(
                            channel,
                            {
                                "type": "indicator_update",
                                "channel": channel,
                                "data": data,
                            },
                        )
                await asyncio.sleep(5.0)  # 5s interval per D-07
            except asyncio.CancelledError:
                break
            except Exception:
                self._log.exception("indicator_update_loop_error")
                await asyncio.sleep(10.0)

    async def close_all(self) -> None:
        """Close all connections and cancel background tasks."""
        # Stop alert engine (Phase 6 Alert Engine — not yet implemented).
        # Guard the import so shutdown/reload doesn't crash if the module is missing.
        try:
            from backend.app.infrastructure.screener.alerts import alert_engine

            if alert_engine.is_running:
                await alert_engine.stop_background_loop()
        except ImportError:
            pass

        # Cancel background tasks
        for _name, task in self._background_tasks.items():
            task.cancel()
        # Close all WebSocket connections
        for _ws_id, ws in list(self._connections.items()):
            with suppress(Exception):
                await ws.close()
        self._connections.clear()
        self._subscriptions.clear()
        self._channel_subscribers.clear()
        self._log.info("ws_all_connections_closed")


# Singleton instance
ws_manager = WebSocketManager()

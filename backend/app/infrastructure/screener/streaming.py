"""WebSocket connection manager for real-time screener streaming.

Provides ConnectionManager class with:
- Connection registration/disconnection per screen
- Sequence-numbered message broadcasting
- Delta updates (changed symbols only)
- Reconnection with history replay
- Heartbeat and configurable intervals
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.infrastructure.screener.configs import load_screen_template
from backend.app.infrastructure.screener.engine import ScreenEngine

log = get_logger("conflu.screener.streaming")


class ConnectionManager:
    """Manages WebSocket connections with sequence tracking.

    Each screen has its own set of connections, sequence counter,
    and message history for reconnection support.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[Any]] = defaultdict(set)
        self._sequences: dict[str, int] = defaultdict(int)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._max_history: int = settings.screen.max_history
        self._stream_interval: float = settings.screen.stream_interval_s
        self._engine = ScreenEngine()
        self._log = get_logger("conflu.screener.streaming")

    async def register(self, screen_id: str, websocket: Any) -> None:
        """Register a WebSocket connection for a screen.

        Args:
            screen_id: Screen identifier (template name).
            websocket: FastAPI WebSocket connection instance.
        """
        self._connections[screen_id].add(websocket)
        self._log.info("client_connected", screen_id=screen_id)

        # Send full snapshot on initial connection
        try:
            result = await self._engine.screen(screen_id)
            snapshot = {
                "type": "screen_update",
                "screen_id": screen_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": result.symbols,
                "total_matched": result.symbols_matched,
                "total_symbols": result.total_symbols,
            }
            await self._send_with_sequence(screen_id, snapshot, websocket)
        except Exception:
            self._log.exception("initial_screen_failed", screen_id=screen_id)
            await websocket.send_json({
                "type": "error",
                "screen_id": screen_id,
                "message": "Failed to load initial screen data",
            })

    async def disconnect(self, screen_id: str, websocket: Any) -> None:
        """Remove a WebSocket connection.

        Args:
            screen_id: Screen identifier.
            websocket: WebSocket connection to remove.
        """
        self._connections[screen_id].discard(websocket)
        self._log.info("client_disconnected", screen_id=screen_id)

    async def broadcast(self, screen_id: str, message: dict[str, Any]) -> None:
        """Send a message to all clients on a screen, with sequencing.

        Args:
            screen_id: Screen identifier.
            message: Message dict to broadcast.
        """
        # Add sequence number
        self._sequences[screen_id] += 1
        message["sequence"] = self._sequences[screen_id]

        # Store in history for reconnection
        self._history[screen_id].append(dict(message))
        if len(self._history[screen_id]) > self._max_history:
            self._history[screen_id].pop(0)

        # Send to all connected clients
        disconnected: list[Any] = []
        for ws in list(self._connections.get(screen_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self._connections[screen_id].discard(ws)

    async def _send_with_sequence(
        self,
        screen_id: str,
        message: dict[str, Any],
        websocket: Any,
    ) -> None:
        """Send a message to a single client with sequence number."""
        self._sequences[screen_id] += 1
        message["sequence"] = self._sequences[screen_id]
        try:
            await websocket.send_json(message)
        except Exception:
            self._log.warning("send_failed", screen_id=screen_id)

    async def resync(self, screen_id: str, websocket: Any, last_sequence: int) -> None:
        """Replay missed messages for a reconnecting client.

        Args:
            screen_id: Screen identifier.
            websocket: Reconnecting WebSocket connection.
            last_sequence: Last sequence number the client received.
        """
        history = self._history.get(screen_id, [])

        if len(history) >= self._max_history or last_sequence < (
            self._sequences[screen_id] - len(history)
        ):
            # Too many missed — send full snapshot instead
            self._log.info(
                "resync_full_snapshot",
                screen_id=screen_id,
                last_sequence=last_sequence,
            )
            await self.register(screen_id, websocket)
            return

        # Replay missed messages
        missed = [
            msg for msg in history
            if msg.get("sequence", 0) > last_sequence
        ]
        for msg in missed:
            try:
                await websocket.send_json(msg)
            except Exception:
                self._log.warning("resync_send_failed", screen_id=screen_id)
                break

        self._log.info(
            "resync_complete",
            screen_id=screen_id,
            replayed=len(missed),
        )

    async def stream_loop(self, screen_id: str) -> None:
        """Background task that periodically evaluates a screen and broadcasts.

        This is designed to be launched as an asyncio task. It runs the
        screen at the configured interval and pushes delta updates.

        Args:
            screen_id: Screen template name to stream.
        """
        self._log.info("stream_started", screen_id=screen_id)

        while True:
            try:
                # Check if any clients remain
                if not self._connections.get(screen_id):
                    await asyncio.sleep(self._stream_interval)
                    continue

                # Run screen evaluation
                result = await self._engine.screen(screen_id)

                # Build delta update
                message = {
                    "type": "screen_update",
                    "screen_id": screen_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "interval_ms": self._stream_interval * 1000,
                    "results": result.symbols,
                    "total_matched": result.symbols_matched,
                    "total_symbols": result.total_symbols,
                }

                await self.broadcast(screen_id, message)

            except asyncio.CancelledError:
                self._log.info("stream_cancelled", screen_id=screen_id)
                break
            except Exception:
                self._log.exception("stream_error", screen_id=screen_id)

            await asyncio.sleep(self._stream_interval)

    def get_connections_count(self, screen_id: str) -> int:
        """Get number of connected clients for a screen."""
        return len(self._connections.get(screen_id, set()))

    async def handle_client_message(
        self,
        screen_id: str,
        websocket: Any,
        data: dict[str, Any],
    ) -> None:
        """Handle an incoming client control message.

        Supported messages:
        - {"type": "ping"} -> responds with pong
        - {"type": "resync", "last_sequence": N} -> replay missed messages
        - {"type": "change_interval", "interval_ms": N} -> update stream rate

        Args:
            screen_id: Screen identifier.
            websocket: Client WebSocket connection.
            data: Parsed JSON message from client.
        """
        msg_type = data.get("type", "")

        if msg_type == "ping":
            await websocket.send_json({
                "type": "pong",
                "screen_id": screen_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        elif msg_type == "resync":
            last_seq = data.get("last_sequence", 0)
            await self.resync(screen_id, websocket, last_seq)

        elif msg_type == "change_interval":
            new_interval = data.get("interval_ms", self._stream_interval * 1000)
            self._stream_interval = max(1.0, new_interval / 1000)
            self._log.info(
                "stream_interval_changed",
                screen_id=screen_id,
                interval_s=self._stream_interval,
            )

        else:
            self._log.warning(
                "unknown_client_message",
                screen_id=screen_id,
                message_type=msg_type,
            )

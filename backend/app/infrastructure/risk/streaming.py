"""RiskStreamManager — WebSocket connection management for real-time risk updates.

Follows the Phase 3 ConnectionManager pattern exactly.
Provides connection registration, sequence-numbered broadcasting,
reconnection history replay, and on-demand background updates.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from backend.app.core.logging import get_logger

log = get_logger("conflu.risk.streaming")


class RiskStreamManager:
    """Manage WebSocket connections for real-time risk updates.

    On-demand design — only computes/broadcasts when at least one client
    is connected. Supports reconnection with history replay.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[Any]] = defaultdict(set)
        self._sequences: dict[str, int] = defaultdict(int)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._max_history: int = 100
        self._log = get_logger("conflu.risk.streaming")

    async def register(self, portfolio_id: str, websocket: Any) -> None:
        """Register a WebSocket connection for a portfolio.

        Sends a full risk snapshot on initial connection (replay history).

        Args:
            portfolio_id: Portfolio identifier.
            websocket: WebSocket connection instance.
        """
        self._connections[portfolio_id].add(websocket)
        self._log.info("risk_client_connected", portfolio_id=portfolio_id)

        # Send full snapshot on connect
        self._send_with_sequence(
            portfolio_id,
            {
                "type": "risk_snapshot",
                "portfolio_id": portfolio_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {"status": "connected", "message": "Risk monitoring active"},
            },
            websocket,
        )

    def unregister(self, portfolio_id: str, websocket: Any) -> None:
        """Remove a WebSocket connection.

        Args:
            portfolio_id: Portfolio identifier.
            websocket: WebSocket connection to remove.
        """
        self._connections[portfolio_id].discard(websocket)
        self._log.info("risk_client_disconnected", portfolio_id=portfolio_id)

    async def broadcast_risk_update(
        self,
        portfolio_id: str,
        update_type: str,
        data: dict[str, Any],
    ) -> None:
        """Broadcast a risk update to all connected clients for a portfolio.

        Message format: {type, portfolio_id, timestamp, sequence, data}

        Args:
            portfolio_id: Portfolio identifier.
            update_type: Type of update (risk_snapshot, risk_delta,
                        var_breach_alert, correlation_shift, hedge_adjustment).
            data: Update payload data.
        """
        if not self._connections.get(portfolio_id):
            return  # No clients, skip broadcast

        # Build message with sequence number
        self._sequences[portfolio_id] += 1
        message = {
            "type": update_type,
            "portfolio_id": portfolio_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "sequence": self._sequences[portfolio_id],
            "data": data,
        }

        # Store in history for reconnection replay
        self._history[portfolio_id].append(dict(message))
        if len(self._history[portfolio_id]) > self._max_history:
            self._history[portfolio_id].pop(0)

        # Send to all connected clients
        disconnected: list[Any] = []
        for ws in list(self._connections.get(portfolio_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self._connections[portfolio_id].discard(ws)

    async def start_background_updates(
        self,
        portfolio_id: str,
        update_coro: Callable[[], Coroutine[Any, Any, dict[str, Any]]],
        interval_s: float = 5.0,
    ) -> None:
        """Periodic polling loop that broadcasts updates while clients connected.

        Args:
            portfolio_id: Portfolio identifier.
            update_coro: Async callable that returns risk data dict.
            interval_s: Seconds between updates.
        """
        self._log.info(
            "risk_background_updates_started",
            portfolio_id=portfolio_id,
            interval_s=interval_s,
        )

        while True:
            try:
                # Only compute when clients are connected
                if not self._connections.get(portfolio_id):
                    await asyncio.sleep(interval_s)
                    continue

                risk_data = await update_coro()
                await self.broadcast_risk_update(portfolio_id, "risk_delta", risk_data)

            except asyncio.CancelledError:
                self._log.info(
                    "risk_background_updates_cancelled",
                    portfolio_id=portfolio_id,
                )
                break
            except Exception:
                self._log.exception(
                    "risk_background_update_error",
                    portfolio_id=portfolio_id,
                )

            await asyncio.sleep(interval_s)

    async def close_all(self) -> None:
        """Close all WebSocket connections."""
        for portfolio_id, connections in self._connections.items():
            for ws in list(connections):
                try:
                    await ws.close()
                except Exception:
                    pass
            self._connections[portfolio_id].clear()
        self._log.info("risk_all_connections_closed")

    def has_connections(self, portfolio_id: str) -> bool:
        """Check if a portfolio has active connections.

        Args:
            portfolio_id: Portfolio identifier.

        Returns:
            True if at least one client is connected.
        """
        return bool(self._connections.get(portfolio_id))

    @property
    def active_portfolios(self) -> list[str]:
        """List portfolios with active connections.

        Returns:
            List of portfolio IDs with active connections.
        """
        return [pid for pid, conns in self._connections.items() if conns]

    async def resync(self, portfolio_id: str, websocket: Any, last_sequence: int) -> None:
        """Replay missed messages for a reconnecting client.

        Args:
            portfolio_id: Portfolio identifier.
            websocket: Reconnecting WebSocket connection.
            last_sequence: Last sequence number the client received.
        """
        history = self._history.get(portfolio_id, [])

        if last_sequence < (self._sequences[portfolio_id] - len(history)):
            # Too many missed — send full snapshot
            self._log.info(
                "risk_resync_full_snapshot",
                portfolio_id=portfolio_id,
                last_sequence=last_sequence,
            )
            await self.register(portfolio_id, websocket)
            return

        # Replay missed messages
        missed = [msg for msg in history if msg.get("sequence", 0) > last_sequence]
        for msg in missed:
            try:
                await websocket.send_json(msg)
            except Exception:
                self._log.warning("risk_resync_send_failed", portfolio_id=portfolio_id)
                break

        self._log.info(
            "risk_resync_complete",
            portfolio_id=portfolio_id,
            replayed=len(missed),
        )

    async def handle_client_message(
        self,
        portfolio_id: str,
        websocket: Any,
        data: dict[str, Any],
    ) -> None:
        """Handle an incoming client control message.

        Supported messages:
        - {"type": "ping"} → responds with pong
        - {"type": "resync", "last_sequence": N} → replay missed messages

        Args:
            portfolio_id: Portfolio identifier.
            websocket: Client WebSocket connection.
            data: Parsed JSON message from client.
        """
        msg_type = data.get("type", "")

        if msg_type == "ping":
            await websocket.send_json(
                {
                    "type": "pong",
                    "portfolio_id": portfolio_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

        elif msg_type == "resync":
            last_seq = data.get("last_sequence", 0)
            await self.resync(portfolio_id, websocket, last_seq)

        else:
            self._log.warning(
                "unknown_risk_client_message",
                portfolio_id=portfolio_id,
                message_type=msg_type,
            )

    def count_connections(self, portfolio_id: str) -> int:
        """Get number of connected clients for a portfolio.

        Args:
            portfolio_id: Portfolio identifier.

        Returns:
            Number of active connections.
        """
        return len(self._connections.get(portfolio_id, set()))

    def _send_with_sequence(
        self,
        portfolio_id: str,
        message: dict[str, Any],
        websocket: Any,
    ) -> None:
        """Send a message to a single client with sequence number.

        Args:
            portfolio_id: Portfolio identifier.
            message: Message dict to send.
            websocket: Target WebSocket connection.
        """
        self._sequences[portfolio_id] += 1
        message["sequence"] = self._sequences[portfolio_id]
        try:
            # FastAPI WebSocket send_json is async; this is a convenience
            # for sync context. Use broadcast for full async.
            asyncio.ensure_future(websocket.send_json(message))
        except Exception:
            self._log.warning("risk_send_failed", portfolio_id=portfolio_id)

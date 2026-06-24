"""Tests for WebSocket ConnectionManager."""

from __future__ import annotations

import pytest

from backend.app.infrastructure.screener.streaming import ConnectionManager


class MockWebSocket:
    """Minimal mock for testing WebSocket connections."""

    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.closed = False

    async def send_json(self, data: dict) -> None:
        self.messages.append(data)


class TestConnectionManager:
    """Test ConnectionManager basic operations."""

    @pytest.fixture
    def manager(self) -> ConnectionManager:
        return ConnectionManager()

    @pytest.fixture
    def screen_id(self) -> str:
        return "test-screen"

    def test_initial_connection_count(self, manager: ConnectionManager, screen_id: str) -> None:
        assert manager.get_connections_count(screen_id) == 0

    def test_register_and_disconnect(self, manager: ConnectionManager, screen_id: str) -> None:
        async def _run() -> None:
            ws = MockWebSocket()
            await manager.register(screen_id, ws)
            assert manager.get_connections_count(screen_id) == 1
            await manager.disconnect(screen_id, ws)
            assert manager.get_connections_count(screen_id) == 0

        import asyncio
        asyncio.run(_run())

    def test_broadcast_adds_sequence(self, manager: ConnectionManager, screen_id: str) -> None:
        async def _run() -> None:
            ws = MockWebSocket()
            await manager.register(screen_id, ws)
            # Clear the initial registration message
            ws.messages.clear()

            await manager.broadcast(screen_id, {"type": "test", "data": "hello"})
            assert len(ws.messages) >= 1
            # Check sequence was added
            last_msg = ws.messages[-1]
            assert "sequence" in last_msg
            assert last_msg["sequence"] >= 1

        import asyncio
        asyncio.run(_run())

    def test_broadcast_with_no_connections(self, manager: ConnectionManager, screen_id: str) -> None:
        """Broadcasting with no connections should not raise."""
        async def _run() -> None:
            await manager.broadcast(screen_id, {"type": "test"})

        import asyncio
        asyncio.run(_run())

    def test_handle_client_message_ping(self, manager: ConnectionManager, screen_id: str) -> None:
        async def _run() -> None:
            ws = MockWebSocket()
            await manager.register(screen_id, ws)
            ws.messages.clear()

            await manager.handle_client_message(screen_id, ws, {"type": "ping"})
            assert len(ws.messages) == 1
            assert ws.messages[0]["type"] == "pong"

        import asyncio
        asyncio.run(_run())

    def test_resync_replays_messages(self, manager: ConnectionManager, screen_id: str) -> None:
        async def _run() -> None:
            ws1 = MockWebSocket()
            await manager.register(screen_id, ws1)
            ws1.messages.clear()

            # Broadcast a message
            await manager.broadcast(screen_id, {"type": "update", "data": "test"})

            # New client connects, resyncs from sequence 0
            ws2 = MockWebSocket()
            await manager.resync(screen_id, ws2, 0)
            # Should receive the replayed message (if within history)
            assert len(ws2.messages) >= 1

        import asyncio
        asyncio.run(_run())

    def test_sequence_increments(self, manager: ConnectionManager, screen_id: str) -> None:
        async def _run() -> None:
            ws = MockWebSocket()
            await manager.register(screen_id, ws)
            ws.messages.clear()

            await manager.broadcast(screen_id, {"type": "msg1"})
            await manager.broadcast(screen_id, {"type": "msg2"})
            assert ws.messages[0]["sequence"] == 1
            assert ws.messages[1]["sequence"] == 2

        import asyncio
        asyncio.run(_run())

    def test_disconnect_removes_connection(self, manager: ConnectionManager, screen_id: str) -> None:
        async def _run() -> None:
            ws = MockWebSocket()
            await manager.register(screen_id, ws)
            assert manager.get_connections_count(screen_id) == 1
            await manager.disconnect(screen_id, ws)
            assert manager.get_connections_count(screen_id) == 0

        import asyncio
        asyncio.run(_run())

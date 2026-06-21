"""WebSocket streaming — unified /ws/stream endpoint with channel-based subscriptions.

Usage:
    from backend.app.api.ws.handler import ws_router, register_ws_routes
    from backend.app.api.ws.manager import ws_manager
"""

from backend.app.api.ws.manager import ws_manager

__all__ = [
    "ws_manager",
]

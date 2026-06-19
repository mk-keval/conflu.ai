"""Screener engine — multi-timeframe vectorized screening, filter pipeline, indicator cache, WebSocket streaming.

Usage:
    from backend.app.infrastructure.screener import ScreenEngine, list_filters
    engine = ScreenEngine()
    result = await engine.screen("trend-follower")
"""

from __future__ import annotations

from backend.app.infrastructure.screener.cache import IndicatorCache
from backend.app.infrastructure.screener.configs import load_screen_template, list_screen_templates
from backend.app.infrastructure.screener.engine import ScreenEngine
from backend.app.infrastructure.screener.filters import list_filters, list_filters_by_category
from backend.app.infrastructure.screener.streaming import ConnectionManager

__all__ = [
    "ScreenEngine",
    "IndicatorCache",
    "ConnectionManager",
    "list_filters",
    "list_filters_by_category",
    "list_screen_templates",
    "load_screen_template",
]

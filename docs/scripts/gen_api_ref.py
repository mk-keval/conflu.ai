"""Generate API reference pages from FastAPI OpenAPI spec."""
from __future__ import annotations

from pathlib import Path


def generate_api_reference() -> None:
    """Generate placeholder API reference pages for MkDocs.
    
    In production, this uses the running API's OpenAPI spec.
    """
    api_dir = Path("docs/api")
    api_dir.mkdir(parents=True, exist_ok=True)
    
    endpoints = {
        "health.md": "# Health\n\n## GET /health\nLiveness check.\n\n## GET /health/ready\nReadiness check with DuckDB connectivity.\n",
        "screener.md": "# Screener API\n\n## POST /api/v1/screen\nRun a multi-timeframe screener.\n\n## GET /api/v1/screens\nList saved screen configurations.\n\n## POST /api/v1/screens\nSave a screen configuration.\n",
        "backtest.md": "# Backtest API\n\n## POST /api/v1/backtest\nRun a new backtest.\n\n## POST /api/v1/backtest/optimize-v2\nRun parameter optimization.\n\n## POST /api/v1/backtest/compare\nCompare multiple backtest runs.\n",
        "data.md": "# Data API\n\n## GET /api/v1/data/{symbol}\nGet OHLCV data for a symbol.\n\n## GET /api/v1/indicators/{symbol}\nGet computed indicators for a symbol.\n",
        "risk.md": "# Risk API\n\n## GET /api/v1/risk/{symbol}/beta\nGet beta vs benchmark.\n\n## GET /api/v1/risk/{portfolio}/var\nGet VaR/CVaR.\n\n## POST /api/v1/risk/position-size\nCalculate position size.\n",
        "alerts.md": "# Alerts API\n\n## GET /api/v1/alerts\nList alerts.\n\n## POST /api/v1/alerts\nCreate an alert.\n\n## DELETE /api/v1/alerts/{alert_id}\nDelete an alert.\n",
        "streaming.md": "# WebSocket Streaming\n\n## WebSocket /api/v1/ws/stream\nReal-time price and indicator streaming.\n\n## WebSocket /api/v1/ws/screener/{screen_id}\nReal-time screener results.\n",
    }
    
    for filename, content in endpoints.items():
        (api_dir / filename).write_text(content)


if __name__ == "__main__":
    generate_api_reference()

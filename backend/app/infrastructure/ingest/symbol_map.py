"""Symbol resolution: internal ↔ TradingView ticker mapping."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

log = get_logger("conflu.ingest.symbol_map")


@dataclass
class AssetClassConfig:
    """Resolved configuration for one asset class."""

    name: str
    market: str
    default_exchange: str
    timezone: str
    symbols: list[str]


class TickerResolver:
    """Resolve internal symbols to TradingView tickers.

    Uses exchange_prefixes from config, with per-symbol overrides.
    """

    def __init__(self) -> None:
        self._build_asset_classes()

    def _build_asset_classes(self) -> None:
        """Build asset class configs from DataSettings."""
        ds = settings.data
        self._asset_classes: dict[str, AssetClassConfig] = {}

        for asset_class, symbols in ds.assets.items():
            market = ds.asset_class_markets.get(asset_class, "america")
            default_exchange = ds.exchange_prefixes.get(asset_class, "")
            timezone = ds.asset_class_timezones.get(asset_class, "UTC")
            self._asset_classes[asset_class] = AssetClassConfig(
                name=asset_class,
                market=market,
                default_exchange=default_exchange,
                timezone=timezone,
                symbols=list(symbols),
            )

    def refresh(self) -> None:
        """Rebuild asset classes from current config (useful if config changes at runtime)."""
        self._build_asset_classes()

    def get_exchange(self, symbol: str, asset_class: str) -> str:
        """Get exchange prefix for a symbol, checking overrides first."""
        overrides = settings.data.symbol_exchange_overrides
        if symbol in overrides:
            return overrides[symbol]
        cfg = self._asset_classes.get(asset_class)
        if cfg is None:
            log.warning("unknown_asset_class", asset_class=asset_class, symbol=symbol)
            return ""
        return cfg.default_exchange

    def to_tv_ticker(self, symbol: str, asset_class: str) -> str:
        """Convert internal symbol to TradingView ticker format.

        Returns: '{EXCHANGE}:{SYMBOL}' (e.g., 'NASDAQ:AAPL', 'BINANCE:BTCUSDT').
        """
        exchange = self.get_exchange(symbol, asset_class)
        return f"{exchange}{symbol}"

    def from_tv_ticker(self, tv_ticker: str) -> tuple[str, str]:
        """Parse a TV ticker into (exchange, symbol).

        Example: 'NASDAQ:AAPL' -> ('NASDAQ', 'AAPL')
        """
        if ":" in tv_ticker:
            parts = tv_ticker.split(":", 1)
            return (parts[0], parts[1])
        return ("", tv_ticker)

    def get_asset_classes(self) -> dict[str, AssetClassConfig]:
        """Return all configured asset classes."""
        return dict(self._asset_classes)

    def get_market_for_asset_class(self, asset_class: str) -> str:
        """Get the TradingView market name for an asset class."""
        cfg = self._asset_classes.get(asset_class)
        return cfg.market if cfg else "america"

    def get_timezone(self, asset_class: str) -> str:
        """Get the default timezone for an asset class."""
        cfg = self._asset_classes.get(asset_class)
        return cfg.timezone if cfg else "UTC"

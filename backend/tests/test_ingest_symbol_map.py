"""Tests for symbol mapping — TickerResolver."""

from __future__ import annotations

from backend.app.infrastructure.ingest.symbol_map import TickerResolver


def test_to_tv_ticker_default() -> None:
    """Default exchange for equities is NASDAQ:"""
    r = TickerResolver()
    assert r.to_tv_ticker("AAPL", "equities") == "NASDAQ:AAPL"


def test_to_tv_ticker_override() -> None:
    """SPY has an override to AMEX:"""
    r = TickerResolver()
    assert r.to_tv_ticker("SPY", "equities") == "AMEX:SPY"


def test_to_tv_ticker_crypto() -> None:
    """Crypto uses BINANCE: prefix."""
    r = TickerResolver()
    assert r.to_tv_ticker("BTCUSDT", "crypto") == "BINANCE:BTCUSDT"


def test_to_tv_ticker_forex() -> None:
    """Forex uses FX: prefix."""
    r = TickerResolver()
    assert r.to_tv_ticker("EURUSD", "forex") == "FX:EURUSD"


def test_to_tv_ticker_commodities() -> None:
    """Commodities use COMEX: prefix."""
    r = TickerResolver()
    assert r.to_tv_ticker("GC1!", "commodities") == "COMEX:GC1!"


def test_to_tv_ticker_indices() -> None:
    """Indices use SP: prefix."""
    r = TickerResolver()
    assert r.to_tv_ticker("SPX", "indices") == "SP:SPX"


def test_from_tv_ticker() -> None:
    """Parse TV ticker into (exchange, symbol)."""
    r = TickerResolver()
    assert r.from_tv_ticker("NASDAQ:AAPL") == ("NASDAQ", "AAPL")


def test_from_tv_ticker_no_exchange() -> None:
    """Ticker without exchange returns empty exchange string."""
    r = TickerResolver()
    assert r.from_tv_ticker("AAPL") == ("", "AAPL")


def test_get_market_for_asset_class() -> None:
    """Returns correct market per asset class."""
    r = TickerResolver()
    assert r.get_market_for_asset_class("equities") == "america"
    assert r.get_market_for_asset_class("crypto") == "crypto"
    assert r.get_market_for_asset_class("forex") == "forex"
    assert r.get_market_for_asset_class("commodities") == "futures"
    assert r.get_market_for_asset_class("indices") == "america"


def test_get_timezone() -> None:
    """Returns correct timezone per asset class."""
    r = TickerResolver()
    assert r.get_timezone("equities") == "America/New_York"
    assert r.get_timezone("crypto") == "UTC"
    assert r.get_timezone("forex") == "UTC"


def test_get_asset_classes() -> None:
    """get_asset_classes returns dict with all configured asset classes."""
    r = TickerResolver()
    acs = r.get_asset_classes()
    assert "equities" in acs
    assert "crypto" in acs
    assert "forex" in acs
    assert "commodities" in acs
    assert "indices" in acs
    assert len(acs["equities"].symbols) > 0


def test_get_exchange_override_priority() -> None:
    """get_exchange checks overrides before default."""
    r = TickerResolver()
    assert r.get_exchange("SPY", "equities") == "AMEX:"
    assert r.get_exchange("AAPL", "equities") == "NASDAQ:"


def test_refresh() -> None:
    """refresh() rebuilds from current config."""
    r = TickerResolver()
    before = r.get_asset_classes()
    r.refresh()
    after = r.get_asset_classes()
    assert before.keys() == after.keys()

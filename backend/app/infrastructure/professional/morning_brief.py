"""MorningBriefService — generates the daily morning brief for Professional Mode.

Pipeline:
1. Detect market regime (auto or override)
2. Select top 3 screens via RegimeScreenSelector
3. Run 3 screens in parallel via TVScreenEngine
4. Rank and format results per screen section
5. Fetch pre-market quotes for top tickers
6. Combine with market internals + sector rotation
7. Return MorningBriefResponse
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import yfinance as yf

from backend.app.core.logging import get_logger
from backend.app.infrastructure.professional.models import (
    MarketInternals,
    MorningBriefResponse,
    ScreenSection,
    SectorRotationSummary,
    TickerBrief,
)
from backend.app.infrastructure.professional.regime_selector import RegimeScreenSelector
from backend.app.infrastructure.screener.configs import ScreenConfig
from backend.app.infrastructure.screener.tv_engine import TVScreenEngine

log = get_logger("conflu.professional.morning_brief")

# ── Regime label mapping ──
_REGIME_LABEL_MAP: dict[str, str] = {
    "Exuberance": "strong_trend",
    "Risk-On": "strong_trend",
    "Neutral": "ranging",
    "Cautious": "ranging",
    "Risk-Off": "high_vol",
    "Crisis": "high_vol",
}

_DEFAULT_REGIME = "strong_trend"

_SECTOR_SYMBOLS: list[str] = [
    "XLF", "XLK", "XLV", "XLI", "XLB", "XLE",
    "XLU", "XLRE", "XLY", "XLP", "XLC",
]

_SECTOR_NAMES: dict[str, str] = {
    "XLF": "Financials",
    "XLK": "Technology",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLE": "Energy",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLY": "Consumer Cyclical",
    "XLP": "Consumer Staples",
    "XLC": "Communication Services",
}


class MorningBriefService:
    """Generates the daily morning brief with screens, sectors, and market internals."""

    def __init__(
        self,
        screen_engine: TVScreenEngine | None = None,
        regime_selector: RegimeScreenSelector | None = None,
    ) -> None:
        self._screen_engine = screen_engine or TVScreenEngine()
        self._regime_selector = regime_selector or RegimeScreenSelector()

    async def generate_morning_brief(
        self, regime_override: str | None = None
    ) -> MorningBriefResponse:
        start_time = time.monotonic()
        log.info("morning_brief_generation_started", regime_override=regime_override)

        # 1. Detect regime
        regime_key = _DEFAULT_REGIME
        regime_label = _DEFAULT_REGIME
        if regime_override:
            regime_key = regime_override
            regime_label = regime_override
        else:
            detected = _detect_regime()
            if detected:
                regime_label = detected
                regime_key = _REGIME_LABEL_MAP.get(detected, _DEFAULT_REGIME)

        regime_description = _regime_description(regime_label)
        log.info("regime_detected", label=regime_label, key=regime_key)

        # 2. Select top 3 screens
        screens = self._regime_selector.select_top_screens(regime_key)
        if not screens:
            screens = self._regime_selector.select_top_screens(_DEFAULT_REGIME)
        log.info("screens_selected", count=len(screens), names=[s.name for s in screens])

        # 3. Run screens in parallel
        screen_tasks = [self._screen_engine.screen(config) for config in screens]
        screen_results = await asyncio.gather(*screen_tasks, return_exceptions=True)

        # 4. Build screen sections
        screen_sections: list[ScreenSection] = []
        all_ticker_symbols: list[str] = []
        for config, result in zip(screens, screen_results):
            if isinstance(result, Exception):
                log.warning("screen_failed_skipping", screen=config.name, error=str(result))
                continue
            tickers = self._build_ticker_briefs(config.name, result)
            for t in tickers:
                all_ticker_symbols.append(t.symbol)
            regime_match = _compute_regime_match_score(config, regime_key)
            screen_sections.append(
                ScreenSection(
                    screen_name=config.name,
                    screen_label=config.description or config.name,
                    regime_match_score=regime_match,
                    tickers=tickers,
                )
            )

        # 5. Pre-market quotes for top 9 tickers
        premarket_symbols = list(dict.fromkeys(all_ticker_symbols))[:9]
        premarket_data = await _fetch_premarket_quotes(premarket_symbols)
        for section in screen_sections:
            for ticker in section.tickers:
                if ticker.symbol in premarket_data:
                    data = premarket_data[ticker.symbol]
                    ticker.live_price = data.get("live_price")
                    ticker.premarket_change_pct = data.get("premarket_change_pct")

        # 6. Market internals
        market_internals = await _fetch_market_internals()

        # 7. Sector rotation
        sector_rotation, sector_list = await _fetch_sector_rotation()

        # 8. Build response
        now_utc = datetime.now(UTC)
        brief = MorningBriefResponse(
            date=now_utc.date().isoformat(),
            regime=regime_label,
            regime_description=regime_description,
            market_internals=market_internals,
            sector_rotation=sector_rotation,
            sectors=sector_list,
            screen_sections=screen_sections,
            generated_at=now_utc.isoformat(),
        )
        elapsed = time.monotonic() - start_time
        log.info("morning_brief_generated", screens=len(screen_sections), tickers=len(all_ticker_symbols), elapsed_ms=round(elapsed * 1000))
        return brief

    def _build_ticker_briefs(self, screen_name: str, screen_result: dict[str, Any]) -> list[TickerBrief]:
        results = screen_result.get("results", [])
        briefs: list[TickerBrief] = []
        for r in results[:9]:
            confluence = r.get("confluence", {})
            elite = r.get("elite", {})
            rating = getattr(confluence, "rating", str(confluence.get("rating", "WATCH")))
            conviction_raw = elite.get("signal_conviction", "low")
            conviction_map = {"high": 8, "medium": 5, "low": 3}
            conviction = conviction_map.get(conviction_raw, 3)
            verdict = _rating_to_verdict(rating)
            education_hints = _build_education_hints(r.get("tv_data", {}))
            briefs.append(
                TickerBrief(
                    symbol=r.get("symbol", "UNKNOWN"),
                    screen_name=screen_name,
                    screen_score=float(r.get("score", 0)),
                    confluence_score=getattr(confluence, "total", confluence.get("total", 0)),
                    entry=float(getattr(confluence, "entry", confluence.get("entry", 0))),
                    stop_loss=float(getattr(confluence, "stop_loss", confluence.get("stop_loss", 0))),
                    targets=list(getattr(confluence, "targets", confluence.get("targets", []))),
                    verdict=verdict,
                    conviction=conviction,
                    education_hints=education_hints,
                )
            )
        return briefs


# ── Module-level helpers ──

def _detect_regime() -> str | None:
    try:
        from backend.app.api.routers.regime import get_market_regime_sync
        response = get_market_regime_sync()
        if response is not None:
            return response.regime_label
    except Exception:
        log.warning("market_regime_detection_failed", exc_info=True)
    return None


def _regime_description(label: str) -> str:
    descriptions: dict[str, str] = {
        "Exuberance": "Strong broad-market uptrend with high participation — ideal for aggressive positioning.",
        "Risk-On": "Positive market conditions with rising prices and healthy breadth.",
        "Neutral": "Mixed signals — no clear directional bias. Focus on stock-specific setups.",
        "Cautious": "Elevated uncertainty. Tighten stops and reduce position sizes.",
        "Risk-Off": "Defensive posture — capital preservation priority. Favor quality and low-beta names.",
        "Crisis": "Extreme market stress. Cash is a position. Consider hedging strategies.",
        "strong_trend": "Bullish trend conditions detected.",
        "ranging": "Range-bound market conditions.",
        "high_vol": "High volatility environment — wider stops required.",
    }
    return descriptions.get(label, f"Market regime: {label}")


def _rating_to_verdict(rating: str) -> str:
    mapping: dict[str, str] = {
        "STRONG_BUY": "STRONG_BUY", "BUY": "BUY", "ACCUMULATE": "BUY",
        "WATCH": "WATCH", "HOLD": "WATCH", "AVOID": "AVOID", "SELL": "AVOID",
    }
    return mapping.get(rating.upper(), "WATCH")


def _compute_regime_match_score(config: ScreenConfig, regime_key: str) -> float:
    _ = config
    return 1.0


def _build_education_hints(tv_data: dict[str, Any]) -> dict[str, str]:
    hints: dict[str, str] = {}
    rsi = tv_data.get("rsi_14")
    if rsi is not None:
        try:
            rsi_f = float(rsi)
            if rsi_f > 70:
                hints["rsi"] = "RSI suggests overbought — pullback possible."
            elif rsi_f < 30:
                hints["rsi"] = "RSI suggests oversold — bounce possible."
        except (ValueError, TypeError):
            pass
    pe = tv_data.get("earnings_per_share_diluted_ttm")
    price = tv_data.get("close")
    if pe is not None and price is not None:
        try:
            pe_ratio = float(price) / float(pe)
            if pe_ratio > 30:
                hints["pe_ratio"] = f"P/E at {pe_ratio:.0f}x — premium valuation."
            elif pe_ratio < 15:
                hints["pe_ratio"] = f"P/E at {pe_ratio:.0f}x — potentially undervalued."
        except (ValueError, ZeroDivisionError, TypeError):
            pass
    return hints


async def _fetch_premarket_quotes(symbols: list[str]) -> dict[str, dict[str, float | None]]:
    if not symbols:
        return {}
    result: dict[str, dict[str, float | None]] = {}
    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                t = tickers.tickers.get(sym)
                if t is None:
                    continue
                info = t.info if hasattr(t, "info") else {}
                regular_price = info.get("regularMarketPrice") or info.get("currentPrice")
                premarket_price = info.get("preMarketPrice")
                premarket_change = info.get("preMarketChangePercent")
                if premarket_price is not None and premarket_change is not None:
                    result[sym] = {"live_price": float(premarket_price), "premarket_change_pct": float(premarket_change)}
                elif regular_price is not None:
                    result[sym] = {"live_price": float(regular_price), "premarket_change_pct": None}
            except Exception:
                log.debug("premarket_fetch_failed", symbol=sym, exc_info=True)
                continue
    except Exception:
        log.warning("premarket_batch_fetch_failed", exc_info=True)
    return result


async def _fetch_market_internals() -> MarketInternals:
    internals = MarketInternals()
    try:
        vix = yf.Ticker("^VIX")
        vix_hist = vix.history(period="5d", interval="1d")
        if not vix_hist.empty:
            internals.vix = round(float(vix_hist["Close"].iloc[-1]), 2)
    except Exception:
        log.debug("vix_fetch_failed", exc_info=True)
    try:
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="5d", interval="1d")
        if not spy_hist.empty:
            internals.sp500_futures = round(float(spy_hist["Close"].iloc[-1]), 2)
    except Exception:
        log.debug("spy_fetch_failed", exc_info=True)
    try:
        qqq = yf.Ticker("QQQ")
        qqq_hist = qqq.history(period="5d", interval="1d")
        if not qqq_hist.empty:
            internals.nasdaq_futures = round(float(qqq_hist["Close"].iloc[-1]), 2)
    except Exception:
        log.debug("qqq_fetch_failed", exc_info=True)
    try:
        dxy = yf.Ticker("DX-Y.NYB")
        dxy_hist = dxy.history(period="5d", interval="1d")
        if not dxy_hist.empty:
            internals.dollar_index = round(float(dxy_hist["Close"].iloc[-1]), 2)
    except Exception:
        log.debug("dxy_fetch_failed", exc_info=True)
    try:
        adv, dec = 0, 0
        for sym in _SECTOR_SYMBOLS:
            try:
                t = yf.Ticker(sym)
                h = t.history(period="5d", interval="1d")
                if len(h) >= 2:
                    change = ((float(h["Close"].iloc[-1]) - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100
                    if change > 0:
                        adv += 1
                    elif change < 0:
                        dec += 1
            except Exception:
                continue
        if adv + dec > 0:
            internals.advance_decline_ratio = round(adv / max(dec, 1), 2)
    except Exception:
        log.debug("advance_decline_fetch_failed", exc_info=True)
    return internals


async def _fetch_sector_rotation() -> tuple[SectorRotationSummary, list[dict]]:
    sector_data: list[dict] = []
    changes_1d: dict[str, float] = {}
    for sym in _SECTOR_SYMBOLS:
        try:
            t = yf.Ticker(sym)
            h = t.history(period="1mo", interval="1d")
            if len(h) >= 2:
                cur = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2])
                changes_1d[sym] = round(((cur - prev) / prev) * 100, 2)
            else:
                changes_1d[sym] = 0.0
        except Exception:
            changes_1d[sym] = 0.0
            log.debug("sector_fetch_failed", symbol=sym, exc_info=True)
    sorted_by_change = sorted(changes_1d.items(), key=lambda x: x[1], reverse=True)
    rs_map: dict[str, int] = {}
    for rank, (sym, _) in enumerate(sorted_by_change, start=1):
        rs_map[sym] = rank
    for sym in _SECTOR_SYMBOLS:
        sector_data.append({
            "symbol": sym,
            "name": _SECTOR_NAMES.get(sym, sym),
            "change_pct": changes_1d.get(sym, 0.0),
            "rs_rank": rs_map.get(sym, 11),
        })
    leaders = [sym for sym, _ in sorted_by_change[:3]]
    laggards = [sym for sym, _ in sorted_by_change[-3:]]
    positive_count = sum(1 for v in changes_1d.values() if v > 0)
    total = len(changes_1d)
    if positive_count / max(total, 1) >= 0.6:
        regime_alignment = "risk_on"
    elif positive_count / max(total, 1) <= 0.3:
        regime_alignment = "risk_off"
    else:
        regime_alignment = "mixed"
    summary = SectorRotationSummary(leading_sectors=leaders, lagging_sectors=laggards, regime_alignment=regime_alignment)
    return summary, sector_data

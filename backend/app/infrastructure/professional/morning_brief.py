"""MorningBriefService — generates the daily morning brief for Professional Mode.

Pipeline:
1. Detect market regime (auto or override)
2. Select top 3 screens via RegimeScreenSelector
3. Fetch sector rotation → get #1 leading sector
4. Build 4th screen: best regime filters + sector_is filter targeting leading sector
5. Run all 4 screens in parallel via TVScreenEngine
6. Rank and format results per screen section
7. Fetch pre-market quotes for top tickers
8. Return MorningBriefResponse with sector rotation data included
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import yfinance as yf

from backend.app.core.logging import get_logger
from backend.app.infrastructure.professional.models import (
    MarketInternals,
    MorningBriefResponse,
    ScreenSection,
    SectorRotationSummary,
    TickerBrief,
)
from backend.app.infrastructure.screener.tv_models import ConfluenceScore
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

        # 2. Select top 3 screens (in-memory, instant)
        screens = self._regime_selector.select_top_screens(regime_key)
        if not screens:
            screens = self._regime_selector.select_top_screens(_DEFAULT_REGIME)
        log.info("screens_selected", count=len(screens), names=[s.name for s in screens])

        # 3. Fetch sector rotation early to get the leading sector for a 4th screen
        sector_rotation, sector_list, weekly_leader_etf = await _fetch_sector_rotation()

        # 4. Run the 3 regime screens in parallel
        screen_tasks = [self._screen_engine.screen(config) for config in screens]
        screen_results = await asyncio.gather(*screen_tasks, return_exceptions=True)

        # 5. Build screen sections from regime screens
        screen_sections: list[ScreenSection] = []
        all_ticker_symbols: list[str] = []
        for config, result in zip(screens, screen_results):
            if isinstance(result, Exception):
                log.warning("screen_failed_skipping", screen=config.name, error=str(result))
                continue
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
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

        # 6. Build 4th section from the weekly leader sector's actual ETF holdings
        # Uses yfinance to get holdings + scores them directly. Avoids TV Screener's
        # proprietary sector naming (which doesn't match GICS sector names).
        if weekly_leader_etf:
            try:
                etf_ticker = yf.Ticker(weekly_leader_etf)
                fd = etf_ticker.funds_data
                if fd and fd.top_holdings is not None and not fd.top_holdings.empty:
                    holdings = fd.top_holdings.index.tolist()[:15]
                    log.info("sector_screen_holdings_fetched", etf=weekly_leader_etf, count=len(holdings))
                    sector_briefs = await self._score_holdings(holdings)
                    if sector_briefs:
                        screen_sections.append(ScreenSection(
                            screen_name=f"Sector Rotation: {weekly_leader_etf}",
                            screen_label=f"Strong weekly momentum — {_SECTOR_NAMES.get(weekly_leader_etf, weekly_leader_etf)} is the leading sector this week",
                            regime_match_score=0.8,
                            tickers=sector_briefs[:3],
                        ))
                        for t in sector_briefs[:3]:
                            all_ticker_symbols.append(t.symbol)
                        log.info("sector_screen_section_added", etf=weekly_leader_etf, tickers=len(sector_briefs[:3]))
            except Exception:
                log.exception("sector_screen_failed", etf=weekly_leader_etf)

        # 7. Deduplicate tickers across sections so each section shows unique picks
        seen_symbols: set[str] = set()
        for section in screen_sections:
            unique_tickers: list[TickerBrief] = []
            for t in section.tickers:
                if t.symbol not in seen_symbols:
                    seen_symbols.add(t.symbol)
                    unique_tickers.append(t)
            section.tickers = unique_tickers[:9]

        # 8. Pre-market quotes for top 9 tickers
        all_ticker_symbols = list(seen_symbols)
        premarket_symbols = all_ticker_symbols[:9]
        premarket_data = await _fetch_premarket_quotes(premarket_symbols)
        for section in screen_sections:
            for ticker in section.tickers:
                if ticker.symbol in premarket_data:
                    data = premarket_data[ticker.symbol]
                    ticker.live_price = data.get("live_price")
                    ticker.premarket_change_pct = data.get("premarket_change_pct")

        # 8. Market internals
        market_internals = await _fetch_market_internals()

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
            confluence: ConfluenceScore | None = r.get("confluence")
            elite_vals: dict = r.get("elite") or {}
            if confluence is None:
                tv_data = r.get("tv_data", {})
                conviction = ({"high": 8, "medium": 5, "low": 3}).get(elite_vals.get("signal_conviction", "low"), 3)
                verdict = _rating_to_verdict(str(r.get("rating", "WATCH")))
                if verdict == "WATCH" and conviction >= 7:
                    verdict = "ACCUMULATE"
                briefs.append(
                    TickerBrief(
                        symbol=r.get("symbol", "UNKNOWN"),
                        screen_name=screen_name,
                        screen_score=float(r.get("score", 0)),
                        confluence_score=0,
                        entry=round(float(r.get("entry", 0)), 2),
                        stop_loss=round(float(r.get("stop_loss", 0)), 2),
                        targets=[round(float(t), 2) for t in r.get("targets", [])],
                        verdict=verdict,
                        conviction=conviction,
                        education_hints=_build_education_hints(tv_data) if tv_data else {},
                    )
                )
                continue
            elite_vals = r.get("elite") or {}
            conviction_raw = elite_vals.get("signal_conviction", "low")
            conviction_map = {"high": 8, "medium": 5, "low": 3}
            conviction = conviction_map.get(conviction_raw, 3)
            verdict = _rating_to_verdict(confluence.rating)
            # Upgrade WATCH → ACCUMULATE when conviction is high
            # (confluence scorer is conservative; high conviction overrides)
            if verdict == "WATCH" and conviction >= 7:
                verdict = "ACCUMULATE"
            education_hints = _build_education_hints(r.get("tv_data", {}))
            briefs.append(
                TickerBrief(
                    symbol=r.get("symbol", "UNKNOWN"),
                    screen_name=screen_name,
                    screen_score=float(r.get("score", 0)),
                    confluence_score=confluence.total,
                    entry=round(float(confluence.entry), 2),
                    stop_loss=round(float(confluence.stop_loss), 2),
                    targets=[round(float(t), 2) for t in confluence.targets],
                    verdict=verdict,
                    conviction=conviction,
                    education_hints=education_hints,
                )
            )
        return briefs

    async def _score_holdings(self, symbols: list[str]) -> list[TickerBrief]:
        """Score sector ETF holdings using yfinance data.
        
        This is used for the 4th sector rotation screen. Since TV Screener uses
        proprietary sector names that don't match GICS, we score the ETF's actual
        holdings directly from yfinance — ensuring the tickers shown are genuinely
        in the leading sector.
        """
        results: list[dict] = []
        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                h = ticker.history(period="2mo", interval="1d")
                if h.empty or len(h) < 10:
                    continue
                closes = [float(c) for c in h["Close"] if not pd.isna(c)]
                volumes = [float(v) for v in h["Volume"] if not pd.isna(v)]
                price = closes[-1]
                n = len(closes)

                # 50-day SMA
                sma50 = sum(closes[-min(50, n):]) / min(50, n) if n >= 1 else price
                # 20-day SMA
                sma20 = sum(closes[-min(20, n):]) / min(20, n) if n >= 1 else price

                # RSI(14)
                gains, losses = 0.0, 0.0
                rsi_period = min(14, n - 1)
                for i in range(n - rsi_period, n):
                    diff = closes[i] - closes[i - 1]
                    if diff > 0:
                        gains += diff
                    elif diff < 0:
                        losses -= diff
                avg_gain = gains / max(rsi_period, 1)
                avg_loss = losses / max(rsi_period, 1)
                rsi = 50.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / max(avg_loss, 0.001)))

                # Volume ratio (last 5d vs 30d avg)
                avg_vol_30 = sum(volumes[-30:]) / min(30, len(volumes)) if len(volumes) >= 1 else 1
                recent_vol = sum(volumes[-5:]) / min(5, len(volumes))
                vol_ratio = recent_vol / max(avg_vol_30, 1)

                # 1-week change
                change_1w = ((closes[-1] - closes[-6]) / max(closes[-6], 0.01)) * 100 if n >= 6 else 0

                # Composite score: weights designed for swing trading health
                score = 0.0
                if price > sma20 and sma20 > sma50:
                    score += 35  # Bullish MA alignment
                elif price > sma20:
                    score += 15
                if 45 <= rsi <= 75:
                    score += 25  # RSI sweet spot — not crashed, not exhausted
                elif rsi > 75:
                    score += 10  # Strong but extended
                elif rsi < 35:
                    score -= 10  # Weak momentum
                if vol_ratio > 1.0:
                    score += 15  # Healthy recent volume
                if change_1w > 2:
                    score += 15  # Positive weekly momentum
                elif change_1w > 0:
                    score += 5
                if sma20 > sma50:
                    score += 10  # Short-term trend above long-term

                score = max(0, min(100, score))
                stop_pct = (closes[-1] - min(closes[-10:])) / max(closes[-1], 0.01)
                stop_pct = max(0.02, min(0.08, stop_pct * 1.5))
                stop_loss = round(price * (1 - stop_pct), 2)
                target_1 = round(price * (1 + stop_pct * 2.0), 2)
                target_2 = round(price * (1 + stop_pct * 3.0), 2)

                verdict = "STRONG BUY" if score >= 70 else "BUY" if score >= 55 else "ACCUMULATE" if score >= 40 else "WATCH"
                conviction = min(10, max(1, int(score / 10)))

                results.append({
                    "symbol": sym, "score": score, "price": price,
                    "conviction": conviction, "verdict": verdict,
                    "entry": round(price, 2), "stop_loss": stop_loss,
                    "targets": [target_1, target_2],
                    "rsi": round(rsi, 1), "change_1w": round(change_1w, 1),
                })
            except Exception:
                continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return [
            TickerBrief(
                symbol=r["symbol"],
                screen_name=f"Sector Rotation Holdings",
                screen_score=r["score"] / 100,
                confluence_score=int(r["score"]),
                entry=r["entry"],
                stop_loss=r["stop_loss"],
                targets=r["targets"],
                verdict=r["verdict"],
                conviction=r["conviction"],
                live_price=r["price"],
                premarket_change_pct=None,
                education_hints={"rsi": str(r["rsi"]), "change_1w": f"{r['change_1w']}%"},
            )
            for r in results[:5]
        ]


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
        spy = yf.Ticker("^GSPC")  # S&P 500 index (not SPY ETF — index level is what non-experts expect)
        spy_hist = spy.history(period="5d", interval="1d")
        if not spy_hist.empty:
            internals.sp500_futures = round(float(spy_hist["Close"].iloc[-1]), 2)
    except Exception:
        log.debug("spy_fetch_failed", exc_info=True)
    try:
        qqq = yf.Ticker("^IXIC")  # Nasdaq Composite index (not QQQ ETF)
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


async def _fetch_sector_rotation() -> tuple[SectorRotationSummary, list[dict], str | None]:
    """Fetch sector data and return (summary, sector_list, weekly_leader_etf).

    Returns the weekly leader separately for swing trading use — 1W relative
    strength is more relevant than 1D noise for multi-day holds.
    """
    sector_data: list[dict] = []
    changes_1d: dict[str, float] = {}
    changes_1w: dict[str, float] = {}
    for sym in _SECTOR_SYMBOLS:
        try:
            t = yf.Ticker(sym)
            h = t.history(period="1mo", interval="1d")
            closes = [float(c) for c in h["Close"] if not pd.isna(c)] if not h.empty else []
            if len(closes) >= 2:
                changes_1d[sym] = round(((closes[-1] - closes[-2]) / closes[-2]) * 100, 2)
            else:
                changes_1d[sym] = 0.0
            if len(closes) >= 6:
                changes_1w[sym] = round(((closes[-1] - closes[-6]) / closes[-6]) * 100, 2)
            else:
                changes_1w[sym] = 0.0
        except Exception:
            changes_1d[sym] = 0.0
            changes_1w[sym] = 0.0
            log.debug("sector_fetch_failed", symbol=sym, exc_info=True)
    sorted_by_change = sorted(changes_1d.items(), key=lambda x: x[1], reverse=True)
    sorted_weekly = sorted(changes_1w.items(), key=lambda x: x[1], reverse=True)
    rs_map: dict[str, int] = {}
    for rank, (sym, _) in enumerate(sorted_by_change, start=1):
        rs_map[sym] = rank
    for sym in _SECTOR_SYMBOLS:
        sector_data.append({
            "symbol": sym,
            "name": _SECTOR_NAMES.get(sym, sym),
            "change_pct": changes_1d.get(sym, 0.0),
            "change_1w_pct": changes_1w.get(sym, 0.0),
            "rs_rank": rs_map.get(sym, 11),
        })
    leaders = [sym for sym, _ in sorted_by_change[:3]]
    laggards = [sym for sym, _ in sorted_by_change[-3:]]
    weekly_leader = sorted_weekly[0][0] if sorted_weekly else None
    positive_count = sum(1 for v in changes_1d.values() if v > 0)
    total = len(changes_1d)
    if positive_count / max(total, 1) >= 0.6:
        regime_alignment = "risk_on"
    elif positive_count / max(total, 1) <= 0.3:
        regime_alignment = "risk_off"
    else:
        regime_alignment = "mixed"
    summary = SectorRotationSummary(leading_sectors=leaders, lagging_sectors=laggards, regime_alignment=regime_alignment)
    return summary, sector_data, weekly_leader

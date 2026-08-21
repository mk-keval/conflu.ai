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

# Max concurrent yfinance holdings fetches for the 4th sector screen.
# Bounded low enough to avoid tripping yfinance rate limits while still
# parallelizing the previously-serial ~15 calls.
_HOLDING_CONCURRENCY: int = 4

# Max concurrent yfinance sector fetches for sector rotation / A-D breadth.
_SECTOR_CONCURRENCY: int = 4

# ── Brief cache ──
# The morning brief is a daily artifact. Regenerating it on every page load
# fires ~50 blocking yfinance/TV calls, which stalls the page and the event
# loop. Cache the last generated brief with a TTL so repeated page loads reuse
# one generation instead of fanning out the full pipeline each time.
_BRIEF_CACHE_TTL: float = 6 * 60 * 60  # 6h — covers pre-market through close

# ── Regime label mapping ──
# "neutral" and "choppy" are first-class config regimes (P1.1): a mid-range
# composite is NOT a reason to serve only defensive screens — the weighted
# config in config/regime_screens.yaml keeps momentum/breakout primary.
_REGIME_LABEL_MAP: dict[str, str] = {
    "Exuberance": "strong_trend",
    "Risk-On": "strong_trend",
    "Neutral": "neutral",
    "Cautious": "choppy",
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
        # TTL cache for the generated brief (see _BRIEF_CACHE_TTL above)
        self._cached_brief: MorningBriefResponse | None = None
        self._cached_at: float = 0.0
        self._cache_lock = asyncio.Lock()

    async def generate_morning_brief(
        self, regime_override: str | None = None, force: bool = False
    ) -> MorningBriefResponse:
        # Serialize the whole check+generate+cache cycle under one lock so
        # concurrent page loads share a single cold generation instead of each
        # fanning out ~50 external calls (D-31's cache intent). asyncio.Lock
        # yields at every await (the pipeline offloads to asyncio.to_thread), so
        # the event loop stays responsive for other requests during generation.
        async with self._cache_lock:
            return await self._generate(regime_override=regime_override, force=force)

    async def _generate(
        self, regime_override: str | None = None, force: bool = False
    ) -> MorningBriefResponse:
        start_time = time.monotonic()

        # Serve from cache when fresh (and no regime override requested).
        if not force and regime_override is None:
            if self._cached_brief is not None:
                age = time.monotonic() - self._cached_at
                if age < _BRIEF_CACHE_TTL:
                    log.info(
                        "morning_brief_cache_hit",
                        age_ms=round(age * 1000),
                        cached_at=self._cached_at,
                    )
                    return self._cached_brief

        log.info("morning_brief_generation_started", regime_override=regime_override, force=force)

        # 1. Detect regime
        regime_key = _DEFAULT_REGIME
        regime_label = _DEFAULT_REGIME
        if regime_override:
            regime_key = regime_override
            regime_label = regime_override
        else:
            detected = await asyncio.to_thread(_detect_regime)
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

        # 4. Run the regime screens — batched when One-Snapshot-Multi-Screen
        # is enabled (one upstream TV call + local masking), else parallel
        # per-template discovery. screen_batch returns the same per-screen
        # dicts (or Exception objects) that the legacy gather produces.
        if hasattr(self._screen_engine, "screen_batch"):
            raw_results = await self._screen_engine.screen_batch(screens)
            screen_results: list[Any] = []
            for config, result in zip(screens, raw_results):
                if isinstance(result, Exception):
                    screen_results.append(result)
                elif isinstance(result, dict):
                    screen_results.append(result)
                else:
                    log.warning("unexpected_batch_result_type", type=type(result).__name__)
                    screen_results.append(RuntimeError(f"bad result for {config.name}"))
        else:
            screen_tasks = [self._screen_engine.screen(config) for config in screens]
            screen_results = list(await asyncio.gather(*screen_tasks, return_exceptions=True))

        # 5. Build screen sections from regime screens
        screen_sections: list[ScreenSection] = []
        all_ticker_symbols: list[str] = []
        # P1.4: TV snapshot rows per symbol — the badge is evaluated once,
        # in the quote-attach pass, where EPS surprise data also exists.
        tv_data_by_symbol: dict[str, dict[str, Any]] = {}
        for config, result in zip(screens, screen_results):
            if isinstance(result, Exception):
                log.warning("screen_failed_skipping", screen=config.name, error=str(result))
                continue
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            for item in result.get("results", []):
                sym = item.get("symbol")
                tv_row = item.get("tv_data")
                if sym and isinstance(tv_row, dict) and sym not in tv_data_by_symbol:
                    tv_data_by_symbol[sym] = tv_row
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
                # yfinance is blocking — fetch ETF holdings off the event loop
                # (same asyncio.to_thread discipline as every other external
                # call in this pipeline; this one was previously on-loop).
                holdings = await asyncio.to_thread(_etf_top_holdings, weekly_leader_etf)
                if holdings:
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
                    # P1.4: single evaluation point — TV structural data from
                    # the snapshot + EPS surprise that rode along on the same
                    # yfinance .info payload as the premarket quote.
                    eps = data.get("earnings_surprise_pct")
                    cat_on, cat_reason = _catalyst_breakout_state(
                        tv_data_by_symbol.get(ticker.symbol, {}), eps
                    )
                    ticker.catalyst_breakout = cat_on
                    ticker.catalyst_breakout_reason = cat_reason

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

        # Store the freshly generated brief in cache (the caller holds the lock
        # for the whole check+generate cycle, so no inner lock is needed here).
        self._cached_brief = brief
        self._cached_at = time.monotonic()

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
                    # Screen results carry no "score" key — the real score is
                    # confluence.total (0-100); normalize to 0-1 (bug B7).
                    screen_score=float(confluence.total) / 100.0,
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

        yfinance is a blocking/synchronous library. Each per-symbol scoring runs
        inside asyncio.to_thread (so it doesn't freeze the event loop) and up to
        `_HOLDING_CONCURRENCY` of them run at once (instead of 15 serial network
        round-trips), which keeps cold-cache generation fast and responsive.
        """
        if not symbols:
            return []

        semaphore = asyncio.Semaphore(_HOLDING_CONCURRENCY)

        async def _score_one(sym: str) -> dict | None:
            async with semaphore:
                return await asyncio.to_thread(_score_holding_sync, sym)

        scored = await asyncio.gather(
            *(_score_one(sym) for sym in symbols),
            return_exceptions=True,
        )

        results: list[dict] = [
            r for r in scored if isinstance(r, dict)
        ]
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

def _etf_top_holdings(etf: str) -> list[str]:
    """Fetch the top holdings of a sector ETF via yfinance (blocking; run in a thread).

    Returns up to 15 symbols, or [] if the fund data is unavailable.
    """
    try:
        fd = yf.Ticker(etf).funds_data
        if fd is None or fd.top_holdings is None or fd.top_holdings.empty:
            return []
        return fd.top_holdings.index.tolist()[:15]
    except Exception:
        log.exception("etf_top_holdings_failed", etf=etf)
        return []


def _score_holding_sync(sym: str) -> dict | None:
    """Score a single sector-ETF holding from yfinance (blocking, runs in a thread).

    Returns a dict with scoring metadata, or None if the symbol has no usable
    history. Extracted from the old sequential loop so _score_holdings can run
    each symbol in asyncio.to_thread with bounded concurrency.
    """
    try:
        ticker = yf.Ticker(sym)
        h = ticker.history(period="2mo", interval="1d")
        if h.empty or len(h) < 10:
            return None
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

        return {
            "symbol": sym, "score": score, "price": price,
            "conviction": conviction, "verdict": verdict,
            "entry": round(price, 2), "stop_loss": stop_loss,
            "targets": [target_1, target_2],
            "rsi": round(rsi, 1), "change_1w": round(change_1w, 1),
        }
    except Exception:
        return None


def _sector_changes_sync(sym: str) -> tuple[float, float]:
    """Fetch 1D and 1W % change for a sector ETF (blocking, runs in a thread).

    Returns (change_1d, change_1w). Tolerates empty/failed history by returning
    (0.0, 0.0).
    """
    try:
        t = yf.Ticker(sym)
        h = t.history(period="1mo", interval="1d")
        closes = [float(c) for c in h["Close"] if not pd.isna(c)] if not h.empty else []
        chg_1d = round(((closes[-1] - closes[-2]) / closes[-2]) * 100, 2) if len(closes) >= 2 else 0.0
        chg_1w = round(((closes[-1] - closes[-6]) / closes[-6]) * 100, 2) if len(closes) >= 6 else 0.0
        return chg_1d, chg_1w
    except Exception:
        log.debug("sector_fetch_failed", symbol=sym, exc_info=True)
        return 0.0, 0.0


def _sector_direction_sync(sym: str) -> int:
    """Return +1/0/-1 for a sector ETF's last close direction (blocking, thread).

    Used for advance/decline breadth. Tolerates failed history by returning 0.
    """
    try:
        t = yf.Ticker(sym)
        h = t.history(period="5d", interval="1d")
        if len(h) >= 2:
            change = ((float(h["Close"].iloc[-1]) - float(h["Close"].iloc[-2])) / float(h["Close"].iloc[-2])) * 100
            if change > 0:
                return 1
            if change < 0:
                return -1
        return 0
    except Exception:
        return 0


def _index_last_close_sync(sym: str) -> float | None:
    """Fetch the latest close for an index symbol (blocking, runs in a thread)."""
    try:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="5d", interval="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        log.debug("index_fetch_failed", symbol=sym, exc_info=True)
    return None


def _detect_regime() -> str | None:
    try:
        from backend.app.infrastructure.market.regime import get_market_regime_sync
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
        "neutral": "Mixed signals — stock-specific momentum/breakout setups primary, one defensive hedge.",
        "choppy": "Choppy tape — smaller size, favor volume-confirmed breakouts.",
    }
    return descriptions.get(label, f"Market regime: {label}")


def _rating_to_verdict(rating: str) -> str:
    mapping: dict[str, str] = {
        "STRONG_BUY": "STRONG_BUY", "BUY": "BUY", "ACCUMULATE": "BUY",
        "WATCH": "WATCH", "HOLD": "WATCH", "AVOID": "AVOID", "SELL": "AVOID",
        # TVConfluenceScorer emits letter ratings (A+/A/B+/B/C/D), which were
        # previously unmapped and always fell through to WATCH (bug B6).
        "A+": "STRONG_BUY", "A": "BUY", "B+": "ACCUMULATE",
        "B": "WATCH", "C": "HOLD", "D": "AVOID",
    }
    return mapping.get(rating.upper(), "WATCH")


def _compute_regime_match_score(config: ScreenConfig, regime_key: str) -> float:
    _ = config
    return 1.0


# ── Catalyst-Breakout badge (P1.4) ──
# Veteran logic: a real catalyst setup = fresh EPS beat + volume expansion
# (rvol > 1.2) + price pressing against the 52-week high (within 3%).
_CATALYST_RVOL_MIN = 1.2
_CATALYST_HIGH_PROXIMITY = 0.97  # close >= 97% of the 52-week high


def _catalyst_breakout_state(
    tv_data: dict[str, Any],
    eps_surprise_pct: float | None,
) -> tuple[bool, str | None]:
    """Evaluate the Catalyst-Breakout badge for one candidate.

    Returns (badge_on, reason). Structural conditions come from TV snapshot
    columns (rvol, close vs 52-week high); the EPS-beat confirmation comes
    from yfinance info already fetched for premarket quotes. When any
    component is unknown the badge stays off — we never claim a catalyst we
    can't see.
    """
    if not tv_data:
        return False, None

    def _num(key: str) -> float | None:
        try:
            value = tv_data.get(key)
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    rvol = _num("relative_volume_10d_calc")
    close = _num("close")
    high_52w = _num("price_52_week_high")

    rvol_ok = rvol is not None and rvol > _CATALYST_RVOL_MIN
    near_high_ok = (
        close is not None
        and high_52w is not None
        and high_52w > 0
        and close >= high_52w * _CATALYST_HIGH_PROXIMITY
    )
    eps_ok = eps_surprise_pct is not None and eps_surprise_pct > 0

    if not (rvol_ok and near_high_ok and eps_ok):
        return False, None

    parts: list[str] = []
    if close is not None and high_52w is not None and high_52w > 0:
        pct_below = (1.0 - close / high_52w) * 100.0
        parts.append(f"within {pct_below:.1f}% of 52-week high")
    if rvol is not None:
        parts.append(f"rvol {rvol:.1f}x")
    if eps_surprise_pct is not None:
        parts.append(f"EPS beat +{eps_surprise_pct:.1f}%")

    return True, "Catalyst breakout: " + ", ".join(parts)


def _build_education_hints(tv_data: dict[str, Any]) -> dict[str, str]:
    hints: dict[str, str] = {}
    rsi = tv_data.get("RSI")
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
    # yfinance .info access is blocking; run the whole batch in a thread so it
    # doesn't freeze the event loop during the (now rare) cold generation.
    result = await asyncio.to_thread(_premarket_quotes_sync, symbols)
    return result


def _premarket_quotes_sync(symbols: list[str]) -> dict[str, dict[str, float | None]]:
    """Fetch pre-market/regular quotes for a batch of symbols (blocking, thread).

    Also extracts the last EPS surprise from the same .info payload so the
    Catalyst-Breakout badge (P1.4) needs zero extra upstream calls.
    """
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
                eps_surprise: float | None = None
                raw_surprise = info.get("earningsSurprisePct")
                if isinstance(raw_surprise, (int, float)):
                    eps_surprise = float(raw_surprise)
                payload: dict[str, float | None] = {
                    "live_price": None,
                    "premarket_change_pct": None,
                    "earnings_surprise_pct": eps_surprise,
                }
                if premarket_price is not None and premarket_change is not None:
                    payload["live_price"] = float(premarket_price)
                    payload["premarket_change_pct"] = float(premarket_change)
                elif regular_price is not None:
                    payload["live_price"] = float(regular_price)
                result[sym] = payload
            except Exception:
                log.debug("premarket_fetch_failed", symbol=sym, exc_info=True)
                continue
    except Exception:
        log.warning("premarket_batch_fetch_failed", exc_info=True)
    return result


async def _fetch_market_internals() -> MarketInternals:
    internals = MarketInternals()

    # Index snapshots (blocking yfinance) run in threads — 4 parallel instead
    # of serial on the event loop.
    async def _snapshot(sym: str) -> float | None:
        return await asyncio.to_thread(_index_last_close_sync, sym)

    vix_val, spy_val, qqq_val, dxy_val = await asyncio.gather(
        _snapshot("^VIX"),
        _snapshot("^GSPC"),  # S&P 500 index (index level is what non-experts expect)
        _snapshot("^IXIC"),  # Nasdaq Composite index
        _snapshot("DX-Y.NYB"),
    )

    if vix_val is not None:
        internals.vix = round(vix_val, 2)
    if spy_val is not None:
        internals.sp500_futures = round(spy_val, 2)
    if qqq_val is not None:
        internals.nasdaq_futures = round(qqq_val, 2)
    if dxy_val is not None:
        internals.dollar_index = round(dxy_val, 2)

    # Advance/decline breadth — sector changes in threads, bounded concurrency.
    semaphore = asyncio.Semaphore(_SECTOR_CONCURRENCY)

    async def _adv_dec(sym: str) -> int:
        async with semaphore:
            return await asyncio.to_thread(_sector_direction_sync, sym)

    directions = await asyncio.gather(*(_adv_dec(sym) for sym in _SECTOR_SYMBOLS))
    adv = sum(1 for d in directions if d > 0)
    dec = sum(1 for d in directions if d < 0)
    if adv + dec > 0:
        internals.advance_decline_ratio = round(adv / max(dec, 1), 2)
    return internals


async def _fetch_sector_rotation() -> tuple[SectorRotationSummary, list[dict], str | None]:
    """Fetch sector data and return (summary, sector_list, weekly_leader_etf).

    Returns the weekly leader separately for swing trading use — 1W relative
    strength is more relevant than 1D noise for multi-day holds.

    Each sector's yfinance history fetch is blocking, so they run in threads
    with bounded concurrency instead of 11 serial round-trips on the event loop.
    """
    semaphore = asyncio.Semaphore(_SECTOR_CONCURRENCY)

    async def _fetch_one(sym: str) -> tuple[str, float, float]:
        async with semaphore:
            chg_1d, chg_1w = await asyncio.to_thread(_sector_changes_sync, sym)
            return sym, chg_1d, chg_1w

    fetched = await asyncio.gather(*(_fetch_one(sym) for sym in _SECTOR_SYMBOLS))

    changes_1d: dict[str, float] = {}
    changes_1w: dict[str, float] = {}
    for sym, change_1d, change_1w in fetched:
        changes_1d[sym] = change_1d
        changes_1w[sym] = change_1w

    sorted_by_change = sorted(changes_1d.items(), key=lambda x: x[1], reverse=True)
    sorted_weekly = sorted(changes_1w.items(), key=lambda x: x[1], reverse=True)
    rs_map: dict[str, int] = {}
    for rank, (sym, _) in enumerate(sorted_by_change, start=1):
        rs_map[sym] = rank
    sector_data = [
        {
            "symbol": sym,
            "name": _SECTOR_NAMES.get(sym, sym),
            "change_pct": changes_1d.get(sym, 0.0),
            "change_1w_pct": changes_1w.get(sym, 0.0),
            "rs_rank": rs_map.get(sym, 11),
        }
        for sym in _SECTOR_SYMBOLS
    ]
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

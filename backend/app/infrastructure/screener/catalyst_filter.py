"""Catalyst post-filter for the screener (D-47 PR 1).

The TradingView screener finds stocks that match technical patterns.
This module runs the 5 catalyst signals (D-46) on each TV-screener
result and surfaces them as a `catalyst_signals` dict. The elite
trader doesn't take a trade unless multiple signals align — a stock
that's in a leading sector AND just reported a beat AND has insider
buying is a much stronger setup than a stock that just has a
bullish chart pattern.

This is the discovery layer: confluence = multiple catalysts firing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import yfinance as yf

from backend.app.infrastructure.professional.macro_context import (
    sector_to_etf,
    _fetch_sector_etf_history,
    _window_return,
    _SECTOR_CACHE_TTL,
)
from backend.app.infrastructure.analyst_revisions import get_revision
from backend.app.infrastructure.insider_cluster import detect_insider_cluster
from backend.app.infrastructure.options_flow import detect_unusual_options_activity

log = logging.getLogger(__name__)


@dataclass
class CatalystSignals:
    """All 5 catalyst signals for a single ticker."""
    symbol: str
    # Sector-relative RS (from D-46 PR 2)
    sector_etf: str | None = None
    rs_vs_sector_1m_pct: float | None = None
    outperforming_sector: bool = False
    # Post-earnings drift (from D-46 PR 3 — needs yesterday's snapshot)
    has_post_earnings_drift: bool = False
    days_since_last_earnings: int | None = None
    last_beat_pct: float | None = None
    # Analyst revision (from D-46 PR 3)
    analyst_target_upgrade_5d_pct: float | None = None
    analyst_upgraded: bool = False
    # Insider cluster (from D-46 PR 4)
    insider_cluster_detected: bool = False
    insider_cluster_size: int = 0
    # Options flow (from D-46 PR 5)
    options_flow_bias: str | None = None  # "bullish" / "bearish" / None
    call_put_volume_ratio: float | None = None
    # Confluence score: how many signals are firing
    confluence_count: int = 0
    # Human-readable summary
    summary: str = ""
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "sector_etf": self.sector_etf,
            "rs_vs_sector_1m_pct": self.rs_vs_sector_1m_pct,
            "outperforming_sector": self.outperforming_sector,
            "has_post_earnings_drift": self.has_post_earnings_drift,
            "days_since_last_earnings": self.days_since_last_earnings,
            "last_beat_pct": self.last_beat_pct,
            "analyst_target_upgrade_5d_pct": self.analyst_target_upgrade_5d_pct,
            "analyst_upgraded": self.analyst_upgraded,
            "insider_cluster_detected": self.insider_cluster_detected,
            "insider_cluster_size": self.insider_cluster_size,
            "options_flow_bias": self.options_flow_bias,
            "call_put_volume_ratio": self.call_put_volume_ratio,
            "confluence_count": self.confluence_count,
            "summary": self.summary,
            "findings": self.findings,
        }


def _get_sector(symbol: str) -> str | None:
    """Pull sector from yfinance."""
    try:
        return yf.Ticker(symbol).info.get("sector")
    except Exception:
        return None


def _get_days_since_earnings(symbol: str) -> tuple[int | None, float | None]:
    """Return (days_since_last_earnings, last_beat_pct) from yfinance.

    Returns (None, None) if data unavailable.
    """
    try:
        y = yf.Ticker(symbol)
        # earnings_dates is a DataFrame indexed by date with EPS estimate/actual
        ed = y.earnings_dates
        if ed is None or ed.empty:
            return None, None
        # Find the most recent past earnings date
        import datetime as _dt
        today = _dt.date.today()
        past = ed[ed.index.date < today]
        if past.empty:
            return None, None
        latest = past.index[-1]
        days_since = (today - latest.date()).days
        # Try to get the surprise %
        actual = ed.loc[latest, "Reported EPS"] if "Reported EPS" in ed.columns else None
        estimate = ed.loc[latest, "EPS Estimate"] if "EPS Estimate" in ed.columns else None
        beat_pct = None
        if actual is not None and estimate is not None and estimate != 0:
            beat_pct = round((float(actual) - float(estimate)) / abs(float(estimate)) * 100, 2)
        return days_since, beat_pct
    except Exception:
        return None, None


def detect_catalyst_signals(
    symbol: str,
    sector: str | None = None,
    stock_history: Any = None,
) -> CatalystSignals:
    """Run all 5 catalyst detectors on a ticker. Returns a populated
    CatalystSignals object (signals that don't fire will be False/None).

    `sector` and `stock_history` are optional optimizations — if the
    caller already has them, we save an extra yfinance call.
    """
    signals = CatalystSignals(symbol=symbol)

    # 1. Sector-relative RS
    try:
        sector_name = sector or _get_sector(symbol)
        signals.sector_etf = sector_to_etf(sector_name)
        if signals.sector_etf and stock_history is not None and len(stock_history) >= 22:
            sector_hist = _fetch_sector_etf_history(signals.sector_etf)
            if sector_hist is not None and len(sector_hist) >= 22:
                stock_1m = _window_return(stock_history, 21)
                sector_1m = _window_return(sector_hist, 21)
                if stock_1m is not None and sector_1m is not None:
                    rs = round(stock_1m - sector_1m, 2)
                    signals.rs_vs_sector_1m_pct = rs
                    signals.outperforming_sector = rs >= 5.0
                    if signals.outperforming_sector:
                        signals.findings.append(
                            f"📈 Sector RS: outperforming {signals.sector_etf} by {rs:+.1f}% over 1M"
                        )
                        signals.confluence_count += 1
    except Exception:
        log.exception("sector_rs_failed", extra={"symbol": symbol})

    # 2. Post-earnings drift
    try:
        days_since, beat_pct = _get_days_since_earnings(symbol)
        if days_since is not None and 0 <= days_since <= 20:
            signals.has_post_earnings_drift = True
            signals.days_since_last_earnings = days_since
            signals.last_beat_pct = beat_pct
            if beat_pct is not None and beat_pct > 0:
                signals.findings.append(
                    f"📈 Post-earnings drift: {days_since}d since print, beat by {beat_pct:+.1f}%"
                )
                signals.confluence_count += 1
    except Exception:
        log.exception("post_earnings_drift_failed", extra={"symbol": symbol})

    # 3. Analyst revision
    try:
        rev = get_revision(symbol, window_days=5)
        if rev is not None and rev.change_pct is not None:
            signals.analyst_target_upgrade_5d_pct = rev.change_pct
            signals.analyst_upgraded = rev.change_pct >= 5.0
            if signals.analyst_upgraded:
                signals.findings.append(
                    f"📈 Analyst upgrade: target raised by {rev.change_pct:+.1f}% over 5d"
                )
                signals.confluence_count += 1
    except Exception:
        log.exception("analyst_revision_failed", extra={"symbol": symbol})

    # 4. Insider cluster
    try:
        cluster = detect_insider_cluster(symbol)
        if cluster is not None:
            signals.insider_cluster_detected = True
            signals.insider_cluster_size = cluster.num_buyers
            signals.findings.append(
                f"🟢 Insider cluster: {cluster.num_buyers} insiders bought same week (${cluster.total_value_usd:,.0f})"
            )
            signals.confluence_count += 1
    except Exception:
        log.exception("insider_cluster_failed", extra={"symbol": symbol})

    # 5. Options flow
    try:
        flow = detect_unusual_options_activity(symbol)
        if flow is not None:
            signals.options_flow_bias = flow.bias
            signals.call_put_volume_ratio = flow.call_put_volume_ratio
            if flow.bias == "bullish":
                signals.findings.append(
                    f"📈 Unusual call activity: call/put ratio {flow.call_put_volume_ratio:.1f}x"
                )
                signals.confluence_count += 1
            elif flow.bias == "bearish":
                signals.findings.append(
                    f"📉 Unusual put activity: call/put ratio {flow.call_put_volume_ratio:.1f}x"
                )
    except Exception:
        log.exception("options_flow_failed", extra={"symbol": symbol})

    # Build summary
    if signals.confluence_count >= 3:
        signals.summary = f"🔥 HIGH CONFLUENCE: {signals.confluence_count}/5 catalysts firing"
    elif signals.confluence_count >= 2:
        signals.summary = f"✅ MODERATE CONFLUENCE: {signals.confluence_count}/5 catalysts firing"
    elif signals.confluence_count >= 1:
        signals.summary = f"○ Weak signal: {signals.confluence_count}/5 catalyst firing"
    else:
        signals.summary = "○ No catalyst signals"

    return signals


def confluence_boost(catalyst_signals: CatalystSignals) -> int:
    """Return a score boost to add to the screener score based on confluence.

    +0 per catalyst (max +5). The elite trader treats confluence as the
    primary trade trigger — 3+ catalysts firing is a much stronger signal
    than 1 catalyst.

    This boost is a tie-breaker, not the primary signal. A stock with
    score 90 and 0 catalysts is less interesting than a stock with
    score 80 and 3 catalysts.
    """
    return min(catalyst_signals.confluence_count, 5)

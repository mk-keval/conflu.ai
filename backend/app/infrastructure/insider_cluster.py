"""Insider cluster detector (D-46 PR 4).

The elite trader watches for cluster insider buying — when 3+ insiders
buy the same ticker in the same week. That's the strongest insider
signal (CEO buying 4x in a month, like KURA's CEO Troy Wilson, is
the elite trader's #1 reason to look at a name).

This module reads yfinance's insider_transactions DataFrame, filters
to buys in the last 30 days, groups by week, and surfaces a finding
when any week has >= MIN_INSIDERS_FOR_CLUSTER buys.

The cluster finding is wired into the sentiment module so the user
sees it on the verdict.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

# Detection thresholds
MIN_INSIDERS_FOR_CLUSTER = 3  # 3+ insiders buying same week = cluster
LOOKBACK_DAYS = 30  # how far back to look
MIN_CLUSTER_VALUE_USD = 100_000  # ignore small insider buys (likely 10b5-1 plan)

# Text patterns (yfinance encodes transaction type in the free-text Text column)
_BUY_PATTERNS = re.compile(r"purchase at price|buy at price", re.IGNORECASE)
_SELL_PATTERNS = re.compile(r"sale at price|sold at price", re.IGNORECASE)


@dataclass
class InsiderCluster:
    """A detected cluster of insider buying."""
    symbol: str
    week_starting: _dt.date
    num_buyers: int
    num_buy_transactions: int
    total_value_usd: float
    insiders: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "week_starting": self.week_starting.isoformat(),
            "num_buyers": self.num_buyers,
            "num_buy_transactions": self.num_buy_transactions,
            "total_value_usd": self.total_value_usd,
            "insiders": self.insiders,
            "findings": self.findings,
        }


def detect_insider_cluster(symbol: str) -> InsiderCluster | None:
    """Pull last 30 days of Form 4 transactions and detect a cluster buy.

    Returns None if no cluster is detected (fewer than MIN_INSIDERS_FOR_CLUSTER
    unique insiders buying in the same week, or no data available).
    """
    try:
        y = yf.Ticker(symbol)
        ins = y.insider_transactions
    except Exception:
        log.exception("insider_fetch_failed", extra={"symbol": symbol})
        return None

    if ins is None or ins.empty:
        return None

    if "Text" not in ins.columns or "Start Date" not in ins.columns:
        return None

    # Filter to last 30 days
    cutoff = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=LOOKBACK_DAYS))
    recent = ins[pd.to_datetime(ins["Start Date"], errors="coerce") >= cutoff].copy()
    if recent.empty:
        return None

    # Classify each row as buy / sell / other based on Text
    text = recent["Text"].fillna("").astype(str)
    is_buy = text.str.contains(_BUY_PATTERNS)
    recent = recent.assign(_is_buy=is_buy)

    buys = recent[recent["_is_buy"]].copy()
    if buys.empty:
        return None

    # Filter to buys >= $100k (avoid tiny 10b5-1 plan purchases)
    buys["Value"] = pd.to_numeric(buys.get("Value"), errors="coerce").fillna(0)
    buys = buys[buys["Value"] >= MIN_CLUSTER_VALUE_USD]
    if buys.empty:
        return None

    # Group by week (ISO week starting Monday)
    buys["_week"] = pd.to_datetime(buys["Start Date"], errors="coerce").dt.to_period("W-SUN").apply(lambda p: p.start_time.date())
    weekly = buys.groupby("_week").agg(
        num_buy_transactions=("_is_buy", "size"),
        insiders=("Insider", lambda s: sorted(set(s.dropna()))),
        total_value_usd=("Value", "sum"),
    ).reset_index()

    if weekly.empty:
        return None

    # Find weeks with the most unique buyers
    weekly["num_buyers"] = weekly["insiders"].apply(len)
    top_week = weekly.sort_values(["num_buyers", "total_value_usd"], ascending=[False, False]).iloc[0]

    if int(top_week["num_buyers"]) < MIN_INSIDERS_FOR_CLUSTER:
        return None

    cluster = InsiderCluster(
        symbol=symbol,
        week_starting=top_week["_week"],
        num_buyers=int(top_week["num_buyers"]),
        num_buy_transactions=int(top_week["num_buy_transactions"]),
        total_value_usd=float(top_week["total_value_usd"]),
        insiders=list(top_week["insiders"]),
    )
    cluster.findings.append(
        f"🟢 Insider cluster: {cluster.num_buyers} insiders bought {symbol} in week "
        f"of {cluster.week_starting.isoformat()} (${cluster.total_value_usd:,.0f} total) — "
        f"smart money accumulation, elite trader's strongest insider signal"
    )
    # Name the insiders
    if len(cluster.insiders) <= 3:
        cluster.findings.append(
            f"   Buyers: {', '.join(cluster.insiders)}"
        )
    else:
        cluster.findings.append(
            f"   Buyers: {', '.join(cluster.insiders[:3])} (+{len(cluster.insiders) - 3} more)"
        )
    return cluster

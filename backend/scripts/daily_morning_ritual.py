"""Daily morning ritual script (D-47 PR 4).

This is the script that powers your Monday-morning coffee routine:

1. Fetch macro context (VIX, sector leaders/laggers, risk regime)
2. Run the screener with catalyst enrichment, min_confluence=2
3. Print the top candidates ranked by score with their 5 catalyst signals
4. Save the full output to docs/SESSIONS/morning_brief/YYYY-MM-DD.json
   so you can compare day-over-day

USAGE:
    python backend/scripts/daily_morning_ritual.py
    python backend/scripts/daily_morning_ritual.py --min-confluence 3
    python backend/scripts/daily_morning_ritual.py --limit 25
    python backend/scripts/daily_morning_ritual.py --tickers OKTA,FTNT,KURA

If you pass --tickers, it skips the screener and just runs the
catalyst signals on the named tickers (useful when you have a
watchlist).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

import requests


def fetch_macro_context() -> dict:
    """Hit the live API for the macro context."""
    # In-process, not HTTP. Reuse the macro_context module.
    from backend.app.infrastructure.professional.macro_context import (
        get_macro_context,
    )
    ctx = get_macro_context()
    return ctx.to_dict()


def run_screener(
    base_url: str,
    min_confluence: int,
    limit: int,
) -> list[dict]:
    """Run the TV screener with catalyst enrichment."""
    # Use a config that finds momentum candidates: bullish structure
    # + above SMA50 + decent volume. The exact filters can be tuned
    # by the user in a saved config.
    config = {
        "name": "morning_ritual_momentum",
        "description": "Momentum candidates with catalyst enrichment",
        "asset_classes": ["equities"],
        "timeframes": ["1D"],
        "filters": [
            # Higher than 50d SMA (uptrend)
            {"category": "trend", "indicator": "price_vs_sma50",
             "operator": "gt", "params": {"value": 1.0}, "timeframe": "1D"},
            # Above 200d SMA (long-term uptrend)
            {"category": "trend", "indicator": "price_vs_sma200",
             "operator": "gt", "params": {"value": 1.0}, "timeframe": "1D"},
            # Decent ADX (trending, not choppy)
            {"category": "trend", "indicator": "adx",
             "operator": "gt", "params": {"value": 15}, "timeframe": "1D"},
            # Positive 1M performance (already running)
            {"category": "performance", "indicator": "perf_1m",
             "operator": "gt", "params": {"value": 0.0}, "timeframe": "1D"},
            # Above-average volume
            {"category": "volume", "indicator": "volume_vs_avg",
             "operator": "gt", "params": {"value": 1.0}, "timeframe": "1D"},
        ],
    }
    payload = {
        "config": config,
        "limit": limit,
        "enrich_with_catalysts": True,
        "min_confluence": min_confluence,
    }
    r = requests.post(
        f"{base_url}/api/v1/screen/tv",
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["data"]["results"]


def run_catalysts_on_tickers(
    base_url: str,
    tickers: list[str],
) -> list[dict]:
    """Hit the analyze endpoint for each ticker, extract catalyst signals."""
    out = []
    for t in tickers:
        r = requests.post(
            f"{base_url}/api/v1/ticker/{t}/analyze",
            json={"symbol": t, "timeframe": "1D"},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()["data"]
        v = data["verdict"]
        out.append({
            "symbol": t,
            "sector": data.get("sector"),
            "action": v["action"],
            "conviction": v["conviction"],
            "entry": (v.get("entry_zone_low"), v.get("entry_zone_high")),
            "stop": v.get("stop_loss"),
            "targets": v.get("targets", []),
            "thesis": v.get("thesis", ""),
        })
    return out


def print_macro(macro: dict) -> None:
    """Print the macro context banner."""
    print("\n" + "=" * 70)
    print("  MACRO CONTEXT — what the market is doing RIGHT NOW")
    print("=" * 70)
    print(f"  VIX:       {macro.get('vix', 'N/A')}  ({macro.get('risk_regime', 'unknown')})")
    print(f"  SPY:       ${macro.get('spy_close', 'N/A')}  ({macro.get('spy_change_1d_pct', 'N/A')}% today)")
    print(f"  QQQ:       ${macro.get('qqq_close', 'N/A')}  ({macro.get('qqq_change_1d_pct', 'N/A')}% today)")
    print(f"  DXY:       {macro.get('dxy', 'N/A')}")
    print(f"  Leading:   {macro.get('leading_sector', 'N/A')} ({macro.get('leading_sector_1d_pct', 'N/A')}%)")
    print(f"  Lagging:   {macro.get('lagging_sector', 'N/A')} ({macro.get('lagging_sector_1d_pct', 'N/A')}%)")


def print_screener_results(results: list[dict]) -> None:
    """Print the top screener candidates with catalyst signals."""
    if not results:
        print("\n  ⚠️  No candidates passed the confluence filter today")
        return

    print("\n" + "=" * 70)
    print(f"  TOP CANDIDATES — {len(results)} passed min_confluence filter")
    print("=" * 70)
    print(f"  {'SYMBOL':<7} {'SCORE':<6} {'CONF':<5} {'CATALYSTS'}")
    print("  " + "-" * 68)
    for r in results:
        sym = r["symbol"]
        score = r.get("score", 0)
        conf = r.get("catalyst_confluence_count", 0)
        signals = r.get("catalyst_signals") or {}
        findings = signals.get("findings", [])
        findings_str = "; ".join(findings[:3]) if findings else "—"
        if len(findings_str) > 60:
            findings_str = findings_str[:57] + "..."
        summary = r.get("catalyst_summary", "—")
        print(f"  {sym:<7} {score:<6} {conf}/5    {summary}")
        if findings:
            print(f"          └─ {findings_str}")


def save_brief(macro: dict, results: list, tickers: list, args, brief_dir: Path) -> None:
    """Save the full output to a dated JSON for day-over-day comparison."""
    today = _dt.date.today().isoformat()
    payload = {
        "date": today,
        "args": vars(args),
        "macro_context": macro,
        "screener_results_count": len(results),
        "screener_results": results,
        "explicit_tickers": tickers,
        "generated_at": _dt.datetime.now().isoformat(),
    }
    out_path = brief_dir / f"{today}.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  💾 Saved to: {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daily morning ritual — macro + catalyst-enriched screener"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="conflu.ai API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--min-confluence",
        type=int,
        default=2,
        help="Minimum catalyst signals to surface (0-5, default 2)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max screener results (default 50)",
    )
    parser.add_argument(
        "--tickers",
        default=None,
        help="Comma-separated tickers to analyze instead of running screener",
    )
    parser.add_argument(
        "--brief-dir",
        type=Path,
        default=Path("docs/SESSIONS/morning_brief"),
        help="Where to save the JSON brief",
    )
    args = parser.parse_args()

    args.brief_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "█" * 70)
    print("  conflu.ai DAILY MORNING RITUAL")
    print(f"  { _dt.date.today().isoformat() }")
    print("█" * 70)

    # 1. Macro context
    try:
        macro = fetch_macro_context()
    except Exception as e:
        print(f"\n  ⚠️  Failed to fetch macro context: {e}")
        macro = {}
    print_macro(macro)

    # 2. Either run screener or analyze explicit tickers
    tickers = args.tickers.split(",") if args.tickers else []
    if tickers:
        print("\n" + "=" * 70)
        print(f"  EXPLICIT TICKERS — analyzing {len(tickers)}")
        print("=" * 70)
        results = run_catalysts_on_tickers(args.base_url, tickers)
        for r in results:
            print(f"  {r['symbol']:<7} {r['action']:<10} c:{r['conviction']:<3} sector={r['sector']}")
            print(f"          entry={r['entry']}  stop={r['stop']}  targets={r['targets']}")
            print(f"          thesis: {r['thesis'][:120]}...")
    else:
        try:
            results = run_screener(args.base_url, args.min_confluence, args.limit)
        except Exception as e:
            print(f"\n  ⚠️  Failed to run screener: {e}")
            results = []
        print_screener_results(results)

    # 3. Save brief
    save_brief(macro, results, tickers, args, args.brief_dir)

    print("\n" + "=" * 70)
    print("  NEXT: review the top 3-5 candidates.")
    print("  For each one: check the verdict, set entry/stop/target,")
    print("  decide if confluence + setup merits a paper trade.")
    print("  Record in docs/SESSIONS/paper_trades/YYYY-MM-DD.csv")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

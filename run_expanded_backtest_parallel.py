"""
Parallel Expanded Backtest — Efficient version using asyncio.gather
Tests elite templates across 50 symbols, 3 key regimes, 1D + 4h timeframes
"""

import sys
sys.path.insert(0, '.')

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from backend.app.infrastructure.screener.configs import load_screen_template
from backend.app.infrastructure.data.fetcher import OHLCVFetcher
from backend.app.infrastructure.backtest.external_backtest import ExternalBacktestEngine, BacktestConfig

# ──────────────────────────────────────────────────────────────────────────────
# ELITE TEMPLATES ONLY (from D-61 results)
# ──────────────────────────────────────────────────────────────────────────────
ELITE_TEMPLATES = [
    "52week-breakout",
    "trend-follower-v2",
    "vcp-breakout",
    "trend-pullback-v2",
    "institutional-trend-follower-mtf",
    "mean-reversion",
    "volume-trend-accumulation",
    "institutional-quality-v2",
    "low-vol-setup",
    "statistical-mean-reversion",
    "distribution",
    "breakdown",
]

# ──────────────────────────────────────────────────────────────────────────────
# EXPANDED SYMBOL UNIVERSE (50 symbols across 11 sectors)
# ──────────────────────────────────────────────────────────────────────────────
SYMBOLS = [
    # Technology (10)
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "INTC", "AMD", "QCOM",
    # Healthcare (5)
    "JNJ", "UNH", "LLY", "ABBV", "MRK",
    # Financials (5)
    "JPM", "V", "MA", "WFC", "GS",
    # Consumer Discretionary (5)
    "AMZN", "TSLA", "HD", "MCD", "NKE",
    # Communication Services (5)
    "GOOGL", "META", "NFLX", "DIS", "CMCSA",
    # Industrials (5)
    "HON", "UNP", "UPS", "CAT", "BA",
    # Consumer Staples (5)
    "PG", "KO", "PEP", "WMT", "COST",
    # Energy (5)
    "XOM", "CVX", "COP", "EOG", "SLB",
    # Utilities (2)
    "NEE", "DUK",
    # Materials (2)
    "LIN", "APD",
    # Real Estate (2)
    "PLD", "AMT",
]

# ──────────────────────────────────────────────────────────────────────────────
# KEY REGIME PERIODS (3 most important)
# ──────────────────────────────────────────────────────────────────────────────
REGIME_PERIODS = {
    "bear_2022": ("2022-01-01", "2022-12-31"),        # Bear market stress test
    "recovery_2023": ("2023-01-01", "2023-12-31"),    # Recovery validation
    "bull_2024": ("2024-01-01", "2024-12-31"),        # Current bull
    "full_3y": ("2022-01-01", "2024-12-31"),          # Full 3-year
}

# ──────────────────────────────────────────────────────────────────────────────
TIMEFRAMES = ["1D", "4h"]  # Most critical for screener

# Concurrency limit (Yahoo Finance rate limit ~25 req/min)
MAX_CONCURRENT = 5

# ──────────────────────────────────────────────────────────────────────────────

semaphore = asyncio.Semaphore(MAX_CONCURRENT)

async def test_one_symbol(
    engine: ExternalBacktestEngine,
    template_name: str,
    signal_params: dict,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Test single symbol with semaphore for rate limiting."""
    async with semaphore:
        config = BacktestConfig(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_cash=100_000,
            fees_bps=10,
            slippage_bps=5,
            position_sizing="fixed",
            sizing_params={"cash_per_trade": 10000},
            signal_params=signal_params,
        )
        try:
            result = await engine.run_backtest(config)
            if result.error:
                return {symbol: {"error": result.error}}
            return {symbol: {
                "total_return": round(result.total_return * 100, 2),
                "annualized_return": round(result.annualized_return * 100, 2),
                "sharpe": round(result.sharpe_ratio, 3),
                "sortino": round(result.sortino_ratio, 3),
                "max_dd_pct": round(result.max_drawdown_pct, 2),
                "win_rate": round(result.win_rate * 100, 2),
                "profit_factor": round(result.profit_factor, 2),
                "expectancy": round(result.expectancy, 2),
                "total_trades": result.total_trades,
                "avg_hold_days": round(result.avg_hold_days, 1),
            }}
        except Exception as e:
            return {symbol: {"error": str(e)}}


async def test_template_regime_tf(
    template_name: str,
    regime_name: str,
    timeframe: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Test one template on one regime + timeframe across all symbols in parallel."""
    print(f"  [{template_name}] {regime_name} | {timeframe}...", end=" ", flush=True)

    try:
        template = load_screen_template(template_name)
    except Exception as e:
        print(f" LOAD FAILED: {e}")
        return {"error": f"Load failed: {e}"}

    signal_params = {}
    for f in template.filters:
        signal_params[f.indicator] = f.params

    fetcher = OHLCVFetcher()
    engine = ExternalBacktestEngine(fetcher=fetcher)

    # Run all symbols in parallel (with semaphore limiting concurrency)
    tasks = [
        test_one_symbol(engine, template_name, signal_params, sym, timeframe, start_date, end_date)
        for sym in SYMBOLS
    ]
    results_list = await asyncio.gather(*tasks)

    # Merge results
    results = {}
    for r in results_list:
        results.update(r)

    valid_results = [r for r in results.values() if "error" not in r and r.get("total_trades", 0) >= 10]
    valid_count = len(valid_results)

    if valid_results:
        agg = {
            "template": template_name,
            "regime": regime_name,
            "timeframe": timeframe,
            "period_start": start_date,
            "period_end": end_date,
            "valid_symbols": valid_count,
            "total_symbols": len(SYMBOLS),
            "avg_return": round(sum(r["total_return"] for r in valid_results) / len(valid_results), 2),
            "avg_annual_return": round(sum(r["annualized_return"] for r in valid_results) / len(valid_results), 2),
            "avg_sharpe": round(sum(r["sharpe"] for r in valid_results) / len(valid_results), 3),
            "avg_sortino": round(sum(r["sortino"] for r in valid_results) / len(valid_results), 3),
            "avg_max_dd": round(sum(r["max_dd_pct"] for r in valid_results) / len(valid_results), 2),
            "avg_win_rate": round(sum(r["win_rate"] for r in valid_results) / len(valid_results), 2),
            "avg_profit_factor": round(sum(r["profit_factor"] for r in valid_results) / len(valid_results), 2),
            "avg_expectancy": round(sum(r["expectancy"] for r in valid_results) / len(valid_results), 2),
            "avg_trades": round(sum(r["total_trades"] for r in valid_results) / len(valid_results), 1),
            "avg_hold_days": round(sum(r["avg_hold_days"] for r in valid_results) / len(valid_results), 1),
            "details": results,
        }
        print(f"OK {valid_count}/{len(SYMBOLS)} | Return: {agg['avg_return']:.1f}% | Sharpe: {agg['avg_sharpe']:.2f} | WR: {agg['avg_win_rate']:.1f}% | PF: {agg['avg_profit_factor']:.2f}")
    else:
        agg = {
            "template": template_name,
            "regime": regime_name,
            "timeframe": timeframe,
            "period_start": start_date,
            "period_end": end_date,
            "valid_symbols": 0,
            "total_symbols": len(SYMBOLS),
            "details": results,
        }
        print(f"FAIL NO VALID RESULTS")

    return agg


async def main():
    print("=" * 70)
    print("PARALLEL EXPANDED BACKTEST")
    print(f"Templates: {len(ELITE_TEMPLATES)} | Symbols: {len(SYMBOLS)} | Timeframes: {TIMEFRAMES} | Regimes: {len(REGIME_PERIODS)}")
    print(f"Total combinations: {len(ELITE_TEMPLATES)} × {len(TIMEFRAMES)} × {len(REGIME_PERIODS)} = {len(ELITE_TEMPLATES) * len(TIMEFRAMES) * len(REGIME_PERIODS)}")
    print(f"Max concurrent requests: {MAX_CONCURRENT}")
    print("=" * 70)

    all_results = {}

    # Create all tasks
    tasks = []
    for template in ELITE_TEMPLATES:
        all_results[template] = {}
        for timeframe in TIMEFRAMES:
            all_results[template][timeframe] = {}
            for regime_name, (start_date, end_date) in REGIME_PERIODS.items():
                task = test_template_regime_tf(template, regime_name, timeframe, start_date, end_date)
                tasks.append((template, timeframe, regime_name, task))

    # Execute all in parallel
    for template, timeframe, regime_name, task in tasks:
        result = await task
        all_results[template][timeframe][regime_name] = result

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"backtest_expanded_parallel_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    # Print summary
    print(f"\n\n{'='*70}")
    print("EXPANDED BACKTEST SUMMARY")
    print(f"{'='*70}")

    for template in ELITE_TEMPLATES:
        print(f"\n{'─'*70}")
        print(f"Template: {template}")
        print(f"{'─'*70}")

        for timeframe in TIMEFRAMES:
            print(f"\n  Timeframe: {timeframe}")
            print(f"  {'Regime':<18} {'Valid':<6} {'Return%':<8} {'Sharpe':<7} {'WR%':<6} {'PF':<6}")
            print(f"  {'-'*55}")

            for regime_name in REGIME_PERIODS.keys():
                if template in all_results and timeframe in all_results[template] and regime_name in all_results[template][timeframe]:
                    result = all_results[template][timeframe][regime_name]
                    if "avg_return" in result:
                        print(f"  {regime_name:<18} {result['valid_symbols']:<6} {result['avg_return']:<8.1f} {result['avg_sharpe']:<7.2f} {result['avg_win_rate']:<6.1f} {result['avg_profit_factor']:<6.2f}")
                    else:
                        print(f"  {regime_name:<18} FAILED")

    print(f"\n\nResults saved to: {output_file}")
    return all_results


if __name__ == "__main__":
    asyncio.run(main())
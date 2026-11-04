"""
Minimal Expanded Backtest — 2 templates, 2 regimes, 20 symbols
Quick regime robustness check
"""

import sys
sys.path.insert(0, '.')

import asyncio
import json
from datetime import datetime

from backend.app.infrastructure.screener.configs import load_screen_template
from backend.app.infrastructure.data.fetcher import OHLCVFetcher
from backend.app.infrastructure.backtest.external_backtest import ExternalBacktestEngine, BacktestConfig

# ──────────────────────────────────────────────────────────────────────────────
TOP_TEMPLATES = ["52week-breakout", "trend-pullback-v2"]

SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "INTC", "AMD", "QCOM",
    "JNJ", "UNH", "LLY", "ABBV", "MRK",
    "JPM", "V", "MA", "WFC", "GS",
]

REGIME_PERIODS = {
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "bull_2024": ("2024-01-01", "2024-12-31"),
}

MAX_CONCURRENT = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

async def test_one_symbol(engine, signal_params, symbol, start_date, end_date):
    async with semaphore:
        config = BacktestConfig(
            symbol=symbol, timeframe="1D",
            start_date=start_date, end_date=end_date,
            initial_cash=100_000, fees_bps=10, slippage_bps=5,
            position_sizing="fixed", sizing_params={"cash_per_trade": 10000},
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

async def test_template_regime(template_name, regime_name, start_date, end_date):
    print(f"  [{template_name}] {regime_name}...", end=" ", flush=True)

    try:
        template = load_screen_template(template_name)
    except Exception as e:
        print(f" LOAD FAILED: {e}")
        return {"error": f"Load failed: {e}"}

    signal_params = {f.indicator: f.params for f in template.filters}
    fetcher = OHLCVFetcher()
    engine = ExternalBacktestEngine(fetcher=fetcher)

    tasks = [test_one_symbol(engine, signal_params, sym, start_date, end_date) for sym in SYMBOLS]
    results_list = await asyncio.gather(*tasks)

    results = {}
    for r in results_list:
        results.update(r)

    valid_results = [r for r in results.values() if "error" not in r and r.get("total_trades", 0) >= 10]
    valid_count = len(valid_results)

    if valid_results:
        agg = {
            "template": template_name,
            "regime": regime_name,
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
        print(f" OK {valid_count}/{len(SYMBOLS)} | Ret: {agg['avg_return']:.1f}% | Sh: {agg['avg_sharpe']:.2f} | WR: {agg['avg_win_rate']:.1f}% | PF: {agg['avg_profit_factor']:.2f}")
    else:
        agg = {"template": template_name, "regime": regime_name, "valid_symbols": 0, "total_symbols": len(SYMBOLS), "details": results}
        print(f" FAIL")

    return agg


async def main():
    print("=" * 60)
    print("MINIMAL EXPANDED BACKTEST")
    print(f"Templates: {len(TOP_TEMPLATES)} | Symbols: {len(SYMBOLS)} | Regimes: {len(REGIME_PERIODS)}")
    print(f"Total: {len(TOP_TEMPLATES) * len(REGIME_PERIODS)} combos × 20 symbols = {len(TOP_TEMPLATES) * len(REGIME_PERIODS) * len(SYMBOLS)} backtests")
    print("=" * 60)

    all_results = {}

    for template in TOP_TEMPLATES:
        all_results[template] = {}
        for regime_name, (start_date, end_date) in REGIME_PERIODS.items():
            result = await test_template_regime(template, regime_name, start_date, end_date)
            all_results[template][regime_name] = result

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"backtest_minimal_expanded_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"\n{'Template':<25} {'Regime':<12} {'Valid':<6} {'Ret%':<7} {'Sharpe':<7} {'WR%':<6} {'PF':<6}")
    print("-" * 65)

    for template in TOP_TEMPLATES:
        for regime_name in REGIME_PERIODS.keys():
            result = all_results[template][regime_name]
            if "avg_return" in result:
                print(f"{template:<25} {regime_name:<12} {result['valid_symbols']:<6} {result['avg_return']:<7.1f} {result['avg_sharpe']:<7.2f} {result['avg_win_rate']:<6.1f} {result['avg_profit_factor']:<6.2f}")
            else:
                print(f"{template:<25} {regime_name:<12} FAIL")

    print(f"\nResults saved to: {output_file}")
    return all_results


if __name__ == "__main__":
    asyncio.run(main())
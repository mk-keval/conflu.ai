"""
Expanded Backtest Runner — More Symbols, Longer History, Multiple Timeframes
Tests elite templates across diverse universe and market regimes
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
# EXPANDED SYMBOL UNIVERSE (50 symbols across sectors & caps)
# ──────────────────────────────────────────────────────────────────────────────
# Large Cap (SPY components across 11 GICS sectors)
LARGE_CAP = [
    # Technology
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "INTC", "AMD", "QCOM",
    # Healthcare
    "JNJ", "UNH", "LLY", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY", "AMGN",
    # Financials
    "JPM", "BRK.B", "V", "MA", "WFC", "GS", "MS", "C", "AXP", "BLK",
    # Consumer Discretionary
    "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TGT", "BKNG", "MAR",
    # Communication Services
    "GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS", "CHTR", "EA",
    # Industrials
    "HON", "UNP", "UPS", "CAT", "BA", "RTX", "LMT", "GE", "MMM", "DE",
    # Consumer Staples
    "PG", "KO", "PEP", "WMT", "COST", "CL", "KMB", "GIS", "K", "HSY",
    # Energy
    "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO", "OXY", "HAL",
    # Utilities
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "PEG", "ED", "FE",
    # Materials
    "LIN", "APD", "SHW", "FCX", "NEM", "DD", "ECL", "PPG", "IFF", "DOW",
    # Real Estate
    "PLD", "AMT", "CCI", "EQIX", "PSA", "WELL", "SPG", "O", "VICI", "EXR",
]

# Mid Cap (S&P 400 representatives)
MID_CAP = [
    "CROX", "DECK", "ONTO", "SMCI", "VRT", "PWR", "JKHY", "CIVI", "MODG", "LNTH",
]

# Small Cap (S&P 600 representatives)
SMALL_CAP = [
    "AAOI", "ACVA", "ADUS", "AEIS", "AIR", "AKYA", "ALKT", "AMAL", "AMBC", "AMCX",
]

# Sector ETFs for regime validation
SECTOR_ETFS = [
    "XLK", "XLV", "XLF", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLB", "XLRE", "XBI",
]

# Broad market ETFs
BROAD_ETFS = ["SPY", "QQQ", "IWM", "DIA", "VTI", "VEA", "VWO"]

# ──────────────────────────────────────────────────────────────────────────────
# SYMBOL SETS FOR TESTING
# ──────────────────────────────────────────────────────────────────────────────
SYMBOL_SETS = {
    "large_cap": LARGE_CAP,
    "mid_cap": MID_CAP,
    "small_cap": SMALL_CAP,
    "sector_etfs": SECTOR_ETFS,
    "broad_etfs": BROAD_ETFS,
    "all_50": LARGE_CAP[:50],  # First 50 large cap
    "all_100": LARGE_CAP + MID_CAP + SMALL_CAP[:10],  # ~110 symbols
}

# Default: 50 large cap across sectors
SYMBOLS = SYMBOL_SETS["all_50"]

# ──────────────────────────────────────────────────────────────────────────────
# MULTI-TIMEFRAME & MULTI-REGIME CONFIG
# ──────────────────────────────────────────────────────────────────────────────
TIMEFRAMES = ["1D", "4h", "1h", "1W"]

# Regime periods (non-overlapping, covering different market conditions)
REGIME_PERIODS = {
    "covid_crash": ("2020-02-01", "2020-06-30"),      # Crash + V-recovery
    "covid_recovery": ("2020-07-01", "2021-12-31"),   # Bull run
    "bear_2022": ("2022-01-01", "2022-12-31"),        # Bear market
    "recovery_2023": ("2023-01-01", "2023-12-31"),    # Recovery
    "bull_2024": ("2024-01-01", "2024-12-31"),        # Current bull
    "full_5y": ("2020-01-01", "2024-12-31"),          # Full 5-year
}

# ──────────────────────────────────────────────────────────────────────────────

async def test_template_on_symbols(
    template_name: str,
    symbols: list[str],
    timeframe: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Test a single template against symbols on specific timeframe/period."""
    try:
        template = load_screen_template(template_name)
    except Exception as e:
        return {"template": template_name, "error": f"Load failed: {e}"}

    signal_params = {}
    for f in template.filters:
        signal_params[f.indicator] = f.params

    config = BacktestConfig(
        symbol="",
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

    fetcher = OHLCVFetcher()
    engine = ExternalBacktestEngine(fetcher=fetcher)

    results = {}
    valid_count = 0

    for symbol in symbols:
        config.symbol = symbol
        try:
            result = await engine.run_backtest(config)
            if result.error:
                results[symbol] = {"error": result.error}
            else:
                results[symbol] = {
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
                }
                if result.total_trades >= 10:
                    valid_count += 1
        except Exception as e:
            results[symbol] = {"error": str(e)}

    valid_results = [r for r in results.values() if "error" not in r and r.get("total_trades", 0) >= 10]

    if valid_results:
        agg = {
            "template": template_name,
            "timeframe": timeframe,
            "period_start": start_date,
            "period_end": end_date,
            "valid_symbols": valid_count,
            "total_symbols": len(symbols),
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
    else:
        agg = {
            "template": template_name,
            "timeframe": timeframe,
            "period_start": start_date,
            "period_end": end_date,
            "valid_symbols": 0,
            "total_symbols": len(symbols),
            "details": results,
        }

    return agg


async def main():
    print("=" * 70)
    print("EXPANDED BACKTEST — Elite Templates × 50 Symbols × 4 TFs × 6 Regimes")
    print("=" * 70)
    print(f"Templates: {len(ELITE_TEMPLATES)}")
    print(f"Symbols: {len(SYMBOLS)} (large cap across 11 sectors)")
    print(f"Timeframes: {TIMEFRAMES}")
    print(f"Regime periods: {list(REGIME_PERIODS.keys())}")
    print()

    all_results = {}

    # Run each template on each timeframe for each regime period
    for template in ELITE_TEMPLATES:
        template_key = template
        all_results[template_key] = {}

        for timeframe in TIMEFRAMES:
            all_results[template_key][timeframe] = {}

            for regime_name, (start_date, end_date) in REGIME_PERIODS.items():
                print(f"\n{'='*60}")
                print(f"Testing: {template} | {timeframe} | {regime_name} ({start_date} to {end_date})")
                print(f"{'='*60}")

                result = await test_template_on_symbols(
                    template, SYMBOLS, timeframe, start_date, end_date
                )

                regime_key = f"{regime_name}_{timeframe}"
                all_results[template_key][timeframe][regime_name] = result

                if "avg_return" in result:
                    print(f"  Valid: {result['valid_symbols']}/{result['total_symbols']}")
                    print(f"  Avg Return: {result['avg_return']:.1f}% | Sharpe: {result['avg_sharpe']:.2f} | WR: {result['avg_win_rate']:.1f}% | PF: {result['avg_profit_factor']:.2f}")
                else:
                    print(f"  FAILED: {result.get('error', 'No valid results')}")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"backtest_expanded_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    # Print summary table
    print(f"\n\n{'='*70}")
    print("EXPANDED BACKTEST SUMMARY")
    print(f"{'='*70}")

    for template in ELITE_TEMPLATES:
        print(f"\n{'─'*70}")
        print(f"Template: {template}")
        print(f"{'─'*70}")

        for timeframe in TIMEFRAMES:
            print(f"\n  Timeframe: {timeframe}")
            print(f"  {'Regime':<20} {'Valid':<6} {'Return%':<8} {'Sharpe':<7} {'WR%':<6} {'PF':<6}")
            print(f"  {'-'*60}")

            for regime_name in REGIME_PERIODS.keys():
                regime_key = f"{regime_name}_{timeframe}"
                if template in all_results and timeframe in all_results[template] and regime_name in all_results[template][timeframe]:
                    result = all_results[template][timeframe][regime_name]
                    if "avg_return" in result:
                        print(f"  {regime_name:<20} {result['valid_symbols']:<6} {result['avg_return']:<8.1f} {result['avg_sharpe']:<7.2f} {result['avg_win_rate']:<6.1f} {result['avg_profit_factor']:<6.2f}")
                    else:
                        print(f"  {regime_name:<20} FAILED")

    print(f"\n\nResults saved to: {output_file}")
    return all_results


if __name__ == "__main__":
    asyncio.run(main())
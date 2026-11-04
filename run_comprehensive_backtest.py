"""
Comprehensive Backtest Runner for All Templates
Tests all templates with external data (Yahoo Finance) and compares performance
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

# Templates to test
TEMPLATES = [
    # New research-backed templates
    "trend-follower-v2",
    "trend-pullback-v2",
    "vcp-breakout",
    "rsi2-reversion",
    "institutional-quality-v2",
    
    # Original high-quality templates
    "trend-follower",
    "high-conviction-stack",
    "bull-flag-continuation",
    "52week-breakout",
    "short-squeeze",
    "statistical-mean-reversion",
    "mean-reversion",
    "volatility-expansion",
    "volume-trend-accumulation",
    "quality-trend-fundamentals",
    "trend-leader",
    "institutional-swing-quality",
    "institutional-trend-follower-mtf",
    "low-vol-setup",
    "distribution",
    "breakdown",
]

# Test symbols (liquid large caps)
SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM"]

# Date range
END_DATE = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")  # 2 years

async def test_template(template_name: str, symbols: list[str]) -> dict:
    """Test a single template against all symbols."""
    print(f"\n{'='*60}")
    print(f"Testing: {template_name}")
    print(f"{'='*60}")
    
    try:
        template = load_screen_template(template_name)
    except Exception as e:
        return {"template": template_name, "error": f"Load failed: {e}"}
    
    # Convert template to signal params
    signal_params = {}
    for f in template.filters:
        signal_params[f.indicator] = f.params
    
    config = BacktestConfig(
        symbol="",  # Will be set per symbol
        timeframe="1D",
        start_date="2023-01-01",
        end_date="2024-12-31",
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
    
    # Aggregate metrics
    valid_results = [r for r in results.values() if "error" not in r and r.get("total_trades", 0) >= 10]
    
    if valid_results:
        agg = {
            "template": template_name,
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
            "valid_symbols": 0,
            "total_symbols": len(symbols),
            "details": results,
        }
    
    print(f"  Valid: {valid_count}/{len(symbols)}")
    if valid_results:
        print(f"  Avg Return: {agg['avg_return']:.2f}% | Sharpe: {agg['avg_sharpe']:.2f} | WR: {agg['avg_win_rate']:.1f}% | PF: {agg['avg_profit_factor']:.2f} | Trades: {agg['avg_trades']:.1f}")
    
    return agg


async def main():
    print(f"Starting comprehensive backtest")
    print(f"Symbols: {SYMBOLS}")
    print(f"Date range: 2023-01-01 to 2024-12-31")
    print(f"Templates: {len(TEMPLATES)}")
    
    all_results = {}
    
    for template in TEMPLATES:
        result = await test_template(template, SYMBOLS)
        all_results[template] = result
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"backtest_results_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    
    # Summary table
    print(f"\n{'Template':<30} {'Valid':<6} {'Return%':<8} {'Sharpe':<7} {'WR%':<6} {'PF':<6} {'Exp':<8} {'Trades':<7}")
    print("-" * 80)
    
    for template, result in all_results.items():
        if "avg_return" in result:
            print(f"{template:<30} {result['valid_symbols']:<6} {result['avg_return']:<8.1f} {result['avg_sharpe']:<7.2f} {result['avg_win_rate']:<6.1f} {result['avg_profit_factor']:<6.2f} {result['avg_expectancy']:<8.2f} {result['avg_trades']:<7.1f}")
        else:
            print(f"{template:<30} FAILED")
    
    # Find best templates
    valid_templates = {k: v for k, v in all_results.items() if "avg_return" in v and v.get("valid_symbols", 0) > 0}
    
    if valid_templates:
        best_return = max(valid_templates.items(), key=lambda x: x[1]["avg_return"])
        best_sharpe = max(valid_templates.items(), key=lambda x: x[1]["avg_sharpe"])
        best_wr = max(valid_templates.items(), key=lambda x: x[1]["avg_win_rate"])
        best_pf = max(valid_templates.items(), key=lambda x: x[1]["avg_profit_factor"])
        
        print(f"\n🏆 Best Return: {best_return[0]} ({best_return[1]['avg_return']:.1f}%)")
        print(f"🏆 Best Sharpe: {best_sharpe[0]} ({best_sharpe[1]['avg_sharpe']:.2f})")
        print(f"🏆 Best Win Rate: {best_wr[0]} ({best_wr[1]['avg_win_rate']:.1f}%)")
        print(f"🏆 Best Profit Factor: {best_pf[0]} ({best_pf[1]['avg_profit_factor']:.2f})")
        
        # Filter for >55% win rate and PF>1.5
        elite = {k: v for k, v in valid_templates.items() 
                 if v["avg_win_rate"] > 55 and v["avg_profit_factor"] > 1.5}
        if elite:
            print(f"\n⭐ ELITE TEMPLATES (>55% WR, >1.5 PF):")
            for k, v in elite.items():
                print(f"  {k}: WR={v['avg_win_rate']:.1f}% PF={v['avg_profit_factor']:.2f} Sharpe={v['avg_sharpe']:.2f}")
        else:
            print(f"\n⚠️  No templates meet elite criteria (>55% WR, >1.5 PF)")
    
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
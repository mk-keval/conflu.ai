#!/usr/bin/env python
"""Research baseline backtest runner.

Usage:
    python scripts/run_research_baseline.py [--setup SETUP] [--universe UNIVERSE] [--start START] [--end END]
    
Runs baseline backtest for a given setup and compares against control distributions.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.research.data import download_daily, load_universe
from backend.app.research.indicators import add_indicators
from backend.app.research.setups import (
    SETUPS,
    eligible,
    statistical_mean_reversion,
    breakout_52week,
    low_vol_setup,
    volume_trend_accumulation
)
from backend.app.research.engine import run_portfolio, ExitRules, PortfolioRules, Trade
from backend.app.research.metrics import compute_metrics, print_metrics, metrics_to_dict, BacktestMetrics
from backend.app.research.control import (
    run_control_suite,
    compute_control_pvalues,
    summarize_control_results
)


def load_setup_config(setup_name: str) -> dict:
    """Load setup configuration from YAML."""
    # Map setup names to config filenames
    config_map = {
        "statistical_mean_reversion": "statistical-mean-reversion.yaml",
        "breakout_52week": "52week-breakout.yaml",
        "low_vol_setup": "low-vol-setup.yaml",
        "volume_trend_accumulation": "volume-trend-accumulation.yaml"
    }
    config_filename = config_map.get(setup_name, f"{setup_name}.yaml")
    config_path = Path(f"config/screens/{config_filename}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_setup_function(setup_name: str):
    """Get setup function by name."""
    return SETUPS.get(setup_name)


def run_backtest(
    setup_name: str,
    universe_path: str,
    start_date: str,
    end_date: str,
    exit_rules: ExitRules,
    portfolio_rules: PortfolioRules,
    cache_dir: str = ".cache/research",
    output_dir: str = "docs/backtests/research"
) -> tuple[list[Trade], pd.Series, dict[str, pd.DataFrame], dict[str, pd.Series], BacktestMetrics]:
    """Run full backtest for a setup."""
    
    print(f"\n{'='*60}")
    print(f"Running {setup_name} backtest")
    print(f"Universe: {universe_path}")
    print(f"Period: {start_date} to {end_date}")
    print(f"{'='*60}")
    
    # Load universe
    symbols = load_universe(universe_path)
    print(f"Loaded {len(symbols)} symbols from universe")
    
    # Add SPY for benchmark
    if "SPY" not in symbols:
        symbols.append("SPY")
    
    # Download data
    print("Downloading data...")
    data, dropped = download_daily(symbols, start_date, end_date, cache_dir)
    print(f"Downloaded data for {len(data)} symbols")
    if dropped:
        print(f"Dropped {len(dropped)} symbols: {[d[0] for d in dropped]}")
    
    # Add indicators
    print("Adding indicators...")
    for symbol, df in data.items():
        data[symbol] = add_indicators(df)
    print("Indicators added")
    
    # Get setup function
    setup_fn = get_setup_function(setup_name)
    if setup_fn is None:
        raise ValueError(f"Unknown setup: {setup_name}")
    
    # Load config for eligibility
    config = load_setup_config(setup_name)
    
    # Generate signals
    print("Generating signals...")
    signals = {}
    for symbol, df in data.items():
        if symbol in ("SPY", "VIX"):
            signals[symbol] = pd.Series(False, index=df.index)
            continue
            
        # Check eligibility
        if not eligible(df).any():
            signals[symbol] = pd.Series(False, index=df.index)
            continue
            
        # Generate setup signals
        sig = setup_fn(df)
        signals[symbol] = sig
        
        n_signals = sig.sum()
        if n_signals > 0:
            print(f"  {symbol}: {n_signals} signals")
    
    total_signals = sum(s.sum() for s in signals.values())
    print(f"Total signals: {total_signals}")
    
    # Run portfolio backtest
    print("Running portfolio backtest...")
    trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    print(f"Completed {len(trades)} trades")
    
    # Compute metrics
    # Get SPY returns for alpha/beta
    spy_returns = None
    if "SPY" in data:
        spy_returns = data["SPY"]["close"].pct_change()
    
    metrics = compute_metrics(trades, equity, benchmark_returns=spy_returns)
    print_metrics(metrics, f"{setup_name} Backtest Results")
    
    return trades, equity, data, signals, metrics


def run_controls(
    data: dict[str, pd.DataFrame],
    signals: dict[str, pd.Series],
    exit_rules: ExitRules,
    portfolio_rules: PortfolioRules,
    n_random: int = 100,
    n_permuted: int = 50,
    n_shifted: int = 5
) -> dict[str, list]:
    """Run control suite."""
    print(f"\n{'='*60}")
    print(f"Running Control Suite")
    print(f"Random: {n_random}, Permuted: {n_permuted}, Shifted: {n_shifted}")
    print(f"{'='*60}")
    
    control_results = run_control_suite(
        data, signals, exit_rules, portfolio_rules,
        n_random=n_random,
        n_permuted=n_permuted,
        n_shifted=n_shifted,
        base_seed=42
    )
    
    # Summarize
    for ctype, results in control_results.items():
        if results:
            r_net_sums = [r.metrics.r_net_sum for r in results]
            sharpes = [r.metrics.sharpe for r in results]
            returns = [r.metrics.total_return_pct for r in results]
            print(f"\n{ctype.upper()} ({len(results)} runs):")
            print(f"  R-net Sum:  mean={np.mean(r_net_sums):.3f}, std={np.std(r_net_sums):.3f}, "
                  f"min={np.min(r_net_sums):.3f}, max={np.max(r_net_sums):.3f}")
            print(f"  Sharpe:     mean={np.mean(sharpes):.3f}, std={np.std(sharpes):.3f}")
            print(f"  Return %:   mean={np.mean(returns):.1f}%, std={np.std(returns):.1f}%")
    
    return control_results


def save_results(
    setup_name: str,
    trades: list[Trade],
    equity: pd.Series,
    metrics: BacktestMetrics,
    control_results: dict[str, list],
    pvalues: dict[str, float],
    output_dir: str = "docs/backtests/research"
) -> str:
    """Save results to JSON."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{setup_name}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Convert trades to serializable format
    trades_data = []
    for t in trades:
        trades_data.append({
            "symbol": t.symbol,
            "signal_date": t.signal_date.isoformat() if isinstance(t.signal_date, pd.Timestamp) else str(t.signal_date),
            "entry_date": t.entry_date.isoformat() if isinstance(t.entry_date, pd.Timestamp) else str(t.entry_date),
            "entry_price": float(t.entry_price),
            "stop": float(t.stop),
            "target": float(t.target),
            "shares": int(t.shares),
            "exit_date": t.exit_date.isoformat() if isinstance(t.exit_date, pd.Timestamp) else str(t.exit_date),
            "exit_price": float(t.exit_price),
            "exit_reason": t.exit_reason,
            "bars_held": int(t.bars_held),
            "r_gross": float(t.r_gross),
            "r_net": float(t.r_net),
            "pnl_usd": float(t.pnl_usd),
            "censored": bool(t.censored)
        })
    
    # Equity curve
    equity_data = [
        {"date": d.isoformat(), "equity": float(e)}
        for d, e in equity.items()
    ]
    
    # Control summary
    control_summary = {}
    for ctype, results in control_results.items():
        if results:
            control_summary[ctype] = {
                "n_runs": len(results),
                "r_net_sum_mean": float(np.mean([r.metrics.r_net_sum for r in results])),
                "r_net_sum_std": float(np.std([r.metrics.r_net_sum for r in results])),
                "sharpe_mean": float(np.mean([r.metrics.sharpe for r in results])),
                "sharpe_std": float(np.std([r.metrics.sharpe for r in results])),
                "return_mean": float(np.mean([r.metrics.total_return_pct for r in results])),
                "return_std": float(np.std([r.metrics.total_return_pct for r in results])),
            }
    
    result = {
        "setup": setup_name,
        "timestamp": timestamp,
        "metrics": metrics_to_dict(metrics),
        "trades": trades_data,
        "equity_curve": equity_data,
        "control_summary": control_summary,
        "p_values": pvalues
    }
    
    with open(filepath, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\nResults saved to: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Run research baseline backtest")
    parser.add_argument("--setup", default="statistical_mean_reversion",
                        choices=list(SETUPS.keys()),
                        help="Setup name to test")
    parser.add_argument("--universe", default="config/replay_universe_sp500.txt",
                        help="Path to universe file")
    parser.add_argument("--start", default="2015-01-01",
                        help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31",
                        help="End date (YYYY-MM-DD)")
    parser.add_argument("--stop-atr", type=float, default=2.0,
                        help="Stop loss ATR multiplier")
    parser.add_argument("--target-atr", type=float, default=3.0,
                        help="Target ATR multiplier")
    parser.add_argument("--max-hold", type=int, default=15,
                        help="Max hold bars")
    parser.add_argument("--risk-pct", type=float, default=0.5,
                        help="Risk percent per trade")
    parser.add_argument("--max-positions", type=int, default=8,
                        help="Max concurrent positions")
    parser.add_argument("--cost-bps", type=float, default=15.0,
                        help="Cost basis points per side")
    parser.add_argument("--n-random", type=int, default=100,
                        help="Number of random control runs")
    parser.add_argument("--n-permuted", type=int, default=50,
                        help="Number of permuted control runs")
    parser.add_argument("--n-shifted", type=int, default=5,
                        help="Number of time-shifted control runs")
    parser.add_argument("--cache-dir", default=".cache/research",
                        help="Cache directory")
    parser.add_argument("--output-dir", default="docs/backtests/research",
                        help="Output directory")
    parser.add_argument("--no-controls", action="store_true",
                        help="Skip control suite")
    
    args = parser.parse_args()
    
    # Print configuration
    print(f"\n{'='*60}")
    print(f"RESEARCH BASELINE BACKTEST")
    print(f"{'='*60}")
    print(f"Setup:         {args.setup}")
    print(f"Universe:      {args.universe}")
    print(f"Date Range:    {args.start} to {args.end}")
    print(f"Stop ATR:      {args.stop_atr}")
    print(f"Target ATR:    {args.target_atr}")
    print(f"Max Hold:      {args.max_hold}")
    print(f"Risk %:        {args.risk_pct}%")
    print(f"Max Positions: {args.max_positions}")
    print(f"Cost BPS:      {args.cost_bps}")
    print(f"{'='*60}")
    
    # Create rules
    exit_rules = ExitRules(
        stop_atr=args.stop_atr,
        target_atr=args.target_atr,
        max_hold_bars=args.max_hold
    )
    
    portfolio_rules = PortfolioRules(
        start_equity=100_000.0,
        risk_pct=args.risk_pct,
        max_positions=args.max_positions,
        max_position_pct=20.0,
        cost_bps_per_side=args.cost_bps
    )
    
    # Run backtest
    trades, equity, data, signals, metrics = run_backtest(
        args.setup,
        args.universe,
        args.start,
        args.end,
        exit_rules,
        portfolio_rules,
        args.cache_dir,
        args.output_dir
    )
    
    # Run controls
    pvalues = {}
    control_results = {}
    
    if not args.no_controls:
        control_results = run_controls(
            data, signals, exit_rules, portfolio_rules,
            n_random=args.n_random,
            n_permuted=args.n_permuted,
            n_shifted=args.n_shifted
        )
        
        # Compute p-values
        pvalues = compute_control_pvalues(metrics, control_results, "r_net_sum")
        print(f"\n{'='*60}")
        print(f"P-VALUES (vs R-net Sum)")
        print(f"{'='*60}")
        for ctype, p in pvalues.items():
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"  {ctype:12s}: p = {p:.4f} {sig}")
        
        pvalues_sharpe = compute_control_pvalues(metrics, control_results, "sharpe")
        print(f"\nP-VALUES (vs Sharpe)")
        print(f"{'='*60}")
        for ctype, p in pvalues_sharpe.items():
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"  {ctype:12s}: p = {p:.4f} {sig}")
    
    # Save results
    save_results(
        args.setup,
        trades,
        equity,
        metrics,
        control_results,
        pvalues,
        args.output_dir
    )
    
    print(f"\n{'='*60}")
    print(f"BACKTEST COMPLETE")
    print(f"{'='*60}")
    
    # Return exit code based on significance
    if pvalues:
        min_p = min(pvalues.values())
        if min_p < 0.05:
            print("RESULT: Statistically significant vs controls (p < 0.05)")
            return 0
        else:
            print("RESULT: NOT statistically significant vs controls (p >= 0.05)")
            return 1
    else:
        print("RESULT: No controls run")
        return 0


if __name__ == "__main__":
    sys.exit(main())
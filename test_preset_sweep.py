import sys
sys.path.insert(0, '.')

import asyncio
from backend.app.infrastructure.backtest.filter_sweep import PRESET_SWEEPS
from backend.app.infrastructure.backtest.filter_sweep_engine import FilterSweepEngine

async def test_preset_sweep():
    # Run the trend_follower_optimization preset
    preset = PRESET_SWEEPS['trend_follower_optimization']
    print(f"Running preset: {preset.name}")
    print(f"Screen: {preset.screen_name}")
    print(f"Original symbols: {preset.symbols}")
    print(f"Params: {list(preset.param_grid.keys())}")
    
    # Use only symbols that exist in DB
    available_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
    
    from backend.app.infrastructure.backtest.filter_sweep import FilterSweepConfig, FilterParamRange
    
    # Filter param grid to only include params for available technical filters
    # The preset has fundamental filters which we can't use
    tech_param_grid = {}
    for name, param_range in preset.param_grid.items():
        # Skip fundamental filters
        if name not in ['market_cap_gt', 'exchange_in', 'country_in', 'close_above', 'eps_positive', 'pe_max']:
            tech_param_grid[name] = param_range
    
    print(f"\nTechnical params to sweep: {list(tech_param_grid.keys())}")
    
    config = FilterSweepConfig(
        sweep_id='preset_test_1',
        name='Preset Trend Follower Sweep',
        description='Running trend_follower_optimization preset with technical filters only',
        screen_name=preset.screen_name,
        param_grid=tech_param_grid,
        symbols=available_symbols,
        timeframe='1D',
        start_date='2025-06-01',
        end_date='2026-06-01',
        initial_cash=100_000,
        fees_bps=10,
        slippage_bps=5,
        position_sizing='fixed',
        sizing_params={},
        optimization_metric='expectancy',
        max_combinations=50,
        parallel_jobs=1,
    )
    
    engine = FilterSweepEngine()
    
    def progress_callback(progress):
        print(f"Progress: {progress.completed}/{progress.total_combinations} - Current: {progress.current_params}")
    
    print("Starting preset sweep...")
    summary = await engine.run_sweep(config, progress_callback)
    
    print(f"\nSweep completed!")
    print(f"Total combinations: {summary.total_combinations}")
    print(f"Valid results: {summary.valid_results}")
    print(f"Failed: {summary.failed_results}")
    print(f"Status: {summary.status}")
    print(f"Duration: {summary.duration_ms/1000:.1f}s")
    
    if summary.valid_results > 0:
        print(f"\n=== BEST RESULTS ===")
        
        print(f"\nBest by Expectancy:")
        if summary.best_by_expectancy:
            be = summary.best_by_expectancy
            print(f"  Params: {be.get('params')}")
            print(f"  Expectancy: {be.get('expectancy'):.2f}")
            print(f"  Sharpe: {be.get('sharpe'):.4f}")
            print(f"  Win Rate: {be.get('win_rate'):.2%}")
            print(f"  Profit Factor: {be.get('profit_factor'):.2f}")
            print(f"  Total Trades: {be.get('total_trades')}")
            print(f"  Avg Hold Days: {be.get('avg_hold_days'):.1f}")
        
        print(f"\nBest by Sharpe:")
        if summary.best_by_sharpe:
            bs = summary.best_by_sharpe
            print(f"  Params: {bs.get('params')}")
            print(f"  Expectancy: {bs.get('expectancy'):.2f}")
            print(f"  Sharpe: {bs.get('sharpe'):.4f}")
            print(f"  Win Rate: {bs.get('win_rate'):.2%}")
            print(f"  Total Trades: {bs.get('total_trades')}")
        
        print(f"\nBest by Win Rate:")
        if summary.best_by_win_rate:
            bw = summary.best_by_win_rate
            print(f"  Params: {bw.get('params')}")
            print(f"  Win Rate: {bw.get('win_rate'):.2%}")
            print(f"  Expectancy: {bw.get('expectancy'):.2f}")
            print(f"  Total Trades: {bw.get('total_trades')}")
        
        print(f"\nBest by Profit Factor:")
        if summary.best_by_profit_factor:
            bpf = summary.best_by_profit_factor
            print(f"  Params: {bpf.get('params')}")
            print(f"  Profit Factor: {bpf.get('profit_factor'):.2f}")
            print(f"  Expectancy: {bpf.get('expectancy'):.2f}")
            print(f"  Total Trades: {bpf.get('total_trades')}")
        
        # Show parameter sensitivity
        if summary.param_sensitivity:
            print(f"\n=== PARAMETER SENSITIVITY ===")
            for param, metrics in summary.param_sensitivity.items():
                print(f"\n{param}:")
                for metric, sensitivity in metrics.items():
                    print(f"  {metric}: {sensitivity:.4f}")

if __name__ == '__main__':
    asyncio.run(test_preset_sweep())
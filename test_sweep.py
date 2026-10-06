import sys
sys.path.insert(0, '.')

import asyncio
from backend.app.infrastructure.backtest.filter_sweep import FilterSweepConfig, FilterParamRange, PRESET_SWEEPS
from backend.app.infrastructure.backtest.filter_sweep_engine import FilterSweepEngine

async def test_sweep():
    # Use a small subset of symbols and combinations
    preset = PRESET_SWEEPS['trend_follower_optimization']
    print(f"Preset: {preset.name}")
    print(f"Screen: {preset.screen_name}")
    print(f"Original symbols: {preset.symbols}")
    print(f"Params: {list(preset.param_grid.keys())}")
    
    # Use only symbols that exist in DB
    available_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
    
    config = FilterSweepConfig(
        sweep_id='test_sweep_1',
        name='Test Trend Follower Sweep',
        description='Test sweep with available symbols',
        screen_name=preset.screen_name,
        param_grid=preset.param_grid,
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
        max_combinations=10,  # Limit for quick test
        parallel_jobs=1,
    )
    
    engine = FilterSweepEngine()
    
    def progress_callback(progress):
        print(f"Progress: {progress.completed}/{progress.total_combinations} - Current: {progress.current_params}")
    
    print("Starting sweep...")
    summary = await engine.run_sweep(config, progress_callback)
    
    print(f"\nSweep completed!")
    print(f"Total: {summary.total_combinations}")
    print(f"Valid: {summary.valid_results}")
    print(f"Failed: {summary.failed_results}")
    print(f"Status: {summary.status}")
    
    if summary.valid_results > 0:
        print(f"\nBest by Expectancy: {summary.best_by_expectancy}")
        print(f"Best by Sharpe: {summary.best_by_sharpe}")
        print(f"Best by Win Rate: {summary.best_by_win_rate}")
        print(f"Best by Profit Factor: {summary.best_by_profit_factor}")
        print(f"Best by Calmar: {summary.best_by_calmar}")

if __name__ == '__main__':
    asyncio.run(test_sweep())
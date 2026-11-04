import sys
sys.path.insert(0, '.')

import asyncio
from backend.app.infrastructure.backtest.filter_sweep import FilterSweepConfig, FilterParamRange
from backend.app.infrastructure.backtest.filter_sweep_engine import FilterSweepEngine

async def test_sweep():
    # Create a config with ONLY technical filters (no fundamental data needed)
    param_grid = {
        "rvol_high": FilterParamRange(
            name="rvol_high",
            display_name="RVOL High",
            param_type="float",
            low=1.0,
            high=2.0,
            step=0.2,
            description="Relative volume threshold"
        ),
        "avg_volume_gt": FilterParamRange(
            name="avg_volume_gt",
            display_name="Avg Volume >",
            param_type="int",
            low=500000,
            high=5000000,
            step=1000000,
            description="Average daily volume minimum"
        ),
        "price_above_ema": FilterParamRange(
            name="price_above_ema",
            display_name="Price Above EMA",
            param_type="int",
            low=20,
            high=200,
            step=20,
            description="EMA period for price above check"
        ),
        "adx_trending": FilterParamRange(
            name="adx_trending",
            display_name="ADX Trending",
            param_type="int",
            low=15,
            high=35,
            step=5,
            description="ADX threshold for trending"
        ),
        "bb_squeeze": FilterParamRange(
            name="bb_squeeze",
            display_name="BB Squeeze",
            param_type="float",
            low=0.05,
            high=0.20,
            step=0.05,
            description="Bollinger Band squeeze threshold"
        ),
    }
    
    config = FilterSweepConfig(
        sweep_id='tech_test_1',
        name='Technical Filters Sweep',
        description='Sweep using only technical filters (no fundamental data needed)',
        screen_name='trend-follower',  # We'll use the template but override filters
        param_grid=param_grid,
        symbols=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA'],
        timeframe='1D',
        start_date='2025-06-01',
        end_date='2026-06-01',
        initial_cash=100_000,
        fees_bps=10,
        slippage_bps=5,
        position_sizing='fixed',
        sizing_params={},
        optimization_metric='expectancy',
        max_combinations=20,
        parallel_jobs=1,
    )
    
    engine = FilterSweepEngine()
    
    def progress_callback(progress):
        print(f"Progress: {progress.completed}/{progress.total_combinations} - Current: {progress.current_params}")
    
    print("Starting technical-only sweep...")
    summary = await engine.run_sweep(config, progress_callback)
    
    print(f"\nSweep completed!")
    print(f"Total: {summary.total_combinations}")
    print(f"Valid: {summary.valid_results}")
    print(f"Failed: {summary.failed_results}")
    print(f"Status: {summary.status}")
    
    if summary.valid_results > 0:
        print(f"\nBest by Expectancy:")
        if summary.best_by_expectancy:
            print(f"  Params: {summary.best_by_expectancy.get('params')}")
            print(f"  Expectancy: {summary.best_by_expectancy.get('expectancy')}")
            print(f"  Sharpe: {summary.best_by_expectancy.get('sharpe')}")
            print(f"  Win Rate: {summary.best_by_expectancy.get('win_rate')}")
            print(f"  Trades: {summary.best_by_expectancy.get('total_trades')}")
        
        print(f"\nBest by Sharpe:")
        if summary.best_by_sharpe:
            print(f"  Params: {summary.best_by_sharpe.get('params')}")
            print(f"  Expectancy: {summary.best_by_sharpe.get('expectancy')}")
            print(f"  Sharpe: {summary.best_by_sharpe.get('sharpe')}")
            print(f"  Win Rate: {summary.best_by_sharpe.get('win_rate')}")
            print(f"  Trades: {summary.best_by_sharpe.get('total_trades')}")

if __name__ == '__main__':
    asyncio.run(test_sweep())
import sys
sys.path.insert(0, '.')

import asyncio
from backend.app.infrastructure.backtest.filter_sweep import PRESET_SWEEPS
from backend.app.infrastructure.backtest.filter_sweep_engine import FilterSweepEngine

async def test():
    preset = PRESET_SWEEPS['vcp_breakout_optimization']
    print(f'Running preset: {preset.name}')
    print(f'Params: {list(preset.param_grid.keys())}')
    
    engine = FilterSweepEngine()
    def progress(p):
        print(f'  Progress: {p.completed}/{p.total_combinations}')
    
    summary = await engine.run_sweep(preset, progress)
    
    print(f'Completed: {summary.valid_results}/{summary.total_combinations} valid')
    if summary.valid_results > 0:
        be = summary.best_by_expectancy
        print(f'Best Expectancy: {be["expectancy"]:.2f}')
        bs = summary.best_by_sharpe
        print(f'Best Sharpe: {bs["sharpe"]:.3f}')
        bw = summary.best_by_win_rate
        print(f'Best Win Rate: {bw["win_rate"]:.1%}')
        bpf = summary.best_by_profit_factor
        print(f'Best Profit Factor: {bpf["profit_factor"]:.2f}')

asyncio.run(test())
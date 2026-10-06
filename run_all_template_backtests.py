import sys
sys.path.insert(0, '.')

import asyncio
import json
from datetime import datetime
from backend.app.infrastructure.backtest.filter_sweep import FilterSweepConfig, FilterParamRange, PRESET_SWEEPS, DEFAULT_FILTER_PARAM_RANGES
from backend.app.infrastructure.backtest.filter_sweep_engine import FilterSweepEngine
from backend.app.infrastructure.screener.configs import load_screen_template

# Available symbols in DB
AVAILABLE_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']

# All template names
ALL_TEMPLATES = [
    'trend-follower',
    'high-conviction-stack',
    'bull-flag-continuation',
    'statistical-mean-reversion',
    'institutional-swing-quality',
    'trend-leader',
    'quality-trend-fundamentals',
    'volatility-expansion',
    '52week-breakout',
    'breakdown',
    'mean-reversion',
    'short-squeeze',
    'volume-trend-accumulation'
]

# Fundamental filter names to skip (we don't have fundamental data)
FUNDAMENTAL_FILTERS = {
    'market_cap_gt', 'exchange_in', 'country_in', 'close_above', 
    'eps_positive', 'pe_max', 'analyst_rating_in'
}

# Map filter indicator names to default param ranges
FILTER_TO_PARAM_RANGE = {
    'avg_volume_gt': DEFAULT_FILTER_PARAM_RANGES['avg_volume_gt'],
    'rvol_high': DEFAULT_FILTER_PARAM_RANGES['rvol_high'],
    'adx_trending': DEFAULT_FILTER_PARAM_RANGES['adx_trending'],
    'price_above_ema': DEFAULT_FILTER_PARAM_RANGES['price_above_ema'],
    'rsi_in_range': DEFAULT_FILTER_PARAM_RANGES['rsi_in_range'],
    'rsi_in_range_max': DEFAULT_FILTER_PARAM_RANGES['rsi_in_range_max'],
    'rsi_oversold': DEFAULT_FILTER_PARAM_RANGES['rsi_oversold'],
    'cci_oversold': DEFAULT_FILTER_PARAM_RANGES['cci_oversold'],
    'atr_pct_below': DEFAULT_FILTER_PARAM_RANGES['atr_pct_below'],
    'bb_squeeze': DEFAULT_FILTER_PARAM_RANGES['bb_squeeze'],
    'volume_gt': DEFAULT_FILTER_PARAM_RANGES['volume_gt'],
    'ema_stack_bullish': FilterParamRange(
        name="ema_stack_bullish",
        display_name="EMA Stack Bullish",
        param_type="categorical",
        choices=["true", "false"],
        description="EMA stack bullish alignment (EMA20>EMA50>EMA200).",
    ),
    'macd_bullish': FilterParamRange(
        name="macd_bullish",
        display_name="MACD Bullish",
        param_type="categorical",
        choices=["true", "false"],
        description="MACD bullish crossover.",
    ),
    'price_above_vwap': FilterParamRange(
        name="price_above_vwap",
        display_name="Price Above VWAP",
        param_type="categorical",
        choices=["true", "false"],
        description="Price above VWAP.",
    ),
    'obv_rising': FilterParamRange(
        name="obv_rising",
        display_name="OBV Rising",
        param_type="categorical",
        choices=["true", "false"],
        description="On Balance Volume rising.",
    ),
}

async def run_template_backtest(template_name: str, max_combinations: int = 30):
    """Run a backtest sweep for a single template."""
    print(f"\n{'='*60}")
    print(f"Running backtest for: {template_name}")
    print(f"{'='*60}")
    
    try:
        # Load template
        template = load_screen_template(template_name)
        
        # Build param_grid from template's technical filters
        tech_param_grid = {}
        for filter_rule in template.filters:
            indicator = filter_rule.indicator
            if indicator not in FUNDAMENTAL_FILTERS and indicator in FILTER_TO_PARAM_RANGE:
                tech_param_grid[indicator] = FILTER_TO_PARAM_RANGE[indicator]
        
        if not tech_param_grid:
            print(f"  No technical filters to sweep for {template_name}")
            return None
        
        print(f"  Technical filters: {list(tech_param_grid.keys())}")
        
        config = FilterSweepConfig(
            sweep_id=f'{template_name}_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            name=f'{template_name} Backtest',
            description=f'Backtest sweep for {template_name} template',
            screen_name=template_name,
            param_grid=tech_param_grid,
            symbols=AVAILABLE_SYMBOLS,
            timeframe='1D',
            start_date='2025-06-01',
            end_date='2026-06-01',
            initial_cash=100_000,
            fees_bps=10,
            slippage_bps=5,
            position_sizing='fixed',
            sizing_params={},
            optimization_metric='expectancy',
            max_combinations=max_combinations,
            parallel_jobs=1,
        )
        
        engine = FilterSweepEngine()
        
        def progress_callback(progress):
            pass  # Silent for batch runs
        
        summary = await engine.run_sweep(config, progress_callback)
        
        # Extract key metrics
        result = {
            'template': template_name,
            'total_combinations': summary.total_combinations,
            'valid_results': summary.valid_results,
            'failed_results': summary.failed_results,
            'status': summary.status,
        }
        
        if summary.valid_results > 0:
            # Best by expectancy
            be = summary.best_by_expectancy
            if be:
                result['best_expectancy'] = {
                    'params': be.get('params'),
                    'expectancy': be.get('expectancy'),
                    'sharpe': be.get('sharpe'),
                    'win_rate': be.get('win_rate'),
                    'profit_factor': be.get('profit_factor'),
                    'total_trades': be.get('total_trades'),
                    'avg_hold_days': be.get('avg_hold_days'),
                }
            
            # Best by sharpe
            bs = summary.best_by_sharpe
            if bs:
                result['best_sharpe'] = {
                    'params': bs.get('params'),
                    'expectancy': bs.get('expectancy'),
                    'sharpe': bs.get('sharpe'),
                    'win_rate': bs.get('win_rate'),
                    'profit_factor': bs.get('profit_factor'),
                    'total_trades': bs.get('total_trades'),
                }
            
            # Best by win rate
            bw = summary.best_by_win_rate
            if bw:
                result['best_win_rate'] = {
                    'params': bw.get('params'),
                    'win_rate': bw.get('win_rate'),
                    'expectancy': bw.get('expectancy'),
                    'total_trades': bw.get('total_trades'),
                }
            
            # Best by profit factor
            bpf = summary.best_by_profit_factor
            if bpf:
                result['best_profit_factor'] = {
                    'params': bpf.get('params'),
                    'profit_factor': bpf.get('profit_factor'),
                    'expectancy': bpf.get('expectancy'),
                    'total_trades': bpf.get('total_trades'),
                }
        
        return result
        
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {'template': template_name, 'error': str(e)}

async def main():
    print("Running backtests for all 13 screen templates...")
    print(f"Symbols: {AVAILABLE_SYMBOLS}")
    print(f"Date range: 2025-06-01 to 2026-06-01")
    
    all_results = {}
    
    for template_name in ALL_TEMPLATES:
        result = await run_template_backtest(template_name, max_combinations=30)
        all_results[template_name] = result
        
        if result and 'best_expectancy' in result:
            be = result['best_expectancy']
            print(f"  OK {template_name}: Valid={result['valid_results']}, Best Expectancy={be['expectancy']:.2f}, Sharpe={be['sharpe']:.3f}, WR={be['win_rate']:.1%}, PF={be['profit_factor']:.2f}, Trades={be['total_trades']}")
        elif result:
            print(f"  FAIL {template_name}: Valid={result.get('valid_results', 0)}, Error={result.get('error', 'No valid results')}")
        else:
            print(f"  FAIL {template_name}: Failed completely")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"backtest_results_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n\nResults saved to: {output_file}")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"{'Template':<30} {'Valid':<6} {'Expectancy':<12} {'Sharpe':<8} {'WinRate':<10} {'ProfitFac':<10} {'Trades':<8}")
    print("-"*80)
    
    for template_name, result in all_results.items():
        if result and 'best_expectancy' in result:
            be = result['best_expectancy']
            print(f"{template_name:<30} {result['valid_results']:<6} {be['expectancy']:<12.2f} {be['sharpe']:<8.3f} {be['win_rate']:<10.1%} {be['profit_factor']:<10.2f} {be['total_trades']:<8}")
        elif result:
            print(f"{template_name:<30} {result.get('valid_results', 0):<6} {'N/A':<12} {'N/A':<8} {'N/A':<10} {'N/A':<10} {'N/A':<8}")
        else:
            print(f"{template_name:<30} {'ERR':<6} {'N/A':<12} {'N/A':<8} {'N/A':<10} {'N/A':<10} {'N/A':<8}")
    
    return all_results

if __name__ == '__main__':
    asyncio.run(main())
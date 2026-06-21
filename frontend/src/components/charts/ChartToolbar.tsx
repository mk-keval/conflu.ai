import { useChartStore } from '@/store/chart';
import { cn } from '@/lib/cn';

const INDICATOR_BUTTONS = [
  { key: 'rsi', label: 'RSI' },
  { key: 'macd', label: 'MACD' },
  { key: 'ema_20', label: 'EMA 20' },
  { key: 'bb', label: 'BB' },
];

const TIMEFRAME_BUTTONS = ['1D', '4H', '1H', '15m'];

export function ChartToolbar() {
  const { activeIndicators, activeTimeframes, toggleIndicator, toggleTimeframe } =
    useChartStore();

  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-1">
        <span className="mr-1 text-xs text-dark-300">TF:</span>
        {TIMEFRAME_BUTTONS.map((tf) => (
          <button
            key={tf}
            onClick={() => toggleTimeframe(tf)}
            className={cn(
              'rounded px-2 py-1 text-xs font-medium transition-colors',
              activeTimeframes.includes(tf)
                ? 'bg-accent text-white'
                : 'bg-dark-600 text-dark-300 hover:bg-dark-500'
            )}
          >
            {tf}
          </button>
        ))}
      </div>

      <div className="h-4 w-px bg-dark-500" />

      <div className="flex items-center gap-1">
        <span className="mr-1 text-xs text-dark-300">Indicators:</span>
        {INDICATOR_BUTTONS.map((ind) => (
          <button
            key={ind.key}
            onClick={() => toggleIndicator(ind.key)}
            className={cn(
              'rounded px-2 py-1 text-xs font-medium transition-colors',
              activeIndicators.includes(ind.key)
                ? 'bg-accent/20 text-accent-light'
                : 'bg-dark-600 text-dark-300 hover:bg-dark-500'
            )}
          >
            {ind.label}
          </button>
        ))}
      </div>
    </div>
  );
}

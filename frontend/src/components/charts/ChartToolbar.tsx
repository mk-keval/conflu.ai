import { useChartStore } from '@/store/chart';
import { cn } from '@/lib/cn';
import { EducationTooltip } from '@/components/professional/EducationTooltip';

const INDICATOR_BUTTONS = [
  { key: 'rsi', label: 'RSI', lesson: 'rsi' },
  { key: 'macd', label: 'MACD', lesson: 'macd_status' },
  { key: 'ema_20', label: 'EMA 20', lesson: 'ma_alignment' },
  { key: 'bb', label: 'BB', lesson: 'bb_position' },
];

const TIMEFRAME_BUTTONS = ['1D', '4H', '1H', '15m'];

export function ChartToolbar() {
  const {
    activeIndicators,
    activeTimeframes,
    toggleIndicator,
    toggleTimeframe,
  } = useChartStore();

  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-1">
        <span className="mr-1 text-xs text-text-muted">TF:</span>
        {TIMEFRAME_BUTTONS.map((tf) => (
          <button
            key={tf}
            onClick={() => toggleTimeframe(tf)}
            className={cn(
              'rounded px-2 py-1 text-xs font-medium transition-colors',
              activeTimeframes.includes(tf)
                ? 'bg-accent text-white'
                : 'bg-surface-hover text-text-muted hover:bg-surface-hover/70'
            )}
          >
            {tf}
          </button>
        ))}
      </div>

      <div className="h-4 w-px bg-border/50" />

      <div className="flex items-center gap-1">
        <span className="mr-1 text-xs text-text-muted">Indicators:</span>
        {INDICATOR_BUTTONS.map((ind) => (
          <span key={ind.key} className="inline-flex items-center gap-0.5">
            <button
              onClick={() => toggleIndicator(ind.key)}
              className={cn(
                'rounded px-2 py-1 text-xs font-medium transition-colors',
                activeIndicators.includes(ind.key)
                  ? 'bg-accent/15 text-accent'
                  : 'bg-surface-hover text-text-muted hover:bg-surface-hover/70'
              )}
            >
              {ind.label}
            </button>
            <EducationTooltip
              metricKey={ind.lesson}
              metricLabel={ind.label}
              compact
              position="bottom"
            />
          </span>
        ))}
      </div>
    </div>
  );
}

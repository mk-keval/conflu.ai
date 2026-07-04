import { useChartStore } from '@/store/chart';
import { formatNumber } from '@/lib/format';
import { cn } from '@/lib/cn';
import { INDICATOR_COLORS } from '@/lib/constants';

interface IndicatorPanelProps {
  symbol: string;
  indicatorValues: Record<string, number | null>;
}

const INDICATOR_LABELS: Record<string, string> = {
  rsi: 'RSI (14)',
  macd: 'MACD',
  ema_20: 'EMA (20)',
  bb: 'Bollinger Bands',
};

function getIndicatorZone(name: string, value: number): 'bullish' | 'bearish' | 'neutral' {
  if (name === 'rsi') {
    if (value > 70) return 'bearish';
    if (value < 30) return 'bullish';
    return 'neutral';
  }
  if (value > 0) return 'bullish';
  if (value < 0) return 'bearish';
  return 'neutral';
}

const zoneColors = {
  bullish: 'text-gain',
  bearish: 'text-loss',
  neutral: 'text-yellow-400',
};

export function IndicatorPanel({ symbol, indicatorValues }: IndicatorPanelProps) {
  const { activeIndicators } = useChartStore();

  const hasValues = activeIndicators.some((ind) => indicatorValues[ind] != null);

  if (!hasValues) {
    return null;
  }

  return (
    <div className="w-48 border-l border-border bg-surface p-3 text-sm">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
        {symbol} — Indicators
      </h3>
      <div className="space-y-2">
        {activeIndicators.map((name) => {
          const value = indicatorValues[name];
          if (value == null) return null;

          const zone = getIndicatorZone(name, value);

          return (
            <div key={name} className="space-y-0.5">
              <div className="text-xs text-text-secondary">
                {INDICATOR_LABELS[name] || name}
              </div>
              <div
                className={cn(
                  'font-mono text-sm font-medium',
                  zoneColors[zone]
                )}
                style={{ color: INDICATOR_COLORS[name as keyof typeof INDICATOR_COLORS] || undefined }}
              >
                {formatNumber(value, 2)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

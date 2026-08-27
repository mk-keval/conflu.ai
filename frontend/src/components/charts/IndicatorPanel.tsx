import { useChartStore } from '@/store/chart';
import { formatNumber } from '@/lib/format';
import { cn } from '@/lib/cn';
import { INDICATOR_COLORS } from '@/lib/constants';
import { EducationTooltip } from '@/components/professional/EducationTooltip';

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

/** Chart indicator → education.json lesson key. */
const INDICATOR_LESSON_KEYS: Record<string, string> = {
  rsi: 'rsi',
  macd: 'macd_status',
  ema_20: 'ma_alignment',
  bb: 'bb_position',
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
          const lessonKey = INDICATOR_LESSON_KEYS[name];

          return (
            <div key={name} className="space-y-0.5">
              <div className="flex items-center gap-1 text-xs text-text-secondary">
                <span>{INDICATOR_LABELS[name] || name}</span>
                {lessonKey && (
                  <EducationTooltip
                    metricKey={lessonKey}
                    metricLabel={INDICATOR_LABELS[name] || name}
                    metricValue={String(value)}
                    compact
                  />
                )}
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

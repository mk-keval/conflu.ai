import { cn } from '@/lib/cn';
import { EducationTooltip } from './EducationTooltip';
import type { MarketInternals } from '@/types/professional';

interface MarketInternalsStripProps {
  internals: MarketInternals;
}

function InternalsItem({
  label,
  value,
  format = 'number',
  educationKey,
}: {
  label: string;
  value: number | null;
  format?: 'number' | 'decimal';
  educationKey: string;
}) {
  const isPositive = value !== null && value > 0;
  const isNegative = value !== null && value < 0;

  // VIX: <15=low fear, >30=high fear
  const isVIX = label === 'VIX';
  const vixStatus = isVIX && value !== null
    ? value > 30 ? 'high' : value > 20 ? 'medium' : 'low'
    : null;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface-tertiary/50">
      <span className="text-xs text-text-muted whitespace-nowrap">{label}</span>
      <span
        className={cn(
          'font-mono text-sm font-semibold',
          vixStatus === 'high' && 'text-red-400',
          vixStatus === 'medium' && 'text-yellow-400',
          vixStatus === 'low' && 'text-green-400',
          !vixStatus && isPositive && 'text-green-400',
          !vixStatus && isNegative && 'text-red-400',
          !vixStatus && value === null && 'text-text-muted'
        )}
      >
        {value !== null
          ? format === 'decimal'
            ? value.toFixed(2)
            : value.toFixed(1)
          : '--'}
      </span>
      <EducationTooltip metricKey={educationKey} compact />
    </div>
  );
}

export function MarketInternalsStrip({ internals }: MarketInternalsStripProps) {
  return (
    <div
      data-testid="market-internals"
      className="flex flex-wrap items-center gap-2"
    >
      <InternalsItem
        label="VIX"
        value={internals.vix}
        format="decimal"
        educationKey="vix"
      />
      <InternalsItem
        label="A/D"
        value={internals.advanceDeclineRatio}
        format="decimal"
        educationKey="advance_decline_ratio"
      />
      <InternalsItem
        label="$USD"
        value={internals.dollarIndex}
        format="decimal"
        educationKey="dollar_index"
      />
      <InternalsItem
        label="S&P 500"
        value={internals.sp500Futures}
        educationKey="sp500_futures"
      />
      <InternalsItem
        label="Nasdaq"
        value={internals.nasdaqFutures}
        educationKey="nasdaq_futures"
      />
    </div>
  );
}

import type { VaRResult } from '@/types/risk';
import { formatPct, formatNumber } from '@/lib/format';
import { cn } from '@/lib/cn';

interface VarGaugeProps {
  data: VaRResult | null;
  isLoading?: boolean;
  error?: string | null;
}

function GaugeBar({
  value,
  label,
  color,
}: {
  value: number;
  label: string;
  color: string;
}) {
  const absVal = Math.abs(value);
  const pct = Math.min(absVal * 5, 100); // Scale: 20% VaR = full bar

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-dark-300 text-xs">{label}</span>
        <span className={cn('font-mono text-sm font-bold', color)}>
          {formatPct(-absVal)}
        </span>
      </div>
      <div className="bg-dark-700 h-3 w-full overflow-hidden rounded-full">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            color.replace('text-', 'bg-').replace('text', 'bg')
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function VarGauge({ data, isLoading, error }: VarGaugeProps) {
  if (isLoading) {
    return (
      <div className="border-dark-600 bg-dark-800 space-y-4 rounded border p-4">
        <div className="bg-dark-600 h-4 w-24 animate-pulse rounded" />
        <div className="space-y-3">
          <div className="bg-dark-600 h-10 animate-pulse rounded" />
          <div className="bg-dark-600 h-10 animate-pulse rounded" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-dark-600 flex h-32 items-center justify-center rounded border text-sm text-loss">
        Error: {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="border-dark-600 text-dark-400 flex h-32 items-center justify-center rounded border border-dashed text-sm">
        No VaR data — select symbols first
      </div>
    );
  }

  return (
    <div className="border-dark-600 bg-dark-800 space-y-4 rounded border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-dark-100 text-xs font-semibold">Value at Risk</h3>
        <div className="text-dark-400 flex gap-2 text-[10px]">
          <span>Confidence: {formatNumber(data.confidence * 100, 0)}%</span>
          <span>Method: {data.method?.replace('_', ' ') ?? '—'}</span>
        </div>
      </div>

      <GaugeBar value={data.var} label="VaR" color="text-loss" />
      <GaugeBar
        value={data.cvar}
        label="CVaR (Expected Shortfall)"
        color="text-orange-400"
      />

      <div className="bg-dark-900 rounded px-3 py-2">
        <p className="text-dark-400 text-[11px]">
          At {formatNumber(data.confidence * 100, 0)}% confidence, the maximum
          expected loss over the given horizon is{' '}
          <span className="font-semibold text-loss">
            {formatPct(Math.abs(data.var))}
          </span>
          . In worst-case scenarios, average loss could reach{' '}
          <span className="font-semibold text-orange-400">
            {formatPct(Math.abs(data.cvar))}
          </span>
          .
        </p>
      </div>
    </div>
  );
}

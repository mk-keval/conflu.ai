import type { VaRResult } from '@/types/risk';
import { formatPct, formatNumber } from '@/lib/format';
import { cn } from '@/lib/cn';

interface VarGaugeProps {
  data: VaRResult | null;
  isLoading?: boolean;
  error?: string | null;
}

function GaugeBar({ value, label, color }: { value: number; label: string; color: string }) {
  const absVal = Math.abs(value);
  const pct = Math.min(absVal * 5, 100); // Scale: 20% VaR = full bar

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-dark-300">{label}</span>
        <span className={cn('font-mono text-sm font-bold', color)}>
          {formatPct(-absVal)}
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-dark-700">
        <div
          className={cn('h-full rounded-full transition-all duration-500', color.replace('text-', 'bg-').replace('text', 'bg'))}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function VarGauge({ data, isLoading, error }: VarGaugeProps) {
  if (isLoading) {
    return (
      <div className="space-y-4 rounded border border-dark-600 bg-dark-800 p-4">
        <div className="h-4 w-24 animate-pulse rounded bg-dark-600" />
        <div className="space-y-3">
          <div className="h-10 animate-pulse rounded bg-dark-600" />
          <div className="h-10 animate-pulse rounded bg-dark-600" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-32 items-center justify-center rounded border border-dark-600 text-sm text-loss">
        Error: {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-32 items-center justify-center rounded border border-dashed border-dark-600 text-sm text-dark-400">
        No VaR data — select symbols first
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded border border-dark-600 bg-dark-800 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-dark-100">
          Value at Risk
        </h3>
        <div className="flex gap-2 text-[10px] text-dark-400">
          <span>Confidence: {formatNumber(data.confidence * 100, 0)}%</span>
          <span>Method: {data.method?.replace('_', ' ') ?? '—'}</span>
        </div>
      </div>

      <GaugeBar value={data.var} label="VaR" color="text-loss" />
      <GaugeBar value={data.cvar} label="CVaR (Expected Shortfall)" color="text-orange-400" />

      <div className="rounded bg-dark-900 px-3 py-2">
        <p className="text-[11px] text-dark-400">
          At {formatNumber(data.confidence * 100, 0)}% confidence, the maximum expected loss over
          the given horizon is <span className="font-semibold text-loss">{formatPct(Math.abs(data.var))}</span>.
          In worst-case scenarios, average loss could reach{' '}
          <span className="font-semibold text-orange-400">{formatPct(Math.abs(data.cvar))}</span>.
        </p>
      </div>
    </div>
  );
}

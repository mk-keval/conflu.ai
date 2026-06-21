import type { KellyResult as KellyResultType } from '@/types/risk';
import { formatPct } from '@/lib/format';
import { cn } from '@/lib/cn';

interface KellyResultProps {
  data: KellyResultType | null;
  isLoading?: boolean;
  error?: string | null;
}

function KellyBar({ value, label, color }: { value: number; label: string; color: string }) {
  const pct = Math.min(Math.abs(value) * 2, 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-dark-300">{label}</span>
        <span className={cn('font-mono text-sm font-bold', color)}>
          {formatPct(value)}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-dark-700">
        <div
          className={cn('h-full rounded-full transition-all duration-500', color.replace('text-', 'bg-').replace('text', 'bg'))}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function KellyResult({ data, isLoading, error }: KellyResultProps) {
  if (isLoading) {
    return (
      <div className="space-y-3 rounded border border-dark-600 bg-dark-800 p-4">
        <div className="h-4 w-24 animate-pulse rounded bg-dark-600" />
        <div className="h-8 animate-pulse rounded bg-dark-600" />
        <div className="h-8 animate-pulse rounded bg-dark-600" />
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
        Run a Kelly calculation first
      </div>
    );
  }

  const conservativePct = data.kelly_pct > data.half_kelly_pct ? data.half_kelly_pct : data.kelly_pct;

  return (
    <div className="space-y-4 rounded border border-dark-600 bg-dark-800 p-4">
      <h3 className="text-xs font-semibold text-dark-100">Kelly Criterion</h3>

      <KellyBar
        value={data.kelly_pct}
        label="Full Kelly"
        color={data.kelly_pct > 0 ? 'text-gain' : 'text-loss'}
      />
      <KellyBar
        value={data.half_kelly_pct}
        label="Half Kelly (Conservative)"
        color={data.half_kelly_pct > 0 ? 'text-accent-light' : 'text-dark-400'}
      />

      <div className="grid grid-cols-2 gap-3 rounded bg-dark-900 p-3">
        <div>
          <p className="text-[10px] text-dark-400">Edge</p>
          <p className="font-mono text-sm font-semibold text-dark-50">
            {formatPct(data.edge)}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-dark-400">Odds</p>
          <p className="font-mono text-sm font-semibold text-dark-50">
            {data.odds.toFixed(2)}:1
          </p>
        </div>
      </div>

      <div className="rounded bg-dark-900 px-3 py-2">
        <p className="text-[11px] leading-relaxed text-dark-400">
          Recommended allocation:{' '}
          <span className={cn('font-semibold', conservativePct > 0 ? 'text-gain' : 'text-loss')}>
            {formatPct(conservativePct)}
          </span>{' '}
          of capital per trade (half-Kelly to reduce volatility).
          {data.kelly_pct <= 0 && (
            <span className="mt-1 block text-loss">
              ⚠ Negative Kelly suggests this strategy has no positive edge.
            </span>
          )}
        </p>
      </div>
    </div>
  );
}

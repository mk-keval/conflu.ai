import type { BetaResult } from '@/types/risk';
import { formatNumber } from '@/lib/format';
import { cn } from '@/lib/cn';

interface BetaCardsProps {
  data: BetaResult[];
  isLoading?: boolean;
  error?: string | null;
}

function betaColor(beta: number): string {
  if (beta < 0) return 'text-gain';
  if (beta < 0.5) return 'text-dark-100';
  if (beta < 1) return 'text-yellow-400';
  if (beta < 1.5) return 'text-orange-400';
  return 'text-loss';
}

function rSquaredColor(r2: number): string {
  if (r2 > 0.7) return 'text-gain';
  if (r2 > 0.4) return 'text-yellow-400';
  return 'text-dark-400';
}

export function BetaCards({ data, isLoading, error }: BetaCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded bg-dark-700" />
        ))}
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

  if (!data.length) {
    return (
      <div className="flex h-32 items-center justify-center rounded border border-dashed border-dark-600 text-sm text-dark-400">
        No beta data
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {data.map((item) => (
        <div
          key={item.symbol}
          className="rounded border border-dark-600 bg-dark-800 px-4 py-3"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-dark-100">{item.symbol}</span>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-dark-400">Beta</span>
              <span className={cn('font-mono text-sm font-bold', betaColor(item.beta))}>
                {formatNumber(item.beta, 3)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-dark-400">R²</span>
              <span className={cn('font-mono text-xs font-medium', rSquaredColor(item.r_squared))}>
                {formatNumber(item.r_squared, 3)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-dark-400">Tracking Error</span>
              <span className="font-mono text-xs text-dark-200">
                {formatNumber(item.tracking_error, 2)}%
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

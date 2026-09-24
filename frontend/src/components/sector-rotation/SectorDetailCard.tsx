import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  TrendingUp,
  DollarSign,
  BarChart3,
  Activity,
  Search,
} from 'lucide-react';
import { fetchSectorDetail } from '@/api/sectorRotation';
import type { SectorDetail } from '@/types/sector';
import { formatPrice, formatPct } from '@/lib/format';
import { cn } from '@/lib/cn';

interface SectorDetailCardProps {
  symbol: string;
  onClose: () => void;
}

export function SectorDetailCard({ symbol, onClose }: SectorDetailCardProps) {
  const navigate = useNavigate();
  const [detail, setDetail] = useState<SectorDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchSectorDetail(symbol)
      .then((data) => setDetail(data))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6">
        <div className="flex animate-pulse flex-col gap-4">
          <div className="h-6 w-48 rounded bg-surface-tertiary" />
          <div className="h-24 rounded bg-surface-tertiary" />
          <div className="h-32 rounded bg-surface-tertiary" />
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6">
        <p className="text-sm text-text-muted">
          Failed to load sector details.
        </p>
      </div>
    );
  }

  const perf = detail.performance;
  const { price_history } = detail;

  return (
    <div className="rounded-xl border border-border bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
            <span className="text-sm font-bold text-accent">{symbol}</span>
          </div>
          <div>
            <h2 className="text-lg font-bold text-text-primary">
              {detail.name}
            </h2>
            <p className="text-xs text-text-muted">{symbol}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Price + Change */}
      <div className="grid grid-cols-3 gap-4 border-b border-border px-5 py-4">
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-xs text-text-muted">
            <DollarSign className="h-3 w-3" /> Price
          </div>
          <span className="text-xl font-bold tabular-nums text-text-primary">
            {formatPrice(perf.price)}
          </span>
        </div>
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-xs text-text-muted">
            <TrendingUp className="h-3 w-3" /> 1 Day
          </div>
          <span
            className={cn(
              'text-lg font-bold tabular-nums',
              (perf.change_1d ?? 0) > 0
                ? 'text-gain'
                : (perf.change_1d ?? 0) < 0
                  ? 'text-loss'
                  : 'text-text-secondary'
            )}
          >
            {formatPct(perf.change_1d ?? 0)}
          </span>
        </div>
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-xs text-text-muted">
            <Activity className="h-3 w-3" /> 1 Week
          </div>
          <span
            className={cn(
              'text-lg font-bold tabular-nums',
              (perf.change_1w ?? 0) > 0
                ? 'text-gain'
                : (perf.change_1w ?? 0) < 0
                  ? 'text-loss'
                  : 'text-text-secondary'
            )}
          >
            {formatPct(perf.change_1w ?? 0)}
          </span>
        </div>
      </div>

      {/* Description */}
      <div className="border-b border-border px-5 py-3">
        <p className="text-sm leading-relaxed text-text-secondary">
          {detail.description}
        </p>
      </div>

      {/* Mini price chart (bar sparkline) */}
      {price_history.length > 0 && (
        <div className="px-5 py-4">
          <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-text-muted">
            <BarChart3 className="h-3 w-3" /> Price History (3mo)
          </div>
          <div className="flex h-20 items-end gap-[2px]">
            {price_history.slice(-60).map((pt, i) => {
              const prices = price_history.slice(-60).map((p) => p.close);
              const max = Math.max(...prices);
              const min = Math.min(...prices);
              const range = max - min || 1;
              const height = ((pt.close - min) / range) * 100;
              const isUp =
                i > 0 && pt.close >= price_history.slice(-60)[i - 1]?.close;
              return (
                <div
                  key={i}
                  className="flex-1 rounded-sm transition-all hover:opacity-80"
                  style={{
                    height: `${Math.max(height, 2)}%`,
                    backgroundColor: isUp
                      ? 'rgb(34, 197, 94)'
                      : 'rgb(239, 68, 68)',
                    opacity: 0.7,
                  }}
                  title={`${pt.date}: $${pt.close.toFixed(2)}`}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Performance metrics grid */}
      <div className="grid grid-cols-2 gap-4 px-5 py-4">
        <div className="rounded-lg bg-surface-tertiary/50 p-3">
          <div className="mb-0.5 text-[11px] text-text-muted">
            Relative Strength (1D)
          </div>
          <span
            className={cn(
              'text-sm font-bold',
              (perf.relative_strength_1d ?? 0) > 0
                ? 'text-gain'
                : (perf.relative_strength_1d ?? 0) < 0
                  ? 'text-loss'
                  : 'text-text-secondary'
            )}
          >
            {perf.relative_strength_1d !== null
              ? perf.relative_strength_1d.toFixed(3)
              : 'N/A'}
          </span>
        </div>
        <div className="rounded-lg bg-surface-tertiary/50 p-3">
          <div className="mb-0.5 text-[11px] text-text-muted">
            Relative Strength (1W)
          </div>
          <span
            className={cn(
              'text-sm font-bold',
              (perf.relative_strength_1w ?? 0) > 0
                ? 'text-gain'
                : (perf.relative_strength_1w ?? 0) < 0
                  ? 'text-loss'
                  : 'text-text-secondary'
            )}
          >
            {perf.relative_strength_1w !== null
              ? perf.relative_strength_1w.toFixed(3)
              : 'N/A'}
          </span>
        </div>
        <div className="rounded-lg bg-surface-tertiary/50 p-3">
          <div className="mb-0.5 text-[11px] text-text-muted">Momentum</div>
          <span className="text-sm font-bold text-text-primary">
            {perf.momentum_score?.toFixed(0) ?? 'N/A'}/100
          </span>
        </div>
        <div className="rounded-lg bg-surface-tertiary/50 p-3">
          <div className="mb-0.5 text-[11px] text-text-muted">
            Volume vs Avg
          </div>
          <span className="text-sm font-bold text-text-primary">
            {perf.volume_vs_avg !== null
              ? `${(perf.volume_vs_avg * 100).toFixed(0)}%`
              : 'N/A'}
          </span>
        </div>
      </div>

      {/* Flow signal */}
      <div className="border-t border-border px-5 py-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">
            Smart Money Flow
          </span>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
                perf.flow_signal === 'inflow'
                  ? 'bg-gain/10 text-gain'
                  : perf.flow_signal === 'outflow'
                    ? 'bg-loss/10 text-loss'
                    : 'bg-surface-tertiary text-text-muted'
              )}
            >
              <span
                className={cn(
                  'h-1.5 w-1.5 rounded-full',
                  perf.flow_signal === 'inflow'
                    ? 'bg-gain'
                    : perf.flow_signal === 'outflow'
                      ? 'bg-loss'
                      : 'bg-text-muted'
                )}
              />
              {perf.flow_signal === 'inflow'
                ? 'Accumulating'
                : perf.flow_signal === 'outflow'
                  ? 'Distributing'
                  : 'Neutral'}
            </span>
            <span className="text-xs tabular-nums text-text-muted">
              ({perf.flow_strength.toFixed(0)}%)
            </span>
          </div>
        </div>
        {perf.flow_strength > 0 && (
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-tertiary">
            <div
              className={cn(
                'h-full rounded-full transition-all',
                perf.flow_signal === 'inflow' ? 'bg-gain' : 'bg-loss'
              )}
              style={{ width: `${perf.flow_strength}%` }}
            />
          </div>
        )}
      </div>

      {/* Find stocks in this sector */}
      <div className="border-t border-border px-5 py-3">
        <button
          onClick={() =>
            navigate(`/screener?sector=${encodeURIComponent(detail.name)}`)
          }
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-border/50 bg-surface/50 px-3 py-2 text-xs font-medium text-text-muted transition-colors hover:border-text-muted/30 hover:bg-surface hover:text-text-primary"
        >
          <Search className="h-3.5 w-3.5" />
          Find stocks in {detail.name}
        </button>
      </div>
    </div>
  );
}

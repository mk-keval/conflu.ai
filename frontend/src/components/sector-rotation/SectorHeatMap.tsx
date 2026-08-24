import { useSectorRotationStore } from '@/store/sectorRotation';
import { cn } from '@/lib/cn';
import { formatPct } from '@/lib/format';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

function getChangeColor(value: number | null): string {
  if (value === null || value === undefined) return 'bg-surface-tertiary text-text-muted';
  if (value > 2) return 'bg-gain/20 text-gain border-gain/30';
  if (value > 0.5) return 'bg-gain/10 text-gain-light border-gain/20';
  if (value > -0.5) return 'bg-surface-tertiary text-text-secondary border-border';
  if (value > -2) return 'bg-loss/10 text-loss-light border-loss/20';
  return 'bg-loss/20 text-loss border-loss/30';
}

function getFlowDot(flow: string, strength: number) {
  if (flow === 'inflow' && strength > 30) return <span className="h-2 w-2 rounded-full bg-gain animate-pulse" title="Strong inflow" />;
  if (flow === 'inflow') return <span className="h-2 w-2 rounded-full bg-gain" title="Inflow" />;
  if (flow === 'outflow' && strength > 30) return <span className="h-2 w-2 rounded-full bg-loss animate-pulse" title="Strong outflow" />;
  if (flow === 'outflow') return <span className="h-2 w-2 rounded-full bg-loss" title="Outflow" />;
  return <span className="h-2 w-2 rounded-full bg-text-muted/40" title="Neutral" />;
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'bullish') return <TrendingUp className="h-3.5 w-3.5 text-gain" />;
  if (trend === 'bearish') return <TrendingDown className="h-3.5 w-3.5 text-loss" />;
  return <Minus className="h-3.5 w-3.5 text-text-muted" />;
}

interface SectorHeatMapProps {
  timeframe: '1D' | '1W';
  onSectorClick: (symbol: string) => void;
}

export function SectorHeatMap({ timeframe, onSectorClick }: SectorHeatMapProps) {
  const sectors = useSectorRotationStore((s) => s.sectors);
  const selected = useSectorRotationStore((s) => s.selectedSector);

  if (sectors.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-border bg-surface/50">
        <p className="text-sm text-text-muted">No sector data available yet</p>
      </div>
    );
  }

  const changeKey = timeframe === '1D' ? 'change_1d' : 'change_1w';
  const rsKey = timeframe === '1D' ? 'relative_strength_1d' : 'relative_strength_1w';
  const volKey = timeframe === '1D' ? 'volume_vs_avg' : 'volume_vs_avg_1w';
  const flowSignalKey = timeframe === '1D' ? 'flow_signal' as const : 'flow_signal_1w' as const;
  const flowStrengthKey = timeframe === '1D' ? 'flow_strength' as const : 'flow_strength_1w' as const;
  const label = timeframe === '1D' ? '1 Day' : '1 Week';

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">
          Sector Performance — {label}
          <span className="normal-case tracking-normal font-normal text-text-muted/70 ml-2">
            (today = noise · this week = signal)
          </span>
        </h3>
        <div className="flex items-center gap-3 text-[11px] text-text-muted">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-gain/20 border border-gain/30" /> Strong
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-surface-tertiary border border-border" /> Neutral
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-loss/20 border border-loss/30" /> Weak
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {sectors.map((sector) => {
          const change = sector[changeKey] ?? 0;
          const rs = sector[rsKey] ?? 0;
          const isSelected = selected === sector.symbol;

          return (
            <button
              key={sector.symbol}
              onClick={() => onSectorClick(sector.symbol)}
              className={cn(
                'relative flex flex-col gap-1.5 rounded-xl border p-3 text-left transition-all duration-150 hover:scale-[1.02] hover:shadow-md',
                getChangeColor(change),
                isSelected && 'ring-2 ring-accent ring-offset-2 ring-offset-background'
              )}
            >
              {/* Header row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold">{sector.symbol}</span>
                  {getFlowDot(sector[flowSignalKey], sector[flowStrengthKey])}
                </div>
                <TrendIcon trend={sector.trend} />
              </div>

              {/* Sector name */}
              <span className="truncate text-[10px] text-text-muted">{sector.name}</span>

              {/* Change percentage */}
              <span className={cn(
                'text-lg font-bold tabular-nums',
                change > 0 ? 'text-gain' : change < 0 ? 'text-loss' : 'text-text-secondary'
              )}>
                {formatPct(change)}
              </span>

              {/* Momentum bar */}
              {sector.momentum_score !== null && (
                <div className="mt-auto flex items-center gap-1.5">
                  <div className="h-1 flex-1 overflow-hidden rounded-full bg-surface">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all',
                        sector.momentum_score >= 60 ? 'bg-gain' : sector.momentum_score >= 40 ? 'bg-warning' : 'bg-loss'
                      )}
                      style={{ width: `${sector.momentum_score}%` }}
                    />
                  </div>
                  <span className="text-[10px] tabular-nums text-text-muted">
                    {sector.momentum_score.toFixed(0)}
                  </span>
                </div>
              )}

              {/* Relative strength + Volume row */}
              <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1 text-[10px] text-text-muted">
                <span className="font-medium">RS:</span>
                <span className={cn(
                  'tabular-nums',
                  rs > 0.5 ? 'text-gain' : rs < -0.5 ? 'text-loss' : ''
                )}>
                  {rs !== null ? rs.toFixed(2) : 'N/A'}
                </span>
              </div>

              {/* Volume indicator — switches between daily (1D) and weekly (1W) */}
              {sector[volKey] !== null && (
                <div className="flex items-center gap-1 text-[10px] text-text-muted">
                  <span className="font-medium">{timeframe === '1D' ? 'DVol' : 'WVol'}:</span>
                  <span className={cn(
                    'tabular-nums',
                    (sector[volKey] ?? 0) > 1.3 ? 'text-accent' : ''
                  )}>
                    {(sector[volKey] ?? 0).toFixed(1)}x avg
                  </span>
                </div>
              )}
            </div>
          </button>
          );
        })}
      </div>
    </div>
  );
}

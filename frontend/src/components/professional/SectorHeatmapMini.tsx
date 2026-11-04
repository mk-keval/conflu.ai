import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/cn';
import type { SectorBrief } from '@/types/professional';

interface SectorHeatmapMiniProps {
  sectors: SectorBrief[];
  isLoading?: boolean;
}

function getSectorColor(changePct: number): string {
  if (changePct > 2)
    return 'bg-green-500/25 border-green-500/40 text-green-300';
  if (changePct > 0.5)
    return 'bg-green-500/10 border-green-500/20 text-green-400';
  if (changePct > -0.5)
    return 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400';
  if (changePct > -2)
    return 'bg-orange-500/10 border-orange-500/20 text-orange-400';
  return 'bg-red-500/15 border-red-500/30 text-red-400';
}

export function SectorHeatmapMini({
  sectors,
  isLoading,
}: SectorHeatmapMiniProps) {
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <div data-testid="sector-heatmap" className="grid grid-cols-4 gap-2">
        {Array.from({ length: 8 }).map((_, idx) => (
          <div
            key={idx}
            className="h-16 animate-pulse rounded-lg bg-surface-tertiary/50"
          />
        ))}
      </div>
    );
  }

  if (!sectors.length) {
    return (
      <div
        data-testid="sector-heatmap"
        className="py-4 text-center text-xs text-text-muted"
      >
        No sector data available
      </div>
    );
  }

  return (
    <div
      data-testid="sector-heatmap"
      className="grid grid-cols-4 gap-2 sm:grid-cols-4 md:grid-cols-6"
    >
      {sectors.map((sector) => (
        <button
          key={sector.symbol}
          onClick={() => navigate('/sector-rotation')}
          className={cn(
            'flex flex-col items-center justify-center rounded-lg border p-2 transition-all duration-150',
            'hover:scale-105 hover:shadow-md',
            getSectorColor(sector.changePct)
          )}
        >
          <span className="text-xs font-bold">{sector.symbol}</span>
          <span className="text-2xs w-full truncate text-center text-text-muted">
            {sector.name}
          </span>
          <span className="mt-0.5 font-mono text-xs font-semibold">
            {sector.changePct > 0 ? '+' : ''}
            {sector.changePct.toFixed(1)}%
          </span>
        </button>
      ))}
    </div>
  );
}

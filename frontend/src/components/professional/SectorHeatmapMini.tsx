import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/cn';
import type { SectorBrief } from '@/types/professional';

interface SectorHeatmapMiniProps {
  sectors: SectorBrief[];
  isLoading?: boolean;
}

function getSectorColor(changePct: number): string {
  if (changePct > 2) return 'bg-green-500/25 border-green-500/40 text-green-300';
  if (changePct > 0.5) return 'bg-green-500/10 border-green-500/20 text-green-400';
  if (changePct > -0.5) return 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400';
  if (changePct > -2) return 'bg-orange-500/10 border-orange-500/20 text-orange-400';
  return 'bg-red-500/15 border-red-500/30 text-red-400';
}

export function SectorHeatmapMini({ sectors, isLoading }: SectorHeatmapMiniProps) {
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <div data-testid="sector-heatmap" className="grid grid-cols-4 gap-2">
        {Array.from({ length: 8 }).map((_, idx) => (
          <div
            key={idx}
            className="h-16 rounded-lg bg-surface-tertiary/50 animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (!sectors.length) {
    return (
      <div data-testid="sector-heatmap" className="text-xs text-text-muted text-center py-4">
        No sector data available
      </div>
    );
  }

  return (
    <div data-testid="sector-heatmap" className="grid grid-cols-4 sm:grid-cols-4 md:grid-cols-6 gap-2">
      {sectors.map((sector) => (
        <button
          key={sector.symbol}
          onClick={() => navigate('/sector-rotation')}
          className={cn(
            'flex flex-col items-center justify-center p-2 rounded-lg border transition-all duration-150',
            'hover:scale-105 hover:shadow-md',
            getSectorColor(sector.changePct)
          )}
        >
          <span className="font-bold text-xs">{sector.symbol}</span>
          <span className="text-2xs text-text-muted truncate w-full text-center">
            {sector.name}
          </span>
          <span className="font-mono text-xs font-semibold mt-0.5">
            {sector.changePct > 0 ? '+' : ''}{sector.changePct.toFixed(1)}%
          </span>
        </button>
      ))}
    </div>
  );
}

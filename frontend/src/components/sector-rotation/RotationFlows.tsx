import { useSectorRotationStore } from '@/store/sectorRotation';
import { cn } from '@/lib/cn';
import { ArrowUp, ArrowDown, Minus } from 'lucide-react';

/** Phase labels and descriptions for the economic rotation cycle. */
const PHASE_META: Record<string, { label: string; description: string; color: string }> = {
  early_cycle: {
    label: 'Early Cycle',
    description: 'Economy recovering from recession. Cyclicals (Materials, Industrials, Consumer Disc.) lead as growth resumes.',
    color: 'text-gain',
  },
  growth_lead: {
    label: 'Growth Leading',
    description: 'Technology and Communication Services leading. Bull market broadening with innovation-driven growth.',
    color: 'text-accent',
  },
  late_cycle: {
    label: 'Late Cycle',
    description: 'Economy maturing. Energy and Financials lead as inflation expectations rise and rates normalize.',
    color: 'text-warning',
  },
  defensive_flight: {
    label: 'Defensive Flight',
    description: 'Risk-off rotation. Capital flowing to Utilities, Consumer Staples, Health Care, and Real Estate as growth concerns mount.',
    color: 'text-loss',
  },
  neutral: {
    label: 'Transitional',
    description: 'No clear rotation pattern detected. Markets in a transitional phase between cycles.',
    color: 'text-text-muted',
  },
  unknown: {
    label: 'Analyzing...',
    description: 'Insufficient data to determine rotation phase.',
    color: 'text-text-muted',
  },
};

function FlowArrow({ flow, strength }: { flow: string; strength: number }) {
  const size = Math.min(Math.max(strength / 10, 16), 32);
  if (flow === 'inflow') return <ArrowUp className="text-gain" style={{ width: size, height: size }} />;
  if (flow === 'outflow') return <ArrowDown className="text-loss" style={{ width: size, height: size }} />;
  return <Minus className="text-text-muted" style={{ width: 16, height: 16 }} />;
}

export function RotationFlows() {
  const sectors = useSectorRotationStore((s) => s.sectors);
  const rotationPhase = useSectorRotationStore((s) => s.rotationPhase);
  const marketRegime = useSectorRotationStore((s) => s.marketRegime);

  // Top sectors by momentum
  const topByMom = [...sectors]
    .sort((a, b) => (b.momentum_score ?? 0) - (a.momentum_score ?? 0))
    .slice(0, 6);

  const phase = PHASE_META[rotationPhase] ?? PHASE_META.unknown;

  return (
    <div className="space-y-4">
      {/* Rotation Phase Banner */}
      <div className={cn(
        'rounded-xl border p-4',
        rotationPhase === 'early_cycle' ? 'border-gain/30 bg-gain/5' :
        rotationPhase === 'defensive_flight' ? 'border-loss/30 bg-loss/5' :
        'border-border bg-surface'
      )}>
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className={cn('text-sm font-bold', phase.color)}>{phase.label}</span>
              {marketRegime && (
                <span className="rounded-full bg-surface-tertiary px-2 py-0.5 text-[10px] text-text-muted">
                  {marketRegime.replace(/_/g, ' ')}
                </span>
              )}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-text-secondary">{phase.description}</p>
          </div>
        </div>
      </div>

      {/* Flow arrows - top sectors */}
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-text-muted">
          Top Momentum Sectors
        </h3>
        <div className="space-y-1.5">
          {topByMom.map((sector, idx) => (
            <div
              key={sector.symbol}
              className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2"
            >
              <span className="w-5 text-center text-xs font-bold text-text-muted">{idx + 1}</span>
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-bold text-text-primary">{sector.symbol}</span>
                <span className="text-[11px] text-text-muted">{sector.name}</span>
              </div>
              <div className="ml-auto flex items-center gap-3">
                <FlowArrow flow={sector.flow_signal} strength={sector.flow_strength} />
                <span className={cn(
                  'text-sm font-bold tabular-nums',
                  (sector.momentum_score ?? 0) >= 60 ? 'text-gain' :
                  (sector.momentum_score ?? 0) >= 40 ? 'text-warning' :
                  'text-loss'
                )}>
                  {sector.momentum_score?.toFixed(0) ?? 'N/A'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

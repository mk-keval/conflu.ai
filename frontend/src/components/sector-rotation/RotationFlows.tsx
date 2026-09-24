import { useSectorRotationStore } from '@/store/sectorRotation';
import type { TimeframeOption } from '@/types/sector';
import { cn } from '@/lib/cn';
import { ArrowUp, ArrowDown, Minus, Info } from 'lucide-react';

/** Phase labels and descriptions for the economic rotation cycle. */
const PHASE_META: Record<
  string,
  { label: string; description: string; color: string; action: string }
> = {
  early_cycle: {
    label: 'Early Cycle',
    description:
      'Cyclicals (Industrials, Consumer Disc., Financials, Tech) leading as the economy recovers from a downturn.',
    color: 'text-gain',
    action:
      'Favor cyclicals. Look for breakouts in XLI, XLF, XLY, XLK. Reduce defensives — they lag when growth resumes.',
  },
  growth_lead: {
    label: 'Growth Leading',
    description:
      'Tech and Communication Services driving the market higher. Innovation-led expansion phase.',
    color: 'text-accent',
    action:
      'Ride momentum in XLK, XLC. Let winners run. Use pullbacks to EMA as entries. Avoid fighting the trend.',
  },
  late_cycle: {
    label: 'Late Cycle',
    description:
      'Energy and Materials leading as inflation expectations build and commodity prices rise.',
    color: 'text-warning',
    action:
      'Add inflation hedges (XLE, XLB). Tighten stops. Start trimming extended growth positions. Protect gains.',
  },
  defensive_flight: {
    label: 'Defensive Flight',
    description:
      'Capital rotating to safety — Utilities, Staples, Health Care, Real Estate. Growth concerns dominate.',
    color: 'text-loss',
    action:
      'Reduce position sizes. Avoid beaten-down cyclicals. Cash is a position. Wait for the rotation to exhaust before re-entering risk.',
  },
  neutral: {
    label: 'Transitional',
    description:
      'No clear rotation pattern detected — market in a tug-of-war between sectors.',
    color: 'text-text-muted',
    action:
      "Stay small. Don't force trades. The market hasn't picked a direction yet — wait for a clearer signal.",
  },
  unknown: {
    label: 'Analyzing...',
    description: 'Insufficient data to determine rotation phase.',
    color: 'text-text-muted',
    action: 'Data still loading. Check back after market data refreshes.',
  },
};

function FlowArrow({ flow, strength }: { flow: string; strength: number }) {
  const size = Math.min(Math.max(strength / 10, 16), 32);
  if (flow === 'inflow')
    return (
      <ArrowUp className="text-gain" style={{ width: size, height: size }} />
    );
  if (flow === 'outflow')
    return (
      <ArrowDown className="text-loss" style={{ width: size, height: size }} />
    );
  return (
    <Minus className="text-text-muted" style={{ width: 16, height: 16 }} />
  );
}

interface RotationFlowsProps {
  timeframe: TimeframeOption;
}

export function RotationFlows({ timeframe }: RotationFlowsProps) {
  const sectors = useSectorRotationStore((s) => s.sectors);
  const rotationPhase = useSectorRotationStore((s) => s.rotationPhase);
  const marketRegime = useSectorRotationStore((s) => s.marketRegime);

  // Timeframe-aware sorting — use RS for the selected period so 1D vs 1W changes the ranking
  const rsKey =
    timeframe === '1D' ? 'relative_strength_1d' : 'relative_strength_1w';
  const flowSignalKey =
    timeframe === '1D' ? ('flow_signal' as const) : ('flow_signal_1w' as const);
  const flowStrengthKey =
    timeframe === '1D'
      ? ('flow_strength' as const)
      : ('flow_strength_1w' as const);
  const volKey =
    timeframe === '1D'
      ? ('volume_vs_avg' as const)
      : ('volume_vs_avg_1w' as const);

  // Top sectors by RS for the selected timeframe
  const topByRS = [...sectors]
    .sort((a, b) => (b[rsKey] ?? -999) - (a[rsKey] ?? -999))
    .slice(0, 6);

  const phase = PHASE_META[rotationPhase] ?? PHASE_META.unknown;

  return (
    <div className="space-y-4">
      {/* Rotation Phase Banner */}
      <div
        className={cn(
          'rounded-xl border p-4',
          rotationPhase === 'early_cycle'
            ? 'border-gain/30 bg-gain/5'
            : rotationPhase === 'defensive_flight'
              ? 'border-loss/30 bg-loss/5'
              : 'border-border bg-surface'
        )}
      >
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className={cn('text-sm font-bold', phase.color)}>
                {phase.label}
              </span>
              {marketRegime && (
                <span className="rounded-full bg-surface-tertiary px-2 py-0.5 text-[10px] text-text-muted">
                  {marketRegime.replace(/_/g, ' ')}
                </span>
              )}
              <span className="rounded-full bg-surface-tertiary px-2 py-0.5 text-[10px] text-text-muted">
                based on 1W data
              </span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-text-secondary">
              {phase.description}
            </p>
            <div className="mt-2 flex items-start gap-1.5 rounded-md bg-surface-tertiary/50 px-2.5 py-1.5">
              <Info className="mt-0.5 h-3 w-3 shrink-0 text-accent" />
              <p className="text-[11px] leading-relaxed text-text-secondary">
                {phase.action}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Flow arrows — top sectors by RS for this timeframe */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted">
            Top RS — {timeframe === '1D' ? 'Today' : 'This Week'}
          </h3>
          {timeframe === '1W' && (
            <span className="text-[10px] text-text-muted/60">
              Phase uses 1W data — switch to 1D for today's action
            </span>
          )}
        </div>
        <div className="space-y-1.5">
          {topByRS.map((sector, idx) => (
            <div
              key={sector.symbol}
              className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2"
            >
              <span className="w-5 text-center text-xs font-bold text-text-muted">
                {idx + 1}
              </span>
              <div className="flex min-w-0 items-center gap-1.5">
                <span className="text-sm font-bold text-text-primary">
                  {sector.symbol}
                </span>
                <span className="truncate text-[11px] text-text-muted">
                  {sector.name}
                </span>
              </div>
              <div className="ml-auto flex shrink-0 items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <FlowArrow
                    flow={sector[flowSignalKey]}
                    strength={sector[flowStrengthKey]}
                  />
                  {sector[volKey] !== null && (
                    <span
                      className={cn(
                        'text-[10px] tabular-nums',
                        (sector[volKey] ?? 0) > 1.3
                          ? 'text-accent'
                          : 'text-text-muted'
                      )}
                    >
                      {(sector[volKey] ?? 0).toFixed(1)}x
                    </span>
                  )}
                </div>
                <span
                  className={cn(
                    'w-12 text-right text-sm font-bold tabular-nums',
                    (sector[rsKey] ?? 0) > 0.5
                      ? 'text-gain'
                      : (sector[rsKey] ?? 0) < -0.5
                        ? 'text-loss'
                        : 'text-text-secondary'
                  )}
                >
                  {sector[rsKey] !== null && sector[rsKey] !== undefined
                    ? (sector[rsKey]! > 0 ? '+' : '') +
                      sector[rsKey]!.toFixed(2)
                    : 'N/A'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

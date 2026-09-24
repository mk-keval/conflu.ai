import { useState } from 'react';
import {
  Target,
  Eye,
  Ban,
  ShieldAlert,
  ChevronRight,
  ChevronDown,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { useSectorFocus } from '@/hooks/useMarketRegime';
import type { SectorFocusEntry } from '@/types/sector';

const VERDICT_STYLES: Record<string, { chip: string; icon: React.ReactNode }> =
  {
    FOCUS: {
      chip: 'bg-gain/15 text-gain border border-gain/40',
      icon: <Target className="h-3.5 w-3.5" />,
    },
    WATCH: {
      chip: 'bg-warning/10 text-warning border border-warning/30',
      icon: <Eye className="h-3.5 w-3.5" />,
    },
    AVOID: {
      chip: 'bg-loss/10 text-loss border border-loss/30',
      icon: <Ban className="h-3.5 w-3.5" />,
    },
    AVOID_RELATIVE: {
      chip: 'bg-loss/5 text-loss/80 border border-loss/20',
      icon: <Ban className="h-3.5 w-3.5" />,
    },
  };

function EntryRow({
  entry,
  onHunt,
  compact,
}: {
  entry: SectorFocusEntry;
  onHunt?: (name: string) => void;
  compact?: boolean;
}) {
  const style = VERDICT_STYLES[entry.verdict] ?? VERDICT_STYLES.WATCH;
  const isFocus = entry.verdict === 'FOCUS';

  return (
    <div
      className={cn(
        'rounded-lg p-3',
        isFocus
          ? 'border border-gain/25 bg-gain/[0.06]'
          : 'border border-border/40 bg-surface-hover/40'
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold uppercase',
            style.chip
          )}
        >
          {style.icon} {entry.verdict.replace('_', ' ')}
        </span>
        <span className="text-sm font-semibold text-text-primary">
          {entry.name}
          <span className="font-normal text-text-muted"> · {entry.symbol}</span>
        </span>
        {entry.score != null && <FocusScore score={entry.score} />}
      </div>
      {!compact && entry.reasons.length > 0 && (
        <ul className="mt-1.5 space-y-0.5">
          {entry.reasons.map((r, i) => (
            <li
              key={i}
              className="flex items-start gap-1.5 text-xs text-text-secondary"
            >
              <span className="shrink-0 text-text-muted">•</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}
      {isFocus && onHunt && (
        <button
          onClick={() => onHunt(entry.name)}
          className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-accent transition-colors hover:text-accent/80"
        >
          Hunt swing candidates in {entry.name}
          <ChevronRight className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}

export function SectorFocusCard({ compact = false }: { compact?: boolean }) {
  const { data, isLoading, error } = useSectorFocus();

  if (isLoading && !data) {
    return (
      <div className="animate-pulse rounded-xl border border-border bg-surface p-4">
        <div className="mb-3 h-3 w-40 rounded bg-surface-hover" />
        <div className="h-16 rounded bg-surface-hover" />
      </div>
    );
  }
  if (error || !data || !data.snapshot_id) return null;

  const handleHunt = (name: string) => {
    window.location.href = `/screener?sector=${encodeURIComponent(name)}&focus=1`;
  };

  return (
    <section
      aria-label="This week's sector focus"
      className="rounded-xl border border-accent/25 bg-surface p-4"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Target className="h-4 w-4 text-accent" /> This Week's Sector Focus
        </h2>
        <div className="flex items-center gap-2 text-[10px] text-text-muted">
          <span title="Weekly relative strength is the swing-trading signal; today's moves are noise">
            weekly horizon = decision lens
          </span>
          <span>·</span>
          <span title={new Date(data.next_refresh_at).toLocaleString()}>
            refreshes{' '}
            {new Date(data.next_refresh_at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
      </div>

      {data.no_hunt_mode ? (
        <div className="flex items-start gap-2 rounded-lg border border-loss/30 bg-loss/5 p-3">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-loss" />
          <div>
            <p className="text-sm font-semibold text-loss">No-hunt mode</p>
            <p className="mt-0.5 text-xs text-text-secondary">
              Broad market weakness detected — capital preservation first.
              Re-check after conditions stabilize.
            </p>
          </div>
        </div>
      ) : data.focus.length === 0 ? (
        <p className="py-2 text-sm text-text-muted">
          No sector clears the bar this week. Patience is a position.
        </p>
      ) : (
        <div className="space-y-2">
          {data.focus.map((e) => (
            <EntryRow
              key={e.symbol}
              entry={e}
              onHunt={handleHunt}
              compact={compact}
            />
          ))}
        </div>
      )}

      {!compact && data.watch.length > 0 && (
        <details className="group mt-3">
          <summary className="flex cursor-pointer items-center gap-1.5 text-xs font-semibold text-text-muted hover:text-text-secondary">
            <Eye className="h-3 w-3" /> Watch ({data.watch.length}) — rising,
            not yet confirmed
          </summary>
          <div className="mt-2 space-y-2">
            {data.watch.slice(0, 4).map((e) => (
              <EntryRow key={e.symbol} entry={e} />
            ))}
          </div>
        </details>
      )}

      {!compact && data.avoid.length > 0 && (
        <div className="mt-3 border-t border-border/40 pt-3">
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-text-muted">
            <Ban className="h-3 w-3" /> Skip for longs this week
          </p>
          <div className="flex flex-wrap gap-1.5">
            {data.avoid.map((e) => (
              <span
                key={e.symbol}
                title={e.reasons.join(' · ')}
                className="cursor-help rounded-full border border-loss/20 bg-loss/5 px-2 py-0.5 text-[11px] text-loss/80"
              >
                {e.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

/**
 * Visible FOCUS-score breakdown — surfaces the scoring formula that was
 * previously hidden in a title attribute. Shows the WEIGHT LEGEND only;
 * per-component values are not exposed by the API, so we never fabricate them.
 * Formula verified against backend sector_focus/service.py.
 */
function FocusScore({ score }: { score: number }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative ml-auto">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        className="inline-flex items-center gap-1 font-mono text-xs text-text-secondary transition-colors hover:text-accent"
        aria-expanded={open}
      >
        {Math.round(score)}/100
        <ChevronDown
          className={cn('h-3 w-3 transition-transform', open && 'rotate-180')}
        />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-64 rounded-lg border border-border bg-surface p-3 text-xs shadow-xl">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            How this score is built
          </p>
          <ul className="space-y-1.5">
            {[
              ['Weekly relative strength', '40%'],
              ['Institutional flow', '25%'],
              ['Momentum', '20%'],
              ['Volume confirmation', '15%'],
            ].map(([label, weight]) => (
              <li key={label} className="flex items-center gap-2">
                <span
                  className="h-1.5 rounded-sm bg-accent/60"
                  style={{ width: `${parseInt(weight) * 1.6}px` }}
                />
                <span className="text-text-primary">{label}</span>
                <span className="ml-auto font-mono text-text-muted">
                  {weight}
                </span>
              </li>
            ))}
            <li className="flex items-center justify-between border-t border-border/50 pt-1">
              <span className="text-text-muted">Improvement bonus</span>
              <span className="font-mono text-gain">up to +10</span>
            </li>
          </ul>
          <p className="mt-2 text-[10px] leading-relaxed text-text-muted">
            In weak markets the score is capped or demoted to WATCH regardless
            of components — capital protection first.
          </p>
        </div>
      )}
    </span>
  );
}

import { Target, Eye, Ban, ShieldAlert, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useSectorFocus } from '@/hooks/useMarketRegime';
import type { SectorFocusEntry } from '@/types/sector';

const VERDICT_STYLES: Record<string, { chip: string; icon: React.ReactNode }> = {
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
        isFocus ? 'bg-gain/[0.06] border border-gain/25' : 'bg-surface-hover/40 border border-border/40'
      )}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className={cn('inline-flex items-center gap-1 text-[11px] font-bold uppercase px-2 py-0.5 rounded-full', style.chip)}>
          {style.icon} {entry.verdict.replace('_', ' ')}
        </span>
        <span className="text-sm font-semibold text-text-primary">
          {entry.name}
          <span className="text-text-muted font-normal"> · {entry.symbol}</span>
        </span>
        {entry.score != null && (
          <span className="ml-auto text-xs font-mono text-text-secondary" title="Composite of weekly relative strength, institutional flow, momentum, and volume confirmation">
            {Math.round(entry.score)}/100
          </span>
        )}
      </div>
      {!compact && entry.reasons.length > 0 && (
        <ul className="mt-1.5 space-y-0.5">
          {entry.reasons.map((r, i) => (
            <li key={i} className="text-xs text-text-secondary flex items-start gap-1.5">
              <span className="text-text-muted shrink-0">•</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}
      {isFocus && onHunt && (
        <button
          onClick={() => onHunt(entry.name)}
          className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-accent hover:text-accent/80 transition-colors"
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
      <div className="rounded-xl border border-border bg-surface p-4 animate-pulse">
        <div className="h-3 w-40 bg-surface-hover rounded mb-3" />
        <div className="h-16 bg-surface-hover rounded" />
      </div>
    );
  }
  if (error || !data || !data.snapshot_id) return null;

  const handleHunt = (name: string) => {
    window.location.href = `/screener?sector=${encodeURIComponent(name)}&focus=1`;
  };

  return (
    <section aria-label="This week's sector focus" className="rounded-xl border border-accent/25 bg-surface p-4">
      <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
        <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
          <Target className="h-4 w-4 text-accent" /> This Week's Sector Focus
        </h2>
        <div className="flex items-center gap-2 text-[10px] text-text-muted">
          <span title="Weekly relative strength is the swing-trading signal; today's moves are noise">
            weekly horizon = decision lens
          </span>
          <span>·</span>
          <span title={new Date(data.next_refresh_at).toLocaleString()}>
            refreshes {new Date(data.next_refresh_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>

      {data.no_hunt_mode ? (
        <div className="flex items-start gap-2 rounded-lg bg-loss/5 border border-loss/30 p-3">
          <ShieldAlert className="h-4 w-4 text-loss mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-loss">No-hunt mode</p>
            <p className="text-xs text-text-secondary mt-0.5">
              Broad market weakness detected — capital preservation first. Re-check after conditions stabilize.
            </p>
          </div>
        </div>
      ) : data.focus.length === 0 ? (
        <p className="text-sm text-text-muted py-2">
          No sector clears the bar this week. Patience is a position.
        </p>
      ) : (
        <div className="space-y-2">
          {data.focus.map((e) => (
            <EntryRow key={e.symbol} entry={e} onHunt={handleHunt} compact={compact} />
          ))}
        </div>
      )}

      {!compact && data.watch.length > 0 && (
        <details className="mt-3 group">
          <summary className="cursor-pointer text-xs font-semibold text-text-muted hover:text-text-secondary flex items-center gap-1.5">
            <Eye className="h-3 w-3" /> Watch ({data.watch.length}) — rising, not yet confirmed
          </summary>
          <div className="mt-2 space-y-2">
            {data.watch.slice(0, 4).map((e) => (
              <EntryRow key={e.symbol} entry={e} />
            ))}
          </div>
        </details>
      )}

      {!compact && data.avoid.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/40">
          <p className="text-xs font-semibold text-text-muted flex items-center gap-1.5 mb-1.5">
            <Ban className="h-3 w-3" /> Skip for longs this week
          </p>
          <div className="flex flex-wrap gap-1.5">
            {data.avoid.map((e) => (
              <span
                key={e.symbol}
                title={e.reasons.join(' · ')}
                className="text-[11px] px-2 py-0.5 rounded-full bg-loss/5 text-loss/80 border border-loss/20 cursor-help"
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

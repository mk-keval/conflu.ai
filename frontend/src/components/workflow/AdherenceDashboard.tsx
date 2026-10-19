/**
 * Adherence Dashboard (Phase 1, Sprint 7) — the beginner's "Skill Score".
 *
 * Reads paper trades straight from the persisted localStorage store and shows:
 *   - rolling 20-trade adherence % (the single-number north-star metric)
 *   - consistency streak (consecutive adherent trades >= ADHERENT_THRESHOLD)
 *   - a per-trade table (symbol, opened/closed, outcome, steps, adherence %)
 *   - one-click CSV export
 *   - Expectancy Meter (Slice 3) — rolling expectancy/profit factor over closed trades
 *   - Open Positions Tracker (Slice 3) — current R on open paper trades
 *
 * Pure, browser-free CSV logic lives in `workflow/adherenceExport.ts` so it is
 * unit-testable. This component is a thin read-only view: it derives everything
 * from `useWorkflowStore` + `useAdherence` and writes nothing (this tab is the
 * *scoreboard*; recording happens in the backend journal — D-68).
 */

import { useMemo } from 'react';
import {
  Target,
  TrendingUp,
  FileDown,
  Inbox,
  Award,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatDate } from '@/lib/format';
import {
  useWorkflowStore,
  useAdherence,
  ADHERENCE_WINDOW,
} from '@/store/workflowStore';
import { ADHERENT_THRESHOLD } from '@/workflow/adherence';
import { buildAdherenceCsv } from '@/workflow/adherenceExport';
import { TermLink } from '@/components/learn/TermLink';
import { ExpectancyMeter } from './ExpectancyMeter';
import { OpenPositionsTracker } from './OpenPositionsTracker';

/** Human-friendly short label for a close outcome (matched to the logger). */
const OUTCOME_LABEL: Record<string, string> = {
  target_hit: 'Target hit',
  stop_hit: 'Stop hit',
  time_stop: 'Time stop',
  flat: 'Closed flat',
  open: 'Open',
};

function outcomeClasses(outcome: string): string {
  switch (outcome) {
    case 'target_hit':
      return 'text-green-400 bg-green-400/10 border-green-400/30';
    case 'stop_hit':
      return 'text-red-400 bg-red-400/10 border-red-400/30';
    case 'time_stop':
      return 'text-orange-400 bg-orange-400/10 border-orange-400/30';
    case 'flat':
      return 'text-text-muted bg-surface-tertiary/40 border-border/40';
    default:
      return 'text-accent bg-accent/10 border-accent/30';
  }
}

/** Trigger a browser download of `content` as a UTF-8 CSV file. */
function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function AdherenceDashboard() {
  const paperTrades = useWorkflowStore((s) => s.paperTrades);
  const adherence = useAdherence();

  const closedTrades = useMemo(
    () =>
      paperTrades
        .filter((t) => t.status === 'closed' && t.closedAt != null)
        .slice()
        .sort((a, b) =>
          a.closedAt! < b.closedAt! ? 1 : a.closedAt! > b.closedAt! ? -1 : 0
        ),
    [paperTrades]
  );

  const hasTrades = paperTrades.length > 0;
  const hasClosed = closedTrades.length > 0;
  const toWindow = Math.min(ADHERENCE_WINDOW, adherence.rolling.count);

  const handleExport = () => {
    if (!hasClosed) return;
    downloadCsv('adherence.csv', buildAdherenceCsv(closedTrades));
  };

  // Big meter colour by performance so a beginner reads it at a glance.
  const meterClasses = cn(
    'relative mx-auto flex h-32 w-32 items-center justify-center rounded-full border-4',
    adherence.rolling.pct >= ADHERENT_THRESHOLD
      ? 'border-green-500 text-green-400'
      : adherence.rolling.pct >= 50
        ? 'border-yellow-400 text-yellow-400'
        : 'border-red-500 text-red-400'
  );

  return (
    <div className="space-y-4">
      {/* ── Empty state: first-time beginner ── */}
      {!hasTrades && (
        <div className="rounded-xl border border-border/50 bg-surface/20 p-10 text-center">
          <Inbox className="mx-auto h-10 w-10 text-text-muted" />
          <h2 className="mt-3 text-sm font-semibold text-text-primary">
            Your Skill Score starts here
          </h2>
          <p className="mx-auto mt-2 max-w-md text-xs text-text-muted">
            Log your first{' '}
            <span className="font-semibold text-text-primary">paper trade</span>{' '}
            from the Execution Engine and your adherence meter will appear here.
            You build it one validated setup at a time.
          </p>
          <p className="mx-auto mt-3 max-w-md text-xs text-text-muted">
            This is your <TermLink text="adherence" /> score — the % of your{' '}
            <TermLink text="trading plan" /> you actually followed. Consistency
            beats any single win.
          </p>
        </div>
      )}

      {/* ── Header cards ── */}
      {hasTrades && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* Rolling adherence meter */}
          <div className="rounded-xl border border-border/50 bg-surface/20 p-4 text-center">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              <Activity className="mr-1 inline h-3 w-3" />
              Rolling {ADHERENCE_WINDOW}-trade adherence
            </div>
            <div className={meterClasses}>
              <div>
                <div className="text-3xl font-bold">
                  {adherence.rolling.pct}%
                </div>
                {toWindow > 0 && (
                  <div className="text-[10px] text-text-muted">
                    over {toWindow} trade{toWindow === 1 ? '' : 's'}
                  </div>
                )}
              </div>
            </div>
            <p className="mt-2 text-[11px] text-text-muted">
              {adherence.rolling.full
                ? `Statistically meaningful (${ADHERENCE_WINDOW} trades logged). Nice.`
                : `${ADHERENCE_WINDOW - adherence.rolling.count} more closed trade${ADHERENCE_WINDOW - adherence.rolling.count === 1 ? '' : 's'} until this number is battle-tested.`}
            </p>
          </div>

          {/* Streak */}
          <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              <Award className="mr-1 inline h-3 w-3" />
              Consistency streak
            </div>
            <div className="flex items-baseline gap-1">
              <span
                className={cn(
                  'text-3xl font-bold',
                  adherence.streak >= 3
                    ? 'text-green-400'
                    : adherence.streak > 0
                      ? 'text-yellow-400'
                      : 'text-text-muted'
                )}
              >
                {adherence.streak}
              </span>
              <span className="text-xs text-text-muted">
                {adherence.streak === 1 ? 'trade' : 'trades'} at{' '}
                {ADHERENT_THRESHOLD}%+
              </span>
            </div>
            <p className="mt-2 text-[11px] text-text-muted">
              Consecutive trades where you followed your plan at least{' '}
              {ADHERENT_THRESHOLD}% of the time. The point of the daily routine
              is to keep this number climbing.
            </p>
          </div>

          {/* Quick stats */}
          <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              <Target className="mr-1 inline h-3 w-3" />
              Trades logged
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-text-primary">
                {paperTrades.length}
              </span>
              <span className="text-xs text-text-muted">total print</span>
            </div>
            <div className="mt-2 space-y-1 text-[11px] text-text-muted">
              <div className="flex justify-between">
                <span>Closed</span>
                <span className="font-mono text-text-primary">
                  {closedTrades.length}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Open</span>
                <span className="font-mono text-text-primary">
                  {paperTrades.length - closedTrades.length}
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={handleExport}
              disabled={!hasClosed}
              className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-border/40 px-3 py-1.5 text-xs font-medium text-text-primary transition-colors hover:border-accent/50 hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              <FileDown className="h-3.5 w-3.5" />
              Export CSV
            </button>
          </div>
        </div>
      )}

      {/* ── Expectancy Meter (Slice 3) ── */}
      {hasTrades && <ExpectancyMeter />}

      {/* ── Open Positions Tracker (Slice 3) ── */}
      {hasTrades && <OpenPositionsTracker />}

      {/* ── Per-trade table ── */}
      {hasTrades && (
        <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold text-text-primary">
              Trade-by-trade score
            </h2>
            <span className="text-[11px] text-text-muted">(newest first)</span>
          </div>

          {!hasClosed ? (
            <p className="text-xs text-text-muted">
              No closed trades yet. Close a paper trade from the logger to see
              it scored here.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-text-muted">
                    <th className="pb-2 pr-3 font-medium">Symbol</th>
                    <th className="pb-2 pr-3 font-medium">Closed</th>
                    <th className="pb-2 pr-3 font-medium">Outcome</th>
                    <th className="pb-2 pr-3 text-right font-medium">Steps</th>
                    <th className="pb-2 text-right font-medium">Adherence</th>
                  </tr>
                </thead>
                <tbody>
                  {closedTrades.map((trade) => (
                    <tr key={trade.id} className="border-t border-border/20">
                      <td className="py-2 pr-3 font-mono font-semibold text-text-primary">
                        {trade.symbol}
                      </td>
                      <td className="py-2 pr-3 text-text-muted">
                        {trade.closedAt ? formatDate(trade.closedAt) : '—'}
                      </td>
                      <td className="py-2 pr-3">
                        <span
                          className={cn(
                            'inline-block rounded-full border px-2 py-0.5 text-[10px] font-medium',
                            outcomeClasses(trade.outcome)
                          )}
                        >
                          {OUTCOME_LABEL[trade.outcome] ?? trade.outcome}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right font-mono text-text-muted">
                        {trade.stepsFollowed}/{trade.stepsTotal}
                      </td>
                      <td className="py-2 text-right">
                        <span
                          className={cn(
                            'font-mono font-semibold',
                            trade.adherencePct >= ADHERENT_THRESHOLD
                              ? 'text-green-400'
                              : trade.adherencePct >= 50
                                ? 'text-yellow-400'
                                : 'text-red-400'
                          )}
                        >
                          {trade.adherencePct}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

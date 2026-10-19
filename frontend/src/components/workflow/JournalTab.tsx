/**
 * Journal tab (D-68 P4) — the SQLite journal of record, visible in the UI.
 *
 * Sections:
 *   - Runs strip: last 14 days of `workflow_runs` (green ok / red error·partial
 *     / gray missed / faint weekend).
 *   - Trades table: filter chips Today / Open / Closed / All over all journal
 *     rows (client-side — the book is small).
 *   - Rejections: collapsed list of why candidates did not become trades.
 *   - Export CSV: downloads the canonical journal export (Excel-friendly).
 *
 * Pure helpers (`filterJournalRows`, `buildRunsStrip`, `shiftDateKey`) are
 * exported so the filtering + strip logic is unit-testable without a DOM.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BookOpen,
  Download,
  Loader2,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  JOURNAL_EXPORT_URL,
  getJournalAll,
  getRejections,
  getRuns,
  type JournalRejection,
  type JournalRow,
  type WorkflowRun,
} from '@/api/workflow';
import { todayKey } from './DailyRoutine';

// ── Pure helpers (unit-tested) ──

export type JournalFilter = 'today' | 'open' | 'closed' | 'all';

export const JOURNAL_FILTERS: Array<{ id: JournalFilter; label: string }> = [
  { id: 'today', label: 'Today' },
  { id: 'open', label: 'Open' },
  { id: 'closed', label: 'Closed' },
  { id: 'all', label: 'All' },
];

/** Day portion of a journal date cell ("YYYY-MM-DD" or null-safe). */
function dayOf(v: string | null | undefined): string {
  return (v || '').slice(0, 10);
}

/**
 * Filter journal rows for the trades table.
 * - `today` matches rows entered **or** closed today (so an after-close run's
 *   exits show up under Today even though they were entered earlier).
 * - `open` / `closed` key off `date_closed`.
 */
export function filterJournalRows(
  rows: JournalRow[],
  filter: JournalFilter,
  today: string
): JournalRow[] {
  switch (filter) {
    case 'today':
      return rows.filter(
        (r) => dayOf(r.date_entered) === today || dayOf(r.date_closed) === today
      );
    case 'open':
      return rows.filter((r) => !dayOf(r.date_closed));
    case 'closed':
      return rows.filter((r) => !!dayOf(r.date_closed));
    default:
      return rows;
  }
}

/** Add `deltaDays` to a YYYY-MM-DD key (local date-only arithmetic). */
export function shiftDateKey(dateKey: string, deltaDays: number): string {
  const [y, m, d] = dateKey.split('-').map(Number);
  const dt = new Date(y, m - 1, d + deltaDays);
  const yy = dt.getFullYear();
  const mm = String(dt.getMonth() + 1).padStart(2, '0');
  const dd = String(dt.getDate()).padStart(2, '0');
  return `${yy}-${mm}-${dd}`;
}

function isWeekend(dateKey: string): boolean {
  const [y, m, d] = dateKey.split('-').map(Number);
  const dow = new Date(y, m - 1, d).getDay();
  return dow === 0 || dow === 6;
}

export const RUNS_STRIP_DAYS = 14;

export type RunsStripStatus = 'ok' | 'error' | 'missed' | 'weekend';

export interface RunsStripCell {
  date: string;
  label: string;
  runs: WorkflowRun[];
  status: RunsStripStatus;
}

/**
 * Build the runs strip: the last `days` calendar days ending today, each cell
 * green (any run, all ok), red (any error/partial run), gray (weekday with no
 * run — a missed day), or faint (weekend).
 */
export function buildRunsStrip(
  runs: WorkflowRun[],
  today: string,
  days: number = RUNS_STRIP_DAYS
): RunsStripCell[] {
  const byDate = new Map<string, WorkflowRun[]>();
  for (const run of runs) {
    const key = dayOf(run.run_date);
    const list = byDate.get(key) ?? [];
    list.push(run);
    byDate.set(key, list);
  }
  const cells: RunsStripCell[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const key = shiftDateKey(today, -i);
    const dayRuns = byDate.get(key) ?? [];
    const status: RunsStripStatus = dayRuns.some(
      (r) => r.status === 'error' || r.status === 'partial'
    )
      ? 'error'
      : dayRuns.length > 0
        ? 'ok'
        : isWeekend(key)
          ? 'weekend'
          : 'missed';
    cells.push({ date: key, label: key.slice(5), runs: dayRuns, status });
  }
  return cells;
}

// ── Display helpers ──

function asNum(v: string | number | null | undefined): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function fmtPrice(v: string | null | undefined): string {
  const n = asNum(v);
  return n == null ? '—' : `$${n.toFixed(2)}`;
}

function fmtR(v: string | null | undefined): string {
  const n = asNum(v);
  return n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(2)}R`;
}

function rClass(v: string | null | undefined): string {
  const n = asNum(v);
  if (n == null) return 'text-text-muted';
  return n >= 0 ? 'text-green-500' : 'text-red-400';
}

const RUN_STATUS_CLASS: Record<RunsStripStatus, string> = {
  ok: 'bg-green-500/70',
  error: 'bg-red-500/70',
  missed: 'bg-border',
  weekend: 'bg-border/30',
};

function runTooltip(cell: RunsStripCell): string {
  if (cell.runs.length === 0) {
    return cell.status === 'weekend'
      ? `${cell.label}: weekend`
      : `${cell.label}: no run`;
  }
  return [
    cell.label,
    ...cell.runs.map((r) => `${r.mode} — ${r.message ?? ''}`),
  ].join('\n');
}

// ── Component ──

const TH = 'px-2 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wider text-text-muted';
const TD = 'px-2 py-1.5 text-xs whitespace-nowrap';

export function JournalTab() {
  const today = useMemo(() => todayKey(), []);
  const [filter, setFilter] = useState<JournalFilter>('all');

  const journalQuery = useQuery({
    queryKey: ['journal-all'],
    queryFn: getJournalAll,
    staleTime: 30_000,
  });
  const runsQuery = useQuery({
    queryKey: ['workflow-runs'],
    queryFn: () => getRuns(RUNS_STRIP_DAYS),
    staleTime: 30_000,
  });
  const rejectionsQuery = useQuery({
    queryKey: ['journal-rejections'],
    queryFn: () => getRejections(200),
    staleTime: 60_000,
  });

  const rows = journalQuery.data?.rows ?? [];
  const filtered = useMemo(
    () => filterJournalRows(rows, filter, today),
    [rows, filter, today]
  );
  const strip = useMemo(
    () => buildRunsStrip(runsQuery.data?.items ?? [], today),
    [runsQuery.data, today]
  );
  const rejections = rejectionsQuery.data?.items ?? [];

  const refetchAll = () => {
    void journalQuery.refetch();
    void runsQuery.refetch();
    void rejectionsQuery.refetch();
  };

  const counts: Record<JournalFilter, number> = useMemo(
    () => ({
      today: filterJournalRows(rows, 'today', today).length,
      open: filterJournalRows(rows, 'open', today).length,
      closed: filterJournalRows(rows, 'closed', today).length,
      all: rows.length,
    }),
    [rows, today]
  );

  return (
    <>
      {/* ── Runs strip ── */}
      <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <BookOpen className="h-4 w-4 text-accent" />
            Journal — runs, trades &amp; rejections
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={refetchAll}
              disabled={journalQuery.isFetching || runsQuery.isFetching}
              className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs text-text-muted transition-colors hover:text-text-primary disabled:opacity-40"
            >
              {journalQuery.isFetching || runsQuery.isFetching ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCw className="h-3 w-3" />
              )}
              Refresh
            </button>
            <a
              href={JOURNAL_EXPORT_URL}
              download
              className="btn-secondary flex items-center gap-1.5 px-3 py-1.5 text-xs"
            >
              <Download className="h-3.5 w-3.5" />
              Export CSV
            </a>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            {strip.map((cell) => (
              <div
                key={cell.date}
                title={runTooltip(cell)}
                className={cn(
                  'h-5 w-5 rounded-sm transition-colors',
                  RUN_STATUS_CLASS[cell.status]
                )}
              />
            ))}
          </div>
          <span className="text-[10px] text-text-muted">
            last {RUNS_STRIP_DAYS} days ·{' '}
            <span className="text-green-500">run</span> ·{' '}
            <span className="text-red-400">error</span> · missed
          </span>
        </div>
        {runsQuery.isError && (
          <p className="mt-2 text-xs text-red-400">
            Runs unavailable — is the backend running?
          </p>
        )}
      </section>

      {/* ── Trades table ── */}
      <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {JOURNAL_FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                filter === f.id
                  ? 'border-accent/30 bg-accent/10 text-accent'
                  : 'border-border/40 text-text-muted hover:text-text-primary'
              )}
            >
              {f.label}
              <span className="ml-1 text-[10px] opacity-70">{counts[f.id]}</span>
            </button>
          ))}
          <span className="ml-auto text-[10px] text-text-muted">
            journal of record: data/paper_trades.db · dates are ET
          </span>
        </div>

        {journalQuery.isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-accent" />
          </div>
        ) : filtered.length === 0 ? (
          <p className="py-4 text-center text-xs text-text-muted">
            {rows.length === 0
              ? 'No trades in the journal yet — press "Run After-Close (one go)" in Daily Routine.'
              : 'No rows match this filter.'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/30">
                  <th className={TH}>Date</th>
                  <th className={TH}>Symbol</th>
                  <th className={TH}>Verdict</th>
                  <th className={cn(TH, 'text-right')}>Entry</th>
                  <th className={cn(TH, 'text-right')}>Stop</th>
                  <th className={cn(TH, 'text-right')}>T1 / T2</th>
                  <th className={cn(TH, 'text-right')}>Size %</th>
                  <th className={TH}>Status</th>
                  <th className={cn(TH, 'text-right')}>R</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => {
                  const closed = !!dayOf(r.date_closed);
                  return (
                    <tr
                      key={`${r.date_entered}-${r.symbol}`}
                      className="border-b border-border/20 hover:bg-surface/30"
                    >
                      <td className={cn(TD, 'font-mono text-text-muted')}>
                        {r.date_entered ?? '—'}
                      </td>
                      <td className={cn(TD, 'font-semibold text-text-primary')}>
                        {r.symbol ?? '—'}
                        {r.action && (
                          <span className="ml-1.5 text-[10px] text-text-muted">
                            {r.action}
                          </span>
                        )}
                      </td>
                      <td className={TD}>
                        <span
                          className={cn(
                            'rounded-full border px-1.5 py-0.5 text-[10px] font-medium',
                            r.gate_verdict === 'PASS' &&
                              'border-green-500/30 text-green-500',
                            r.gate_verdict === 'CONDITIONAL' &&
                              'border-yellow-400/30 text-yellow-400',
                            r.gate_verdict === 'FAIL' &&
                              'border-red-400/30 text-red-400'
                          )}
                        >
                          {r.gate_verdict ?? '—'}
                        </span>
                      </td>
                      <td className={cn(TD, 'text-right font-mono')}>
                        {fmtPrice(r.entry_price)}
                      </td>
                      <td className={cn(TD, 'text-right font-mono')}>
                        {fmtPrice(r.stop_loss)}
                      </td>
                      <td
                        className={cn(TD, 'text-right font-mono text-text-muted')}
                      >
                        {fmtPrice(r.target_1)} / {fmtPrice(r.target_2)}
                      </td>
                      <td className={cn(TD, 'text-right font-mono')}>
                        {asNum(r.position_size_pct)?.toFixed(1) ?? '—'}
                      </td>
                      <td className={TD}>
                        {closed ? (
                          <span className="text-text-muted">
                            closed · {r.exit_reason ?? '—'}
                          </span>
                        ) : (
                          <span className="text-yellow-400">open</span>
                        )}
                      </td>
                      <td
                        className={cn(
                          TD,
                          'text-right font-mono',
                          rClass(r.realized_r)
                        )}
                      >
                        {closed ? fmtR(r.realized_r) : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {journalQuery.isError && (
          <p className="mt-2 text-xs text-red-400">
            Journal unavailable — is the backend running?
          </p>
        )}
      </section>

      {/* ── Rejections (collapsed) ── */}
      <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
        <details>
          <summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-text-primary">
            <XCircle className="h-4 w-4 text-accent" />
            Rejections — why candidates didn&apos;t become trades
            <span className="text-xs font-normal text-text-muted">
              ({rejections.length})
            </span>
          </summary>
          {rejections.length === 0 ? (
            <p className="mt-3 text-xs text-text-muted">
              No rejections logged yet.
            </p>
          ) : (
            <ul className="mt-3 space-y-1.5">
              {rejections.slice(0, 50).map((rej: JournalRejection) => (
                <li
                  key={rej.id}
                  className="flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded-md border border-border/20 bg-surface/10 px-2.5 py-1.5 text-xs"
                >
                  <span className="font-mono text-text-muted">
                    {rej.date_seen}
                  </span>
                  <span className="font-semibold text-text-primary">
                    {rej.symbol}
                  </span>
                  <span className="text-yellow-400">
                    {rej.failed_step ?? rej.gate_verdict ?? 'FAIL'}
                  </span>
                  <span className="text-text-muted">{rej.reason}</span>
                </li>
              ))}
            </ul>
          )}
        </details>
      </section>
    </>
  );
}

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
  Clock3,
  Download,
  FlaskConical,
  Loader2,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  JOURNAL_EXPORT_URL,
  getJournalAll,
  getPendingOrders,
  getReplayJournal,
  getRejections,
  getRuns,
  type JournalRejection,
  type JournalRow,
  type PendingOrder,
  type ReplayRun,
  type ReplayStats,
  type ReplayTrade,
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

function fmtPrice(v: string | number | null | undefined): string {
  const n = asNum(v);
  return n == null ? '—' : `$${n.toFixed(2)}`;
}

function fmtR(v: string | null | undefined): string {
  const n = asNum(v);
  return n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(2)}R`;
}

function rClass(v: string | number | null | undefined): string {
  const n = asNum(v);
  if (n == null) return 'text-text-muted';
  return n >= 0 ? 'text-green-500' : 'text-red-400';
}

function isFlagged(v: string | number | boolean | null | undefined): boolean {
  return v === 1 || v === '1' || v === true;
}

function pendingPrice(order: PendingOrder): string {
  if (order.order_type === 'moo') {
    return order.entry_high == null ? 'next open' : `≤ ${fmtPrice(order.entry_high)}`;
  }
  return fmtPrice(order.limit_price);
}

// ── Replay helpers (D-71) ──

export type ReplayFilter = 'all' | 'wins' | 'losses';

export const REPLAY_FILTERS: Array<{ id: ReplayFilter; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'wins', label: 'Winners' },
  { id: 'losses', label: 'Losers' },
];

/** Replay rows are already closed (the engine exits every trade). */
export function filterReplayRows(
  rows: ReplayTrade[],
  filter: ReplayFilter
): ReplayTrade[] {
  if (filter === 'wins') return rows.filter((r) => (r.pnl_usd ?? 0) > 0);
  if (filter === 'losses') return rows.filter((r) => (r.pnl_usd ?? 0) <= 0);
  return rows;
}

function fmtMoney(v: number | string | null | undefined): string {
  const n = asNum(v);
  if (n == null) return '—';
  const sign = n >= 0 ? '+' : '−';
  return `${sign}$${Math.abs(n).toLocaleString('en-US', {
    maximumFractionDigits: 0,
  })}`;
}

function fmtPct(v: number | null | undefined): string {
  return v == null ? '—' : `${(v * 100).toFixed(1)}%`;
}

function fmtPf(v: number | null | undefined): string {
  return v == null ? '—' : v.toFixed(2);
}

function Stat({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-surface/10 px-3 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-text-muted">
        {label}
      </div>
      <div className={cn('font-mono text-sm', className)}>{value}</div>
    </div>
  );
}

interface ReplayPanelProps {
  run: ReplayRun | null;
  rows: ReplayTrade[];
  summary: ReplayStats | null;
  isLoading: boolean;
  isError: boolean;
  isFetching: boolean;
  filter: ReplayFilter;
  onFilter: (f: ReplayFilter) => void;
  onRefresh: () => void;
}

function ReplayPanel({
  run,
  rows,
  summary,
  isLoading,
  isError,
  isFetching,
  filter,
  onFilter,
  onRefresh,
}: ReplayPanelProps) {
  const visible = useMemo(() => filterReplayRows(rows, filter), [rows, filter]);
  const counts: Record<ReplayFilter, number> = useMemo(
    () => ({
      all: rows.length,
      wins: filterReplayRows(rows, 'wins').length,
      losses: filterReplayRows(rows, 'losses').length,
    }),
    [rows]
  );
  const shown = visible.slice(0, 750);

  return (
    <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <FlaskConical className="h-4 w-4 text-accent" />
          Replay — deployed screens over the last{' '}
          {run?.params?.window_days ?? 60} days
        </h2>
        <button
          onClick={onRefresh}
          disabled={isFetching}
          className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs text-text-muted transition-colors hover:text-text-primary disabled:opacity-40"
        >
          {isFetching ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
          Refresh
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
        </div>
      ) : isError ? (
        <p className="py-4 text-center text-xs text-red-400">
          Replay unavailable — is the backend running?
        </p>
      ) : !run || !summary ? (
        <div className="py-4 text-center text-xs text-text-muted">
          <p>No replay generated yet.</p>
          <p className="mt-1">
            From the project root:{' '}
            <code className="rounded bg-surface/40 px-1 py-0.5 font-mono text-[11px] text-text-primary">
              python run_paper_replay.py
            </code>{' '}
            — then refresh.
          </p>
        </div>
      ) : (
        <>
          <div className="mb-3 rounded-lg border border-yellow-400/30 bg-yellow-400/5 px-3 py-2 text-[11px] leading-relaxed text-yellow-200/90">
            <span className="font-semibold">SIMULATED REPLAY</span> —{' '}
            {run.window_start} → {run.window_end} · {run.templates_count} deployed
            screens × {run.universe_count} symbols · entries at next open, ATR
            stop/target exits, {String(run.params?.max_hold_bars ?? 15)}-bar cap.
            TradingView&apos;s screener cannot be rewound, so this replays the
            templates (not the exact live brief) and never counts toward the
            forward scorecard.
          </div>

          <div className="mb-3 flex flex-wrap gap-2">
            <Stat label="Trades" value={String(summary.trades)} />
            <Stat
              label="Winners / Losers"
              value={`${summary.wins} W · ${summary.losses} L`}
            />
            <Stat
              label="Win rate"
              value={fmtPct(summary.win_rate)}
              className="text-text-primary"
            />
            <Stat
              label="Expectancy"
              value={`${summary.expectancy_r >= 0 ? '+' : ''}${summary.expectancy_r.toFixed(3)}R`}
              className={summary.expectancy_r >= 0 ? 'text-green-500' : 'text-red-400'}
            />
            <Stat label="Profit factor" value={fmtPf(summary.profit_factor_r)} />
            <Stat
              label={`P&L @ ${String(run.params?.risk_pct ?? 1)}% risk`}
              value={fmtMoney(summary.pnl_usd)}
              className={summary.pnl_usd >= 0 ? 'text-green-500' : 'text-red-400'}
            />
          </div>
          <p className="mb-3 text-[10px] text-text-muted">
            avg win {summary.avg_win_r >= 0 ? '+' : ''}
            {summary.avg_win_r.toFixed(2)}R · avg loss{' '}
            {summary.avg_loss_r.toFixed(2)}R · avg hold{' '}
            {summary.avg_hold_bars.toFixed(1)} bars ·{' '}
            {String(
              (run.metadata?.counts?.raw_signals ?? 0).toLocaleString('en-US')
            )}{' '}
            raw signals → {run.metadata?.counts?.after_regime_gate ?? 0}{' '}
            regime-gated → {summary.trades} entries
          </p>

          <div className="mb-3 flex flex-wrap items-center gap-2">
            {REPLAY_FILTERS.map((f) => (
              <button
                key={f.id}
                onClick={() => onFilter(f.id)}
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
              replay ledger: replay_trades · separate from the forward journal ·
              dates are ET
            </span>
          </div>

          {visible.length === 0 ? (
            <p className="py-4 text-center text-xs text-text-muted">
              No rows match this filter.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border/30">
                    <th className={TH}>Date</th>
                    <th className={TH}>Symbol</th>
                    <th className={TH}>Screen</th>
                    <th className={TH}>Regime</th>
                    <th className={cn(TH, 'text-right')}>Entry</th>
                    <th className={cn(TH, 'text-right')}>Stop</th>
                    <th className={cn(TH, 'text-right')}>Target</th>
                    <th className={TH}>Exit</th>
                    <th className={cn(TH, 'text-right')}>R</th>
                    <th className={cn(TH, 'text-right')}>P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r) => (
                    <tr
                      key={r.id}
                      className="border-b border-border/20 hover:bg-surface/30"
                    >
                      <td className={cn(TD, 'font-mono text-text-muted')}>
                        {r.signal_date ?? '—'} → {r.date_entered}
                      </td>
                      <td className={cn(TD, 'font-semibold text-text-primary')}>
                        {r.symbol}
                        {r.direction === 'short' && (
                          <span className="ml-1.5 text-[10px] text-red-400">
                            SHORT
                          </span>
                        )}
                      </td>
                      <td className={TD}>
                        <span title={r.notes ?? undefined}>{r.template ?? '—'}</span>
                        {r.screen_rank != null && (
                          <span className="ml-1 text-[10px] text-text-muted">
                            #{r.screen_rank}
                          </span>
                        )}
                        {r.also_signaled_by && (
                          <span
                            className="ml-1 text-[10px] text-text-muted"
                            title={`also signalled by: ${r.also_signaled_by}`}
                          >
                            +{r.also_signaled_by.split(',').length}
                          </span>
                        )}
                      </td>
                      <td className={cn(TD, 'text-text-muted')}>{r.regime ?? '—'}</td>
                      <td className={cn(TD, 'text-right font-mono')}>
                        {fmtPrice(r.entry_price)}
                      </td>
                      <td className={cn(TD, 'text-right font-mono')}>
                        {fmtPrice(r.stop_loss)}
                      </td>
                      <td className={cn(TD, 'text-right font-mono text-text-muted')}>
                        {fmtPrice(r.target_1)}
                      </td>
                      <td className={cn(TD, 'text-text-muted')}>
                        {r.exit_date ?? '—'} · {r.exit_reason ?? '—'}
                      </td>
                      <td className={cn(TD, 'text-right font-mono', rClass(r.realized_r))}>
                        {r.realized_r != null
                          ? `${r.realized_r >= 0 ? '+' : ''}${r.realized_r.toFixed(2)}R`
                          : '—'}
                      </td>
                      <td
                        className={cn(
                          TD,
                          'text-right font-mono',
                          rClass(r.pnl_usd)
                        )}
                      >
                        {fmtMoney(r.pnl_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visible.length > shown.length && (
                <p className="mt-2 text-center text-[10px] text-text-muted">
                  showing {shown.length} of {visible.length} rows — use the
                  filters or the JSON artifact for the full list
                </p>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
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
  const [mode, setMode] = useState<'live' | 'replay'>('live');
  const [replayFilter, setReplayFilter] = useState<ReplayFilter>('all');

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
  const pendingQuery = useQuery({
    queryKey: ['pending-orders'],
    queryFn: () => getPendingOrders(50),
    staleTime: 30_000,
  });
  const replayQuery = useQuery({
    queryKey: ['journal-replay'],
    queryFn: getReplayJournal,
    enabled: mode === 'replay',
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
  const pending = pendingQuery.data?.items ?? [];

  const refetchAll = () => {
    void journalQuery.refetch();
    void runsQuery.refetch();
    void rejectionsQuery.refetch();
    void pendingQuery.refetch();
    void replayQuery.refetch();
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

  const modeToggle = (
    <div className="flex w-fit items-center gap-1 rounded-lg border border-border/50 bg-surface/20 p-1">
      {(
        [
          { id: 'live', label: 'Live journal' },
          { id: 'replay', label: '2-month replay' },
        ] as const
      ).map((m) => (
        <button
          key={m.id}
          onClick={() => setMode(m.id)}
          className={cn(
            'rounded-md px-3 py-1 text-xs font-medium transition-colors',
            mode === m.id
              ? 'bg-accent/10 text-accent'
              : 'text-text-muted hover:text-text-primary'
          )}
        >
          {m.label}
        </button>
      ))}
    </div>
  );

  if (mode === 'replay') {
    return (
      <>
        {modeToggle}
        <ReplayPanel
          run={replayQuery.data?.run ?? null}
          rows={replayQuery.data?.rows ?? []}
          summary={replayQuery.data?.summary ?? null}
          isLoading={replayQuery.isLoading}
          isError={replayQuery.isError}
          isFetching={replayQuery.isFetching}
          filter={replayFilter}
          onFilter={setReplayFilter}
          onRefresh={() => void replayQuery.refetch()}
        />
      </>
    );
  }

  return (
    <>
      {modeToggle}
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
              disabled={
                journalQuery.isFetching ||
                runsQuery.isFetching ||
                pendingQuery.isFetching
              }
              className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs text-text-muted transition-colors hover:text-text-primary disabled:opacity-40"
            >
              {journalQuery.isFetching ||
              runsQuery.isFetching ||
              pendingQuery.isFetching ? (
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

      {/* ── Pending orders (D-73) ── */}
      <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Clock3 className="h-4 w-4 text-accent" />
            Pending orders — waiting for the next session
            <span className="text-xs font-normal text-text-muted">
              ({pending.length})
            </span>
          </h2>
          <span className="text-[10px] text-text-muted">
            signal after close → fill from actual T+1 bars · 3-session expiry
          </span>
        </div>

        {pendingQuery.isLoading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-accent" />
          </div>
        ) : pending.length === 0 ? (
          <p className="py-3 text-center text-xs text-text-muted">
            No pending orders. Accepted signals appear here after the
            after-close run; they never fill from the signal day.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/30">
                  <th className={TH}>Signal</th>
                  <th className={TH}>Symbol</th>
                  <th className={TH}>Order</th>
                  <th className={cn(TH, 'text-right')}>Limit / Cap</th>
                  <th className={cn(TH, 'text-right')}>Stop</th>
                  <th className={cn(TH, 'text-right')}>T1 / T2</th>
                  <th className={cn(TH, 'text-right')}>Size %</th>
                  <th className={TH}>Expires</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((o) => (
                  <tr
                    key={o.id}
                    className="border-b border-border/20 hover:bg-surface/30"
                  >
                    <td className={cn(TD, 'font-mono text-text-muted')}>
                      {o.signal_date}
                    </td>
                    <td className={cn(TD, 'font-semibold text-text-primary')}>
                      {o.symbol}
                      {o.action && (
                        <span className="ml-1.5 text-[10px] text-text-muted">
                          {o.action}
                        </span>
                      )}
                    </td>
                    <td className={TD}>
                      <span className="rounded-full border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-accent">
                        {o.order_type}
                      </span>
                    </td>
                    <td className={cn(TD, 'text-right font-mono')}>
                      {pendingPrice(o)}
                    </td>
                    <td className={cn(TD, 'text-right font-mono')}>
                      {fmtPrice(o.stop_loss)}
                    </td>
                    <td
                      className={cn(TD, 'text-right font-mono text-text-muted')}
                    >
                      {fmtPrice(o.target_1)} / {fmtPrice(o.target_2)}
                    </td>
                    <td className={cn(TD, 'text-right font-mono')}>
                      {asNum(o.position_size_pct)?.toFixed(1) ?? '—'}
                    </td>
                    <td className={cn(TD, 'text-text-muted')}>
                      {o.expires_after_sessions ?? 3} sessions
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {pendingQuery.isError && (
          <p className="mt-2 text-xs text-red-400">
            Pending orders unavailable — is the backend running?
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
              ? 'No fills yet — accepted signals appear under Pending orders and fill only from the next session.'
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
                  const voided = isFlagged(r.voided);
                  const excluded = isFlagged(r.exclude_from_stats);
                  return (
                    <tr
                      key={`${r.date_entered}-${r.symbol}`}
                      className={cn(
                        'border-b border-border/20 hover:bg-surface/30',
                        voided && 'opacity-60'
                      )}
                    >
                      <td className={cn(TD, 'font-mono text-text-muted')}>
                        {r.date_entered ?? '—'}
                      </td>
                      <td className={cn(TD, 'font-semibold text-text-primary')}>
                        {r.symbol ?? '—'}
                        {voided && (
                          <span
                            title={
                              r.void_reason ??
                              'Recorded fill never traded — kept for the audit trail'
                            }
                            className="ml-1.5 rounded-full border border-red-400/40 px-1.5 py-0.5 text-[9px] font-normal uppercase tracking-wide text-red-400"
                          >
                            void
                          </span>
                        )}
                        {excluded && !voided && (
                          <span
                            title="Pre-instrumentation row — visible, but excluded from the forward scorecard"
                            className="ml-1.5 rounded-full border border-border/60 px-1.5 py-0.5 text-[9px] font-normal uppercase tracking-wide text-text-muted"
                          >
                            out-of-sample
                          </span>
                        )}
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
                        {voided ? (
                          <span
                            className="text-red-400"
                            title={r.void_reason ?? undefined}
                          >
                            voided · excluded
                          </span>
                        ) : closed ? (
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
                        {closed && !voided ? fmtR(r.realized_r) : '—'}
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
                  {rej.template && (
                    <span className="text-text-muted">[{rej.template}]</span>
                  )}
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

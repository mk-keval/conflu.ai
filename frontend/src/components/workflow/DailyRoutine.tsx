/**
 * Daily Routine wizard (Slice 3 — Mission Surface).
 *
 * Renders the 2-touchpoint working-professional routine:
 *   1. Pre-Market (Touchpoint A) — Run gate enforcement via API, review gate tables
 *   2. After-Close (Touchpoint B) — Sync exits via API, review fills, apply, set plan_adherence
 *
 * Pure composition helpers are exported so the step ordering is unit-testable.
 */

import { useEffect, useMemo, useState } from 'react';
import {
  CalendarCheck2,
  CheckCircle2,
  Circle,
  ClipboardList,
  PlayCircle,
  Upload,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { useWorkflowStore } from '@/store/workflowStore';
import api from '@/api/client';
import { runClose, type RunCloseResult } from '@/api/workflow';
import type { DailyRoutine } from '@/types/workflow';

/** Local date key ("YYYY-MM-DD") for "today" — single helper so the basis is easy to change. */
export function todayKey(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Touchpoint A (Pre-Market) description and actions — now API-driven. */
export const TOUCHPOINT_A_ACTIONS = [
  'Click "Run Gate Enforcement" to fetch brief, evaluate gates, write journal',
  'Review 7-step gate table for each qualifying symbol',
  'Verify "no qualifying setups today" if empty',
  'Log any paper trades via Execution Engine',
] as const;

/** Touchpoint B (After-Close) description and actions — now API-driven. */
export const TOUCHPOINT_B_ACTIONS = [
  'Click "Sync Exits (Dry Run)" to review inferred fills',
  'Verify exit reasons (target/stop/time) and plan_adherence',
  'Click "Sync Exits (Apply)" to persist exits + set plan_adherence',
  'Reflect: did I follow the plan? (adherence score updates automatically)',
] as const;

/** Ordered step list with the still-pending "next" step highlighted (null-safe). */
export function routineStepList(routine: DailyRoutine | undefined) {
  if (!routine) return [];
  return routine.steps.map((s, i) => ({
    ...s,
    isNext: i === routine.currentStep && routine.status === 'in_progress',
  }));
}

/** Human-readable local time from an ISO timestamp, or null. */
export function formatStepTime(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** One-go run hint: before this elapsed time we're in the gate (enforce) phase. */
export const RUN_CLOSE_GATE_HINT_MS = 10_000;

/**
 * Stepped progress text for the one-go after-close run. The combined endpoint
 * does both touchpoints in a single call, so the phases are time-hinted:
 * gate enforcement (brief + per-ticker gates) runs first, then the exit sync.
 */
export function runCloseProgressText(elapsedMs: number): string {
  return elapsedMs < RUN_CLOSE_GATE_HINT_MS
    ? 'Running gate enforcement…'
    : 'Syncing exits…';
}

const STEP_ICONS: Record<number, typeof ClipboardList> = {
  1: CalendarCheck2,
  2: CheckCircle2,
};

export function DailyRoutine() {
  const date = todayKey();
  const routine = useWorkflowStore((s) => s.dailyRoutines[date]);
  const getOrCreateRoutine = useWorkflowStore((s) => s.getOrCreateRoutine);

  // Ensure a routine exists for today (idempotent create; persisted to localStorage).
  useEffect(() => {
    getOrCreateRoutine(date);
  }, [date, getOrCreateRoutine]);

  const steps = useMemo(() => routineStepList(routine), [routine]);
  const completeStep = useWorkflowStore((s) => s.completeRoutineStep);
  const hydrate = useWorkflowStore((s) => s.hydrateFromJournal);

  // API loading states
  const [enforceLoading, setEnforceLoading] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncDryRunLoading, setSyncDryRunLoading] = useState(false);
  const [enforceResult, setEnforceResult] = useState<{
    accepted: number;
    rejected: number;
    message: string;
  } | null>(null);
  const [syncResult, setSyncResult] = useState<{
    updated: number;
    skipped: number;
    message: string;
    applied: boolean;
    items: Array<{ 
      symbol: string; 
      exit_reason: string; 
      realized_r: number | null;
      applied: boolean;
    }>;
  } | null>(null);

  // One-go after-close run (D-68 P4): enforce → exits in a single call.
  const [runClosePhase, setRunClosePhase] = useState<
    'idle' | 'running' | 'done' | 'error'
  >('idle');
  const [runCloseElapsed, setRunCloseElapsed] = useState(0);
  const [runCloseResult, setRunCloseResult] = useState<RunCloseResult | null>(null);
  const [runCloseError, setRunCloseError] = useState<string | null>(null);

  // Tick the elapsed timer while the one-go run is in flight (stepped text).
  useEffect(() => {
    if (runClosePhase !== 'running') return;
    const started = Date.now();
    const timer = window.setInterval(
      () => setRunCloseElapsed(Date.now() - started),
      1000
    );
    return () => window.clearInterval(timer);
  }, [runClosePhase]);

  const handleRunClose = async () => {
    setRunClosePhase('running');
    setRunCloseElapsed(0);
    setRunCloseResult(null);
    setRunCloseError(null);
    try {
      const res = await runClose({ min_conviction: 5, apply_exits: true });
      setRunCloseResult(res);
      setRunClosePhase('done');
      // One button completes the whole after-close routine.
      completeStep(date, 1);
      completeStep(date, 2);
      void hydrate();
    } catch (e: any) {
      // The api client rejects with { code, message } objects (see client.ts).
      setRunCloseError(e?.message || 'Unknown error');
      setRunClosePhase('error');
    }
  };

  const handleRunGate = async () => {
    setEnforceLoading(true);
    setEnforceResult(null);
    try {
      const res = await api.post('/api/v1/workflow/paper-trades/enforce', {
        min_conviction: 5,
      });
      setEnforceResult({
        accepted: res.data.accepted?.length ?? 0,
        rejected: res.data.rejected?.length ?? 0,
        message: res.data.message ?? '',
      });
      void hydrate();
    } catch (e: any) {
      const msg = e?.response?.data?.error?.message
        || e?.response?.data?.message
        || e?.message
        || 'Unknown error';
      setEnforceResult({ accepted: 0, rejected: 0, message: `Error: ${msg}` });
    } finally {
      setEnforceLoading(false);
    }
  };

  const handleSyncExits = async (apply: boolean) => {
    if (apply) setSyncLoading(true);
    else setSyncDryRunLoading(true);
    setSyncResult(null);
    try {
      const res = await api.post('/api/v1/workflow/paper-trades/sync-exits', {
        apply,
      });
      setSyncResult({
        updated: res.data.updated ?? 0,
        skipped: res.data.skipped ?? 0,
        message: res.data.message ?? '',
        applied: apply,
        items: (res.data.items ?? []).map((item: any) => ({
          symbol: item.symbol,
          exit_reason: item.exit_reason,
          realized_r: item.realized_r,
          applied: item.applied ?? false,
        })),
      });
      if (apply) void hydrate();
    } catch (e: any) {
      const msg = e?.response?.data?.error?.message
        || e?.response?.data?.message
        || e?.message
        || 'Unknown error';
      setSyncResult({ updated: 0, skipped: 0, message: `Error: ${msg}`, applied: apply, items: [] });
    } finally {
      setSyncLoading(false);
      setSyncDryRunLoading(false);
    }
  };

  const progressPct =
    routine && routine.steps.length > 0
      ? (routine.steps.filter((s) => s.status === 'completed').length /
           routine.steps.length) *
         100
      : 0;
  const completedCount =
    routine?.steps.filter((s) => s.status === 'completed').length ?? 0;

  return (
    <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <CalendarCheck2 className="h-4 w-4 text-accent" />
          Daily Routine (2 Touchpoints)
        </h2>
        <span
          className={cn(
            'rounded-full border px-2 py-0.5 text-xs font-medium',
            routine?.status === 'completed'
              ? 'border-green-500/30 bg-green-500/10 text-green-500'
              : 'border-yellow-400/30 bg-yellow-400/10 text-yellow-400'
          )}
        >
          {routine?.status === 'completed' ? 'Completed' : 'In progress'}
        </span>
      </div>

      <p className="mb-3 text-xs text-text-muted">
        {date} - Default rhythm: press{' '}
        <span className="font-medium text-text-primary">
          Run After-Close (one go)
        </span>{' '}
        once after the close — it runs gate enforcement (entries) then applies
        exits in one call. Pre-market enforcement is optional; the individual
        touchpoints live under &quot;Manual steps&quot; in each step below.
      </p>

      {/* One-go after-close run (D-68 P4): one call = enforce + exits applied */}
      <div className="mb-4 rounded-lg border border-accent/30 bg-accent/5 p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
              <Sparkles className="h-4 w-4 text-accent" />
              After-Close (one go)
            </p>
            <p className="text-[11px] text-text-muted">
              Gate enforcement → exits applied → one run row. Entries logged
              today are skipped by the exit phase (exits start next session).
            </p>
          </div>
          <button
            onClick={handleRunClose}
            disabled={runClosePhase === 'running'}
            className="btn-primary gap-1.5 px-4 py-2 text-sm"
          >
            {runClosePhase === 'running' ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {runCloseProgressText(runCloseElapsed)}
              </>
            ) : (
              <>
                <PlayCircle className="h-4 w-4" />
                Run After-Close (one go)
              </>
            )}
          </button>
        </div>

        {runClosePhase === 'done' && runCloseResult && (
          <div className="mt-2 border-t border-accent/20 pt-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              <span
                className={
                  runCloseResult.enforce.accepted.length > 0
                    ? 'text-green-500'
                    : 'text-text-muted'
                }
              >
                ✓ {runCloseResult.enforce.accepted.length} accepted
              </span>
              <span
                className={
                  runCloseResult.enforce.rejected.length > 0
                    ? 'text-red-400'
                    : 'text-text-muted'
                }
              >
                ✗ {runCloseResult.enforce.rejected.length} rejected
              </span>
              <span
                className={
                  runCloseResult.exits.updated > 0
                    ? 'text-green-500'
                    : 'text-text-muted'
                }
              >
                ⇢ {runCloseResult.exits.updated} exit(s) applied
              </span>
              <span
                className={
                  runCloseResult.exits.skipped > 0
                    ? 'text-yellow-400'
                    : 'text-text-muted'
                }
              >
                ⊘ {runCloseResult.exits.skipped} skipped
              </span>
            </div>
            <p className="mt-1 text-[11px] text-text-muted">
              {runCloseResult.message}
            </p>
            <p className="mt-1 text-[11px] text-green-500">
              Both touchpoints marked done — see the Journal tab for the run
              row, trades and rejections.
            </p>
          </div>
        )}
        {runClosePhase === 'error' && (
          <p className="mt-2 border-t border-accent/20 pt-2 text-xs text-red-400">
            Run failed: {runCloseError}. A run row with status
            &quot;error&quot;/&quot;partial&quot; is still written when possible
            — check the backend log.
          </p>
        )}
      </div>

      {/* Step list */}
      <ol className="space-y-2">
        {steps.map((s) => {
          const Icon = STEP_ICONS[s.seq] ?? Circle;
          const done = s.status === 'completed';
          const isNext = s.isNext;
          return (
            <li
              key={s.seq}
              className={cn(
                'rounded-lg border p-3 transition-colors',
                done
                  ? 'border-green-500/30 bg-green-500/5'
                  : isNext
                    ? 'border-accent/40 bg-accent/5'
                    : 'border-border/40 bg-surface/10',
                !done && !isNext && 'opacity-50'
              )}
            >
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    'flex h-6 w-6 items-center justify-center rounded-full',
                    done
                      ? 'text-green-500'
                      : isNext
                        ? 'text-accent'
                        : 'text-text-muted'
                  )}
                >
                  {done ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-text-primary">
                      {s.seq}. {s.step}
                    </span>
                    {done && s.completedAt && (
                      <span className="text-[10px] text-text-muted">
                        done {formatStepTime(s.completedAt)}
                      </span>
                    )}
                  </div>
                  {!done && (
                    <div className="mt-1 text-[11px] text-text-muted">
                      {s.seq === 1
                        ? 'Touchpoint A: Run the pre-market script, review gate tables, log trades.'
                        : 'Touchpoint B: Sync exits, review fills, apply, set plan adherence.'}
                    </div>
                  )}
                </div>
                {isNext ? (
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">
                    Now
                  </span>
                ) : null}
              </div>

              {/* Touchpoint A: Pre-Market */}
              {isNext && s.seq === 1 && (
                <div className="mt-3 space-y-2 border-t border-border/30 pt-3">
                  <p className="text-xs font-medium text-text-primary">
                    Touchpoint A - Pre-Market (~10 min)
                  </p>
                  <ul className="space-y-1 text-xs text-text-secondary">
                    {TOUCHPOINT_A_ACTIONS.map((action, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <PlayCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
                        <span dangerouslySetInnerHTML={{ __html: action }} />
                      </li>
                    ))}
                  </ul>
                  <details className="rounded-md border border-border/30 bg-surface/10 px-3 py-2">
                    <summary className="cursor-pointer text-xs font-medium text-accent">
                      Manual steps — run gate enforcement only (pre-market)
                    </summary>
                    <div className="mt-2 space-y-2">
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={handleRunGate}
                          disabled={enforceLoading}
                          className="btn-primary gap-1.5 px-3 py-2 text-sm"
                        >
                          {enforceLoading ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Running gate...
                            </>
                          ) : (
                            <>
                              <PlayCircle className="h-4 w-4" />
                              Run Gate Enforcement
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => completeStep(date, 1)}
                          disabled={!enforceResult}
                          className="btn-secondary gap-1.5 px-3 py-2 text-sm"
                        >
                          <CheckCircle2 className="h-4 w-4" />
                          Mark Pre-Market Done
                        </button>
                      </div>
                      {enforceResult && (
                        <div className="text-xs text-text-secondary space-y-1">
                          <span className={enforceResult.accepted > 0 ? 'text-green-500' : 'text-text-muted'}>
                            ✓ {enforceResult.accepted} accepted
                          </span>
                          <span className={enforceResult.rejected > 0 ? 'text-red-400' : 'text-text-muted'}>
                            ✗ {enforceResult.rejected} rejected
                          </span>
                          <span>{enforceResult.message}</span>
                        </div>
                      )}
                      {!enforceResult && !enforceLoading && (
                        <span className="text-[11px] text-text-muted">
                          Run gate enforcement first, then mark complete
                        </span>
                      )}
                    </div>
                  </details>
                </div>
              )}

              {/* Touchpoint B: After-Close */}
              {isNext && s.seq === 2 && (
                <div className="mt-3 space-y-2 border-t border-border/30 pt-3">
                  <p className="text-xs font-medium text-text-primary">
                    Touchpoint B - After-Close (~2 min)
                  </p>
                  <ul className="space-y-1 text-xs text-text-secondary">
                    {TOUCHPOINT_B_ACTIONS.map((action, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <Upload className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
                        <span dangerouslySetInnerHTML={{ __html: action }} />
                      </li>
                    ))}
                  </ul>
                  <details className="rounded-md border border-border/30 bg-surface/10 px-3 py-2">
                    <summary className="cursor-pointer text-xs font-medium text-accent">
                      Manual steps — review + apply exits separately
                    </summary>
                    <div className="mt-2 space-y-2">
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => handleSyncExits(false)}
                          disabled={syncDryRunLoading}
                          className="btn-secondary gap-1.5 px-3 py-2 text-sm"
                        >
                          {syncDryRunLoading ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Dry run...
                            </>
                          ) : (
                            <>
                              <Upload className="h-4 w-4" />
                              Sync Exits (Dry Run)
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => handleSyncExits(true)}
                          disabled={syncLoading || !syncResult}
                          className="btn-primary gap-1.5 px-3 py-2 text-sm"
                        >
                          {syncLoading ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Applying...
                            </>
                          ) : (
                            <>
                              <CheckCircle2 className="h-4 w-4" />
                              Sync Exits (Apply)
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => completeStep(date, 2)}
                          disabled={!syncResult || !syncResult.applied}
                          className="btn-secondary gap-1.5 px-3 py-2 text-sm"
                        >
                          <CheckCircle2 className="h-4 w-4" />
                          Mark After-Close Done
                        </button>
                      </div>
                      {syncResult && (
                        <div className="text-xs text-text-secondary space-y-1 max-h-40 overflow-y-auto">
                          <span className={syncResult.updated > 0 ? 'text-green-500' : 'text-text-muted'}>
                            ✓ {syncResult.updated} exit(s) {syncResult.applied ? 'applied' : 'would apply'}
                          </span>
                          <span className={syncResult.skipped > 0 ? 'text-yellow-400' : 'text-text-muted'}>
                            ⊘ {syncResult.skipped} skipped
                          </span>
                          <span>{syncResult.message}</span>
                          {syncResult.items.length > 0 && (
                            <details className="mt-1">
                              <summary className="text-accent cursor-pointer">Show details</summary>
                              <ul className="mt-1 space-y-1 text-[10px]">
                                {syncResult.items.slice(0, 10).map((item, i) => (
                                  <li key={i} className="flex gap-2">
                                    <span className="font-mono">{item.symbol}</span>
                                    <span>{item.exit_reason}</span>
                                    <span className={item.realized_r != null && item.realized_r >= 0 ? 'text-green-500' : 'text-red-400'}>
                                      {item.realized_r == null ? '—' : `${item.realized_r >= 0 ? '+' : ''}${item.realized_r.toFixed(2)}R`}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </details>
                          )}
                        </div>
                      )}
                      {!syncResult && !syncLoading && !syncDryRunLoading && (
                        <span className="text-[11px] text-text-muted">
                          Run sync-exits dry run first, then apply, then mark complete
                        </span>
                      )}
                    </div>
                  </details>
                </div>
              )}

              {/* Non-active steps complete with a single action. */}
              {isNext && !done && s.seq !== 1 && s.seq !== 2 && (
                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={() => completeStep(date, s.seq)}
                    className="btn-primary gap-1.5 px-3 py-1.5 text-sm"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    Mark {s.step} Done
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ol>

      {/* Progress */}
      <div className="mt-4 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <span className="text-[11px] text-text-muted">
          {completedCount}/{steps.length} touchpoints
        </span>
      </div>
    </section>
  );
}

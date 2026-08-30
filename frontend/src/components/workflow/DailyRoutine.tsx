/**
 * Daily Routine wizard (Phase 1, Sprint 2 — gap #4, in-flow guided learning).
 *
 * Renders the 4-step working-professional routine (Pre-Market → Market Open →
 * Mid-Day → After-Close Journal) and advances it strictly in order through the
 * persisted `useWorkflowStore`. The After-Close Journal (step 4) is the
 * mandatory journaling step: it surfaces a 3-question thesis-vs-reality prompt
 * and persists the answers into the step payload.
 *
 * Pure composition helpers are exported (not `default`) so the journal payload
 * and step ordering are unit-testable without a DOM (see `__tests__/`).
 */

import { useEffect, useMemo, useState } from 'react';
import {
  CalendarCheck2,
  CheckCircle2,
  Circle,
  ClipboardList,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { TermLink } from '@/components/learn/TermLink';
import { useWorkflowStore } from '@/store/workflowStore';
import type {
  DailyRoutine,
  RoutineStepSeq,
} from '@/types/workflow';

/** Local date key ("YYYY-MM-DD") for "today" — single helper so the basis is easy to change. */
export function todayKey(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** The 3-question thesis-vs-reality journal prompt shown at step 4. */
export const JOURNAL_QUESTIONS = [
  {
    key: 'q1',
    label: 'What was my original thesis for today’s trades?',
  },
  {
    key: 'q2',
    label: 'What actually happened versus my thesis?',
  },
  {
    key: 'q3',
    label: 'What would I do differently next time?',
  },
] as const;

export type JournalData = Record<string, string>;

/** Build the journal `data` payload persisted onto the routine’s step 4. */
export function buildJournalData(answers: JournalData): Record<string, unknown> {
  return { ...answers, journaledAt: new Date().toISOString() };
}

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

const STEP_ICONS: Record<number, typeof ClipboardList> = {
  1: CalendarCheck2,
  2: ClipboardList,
  3: Circle,
  4: CheckCircle2,
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

  const [journal, setJournal] = useState<JournalData>({});
  const completeStep = useWorkflowStore((s) => s.completeRoutineStep);

  const handleCompleteStep = (seq: RoutineStepSeq) => {
    if (seq === 4) {
      completeStep(date, 4, buildJournalData(journal));
    } else {
      completeStep(date, seq);
    }
  };

  const progressPct =
    routine && routine.steps.length > 0
      ? (routine.steps.filter((s) => s.status === 'completed').length / routine.steps.length) * 100
      : 0;
  const completedCount = routine?.steps.filter((s) => s.status === 'completed').length ?? 0;

  return (
    <section className="rounded-xl border border-border/50 bg-surface/20 p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-text-primary flex items-center gap-2">
          <CalendarCheck2 className="h-4 w-4 text-accent" />
          Daily Routine
        </h2>
        <span
          className={cn(
            'text-xs font-medium px-2 py-0.5 rounded-full border',
            routine?.status === 'completed'
              ? 'text-green-500 bg-green-500/10 border-green-500/30'
              : 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30'
          )}
        >
          {routine?.status === 'completed' ? 'Completed' : 'In progress'}
        </span>
      </div>

      <p className="text-xs text-text-muted mb-4">
        {date} · Complete each step in order. Step 4 (After-Close Journal) is the
        mandatory reflection that builds your trading discipline.
      </p>

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
                    done ? 'text-green-500' : isNext ? 'text-accent' : 'text-text-muted'
                  )}
                >
                  {done ? <CheckCircle2 className="h-5 w-5" /> : <Icon className="h-4 w-4" />}
                </span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-text-primary">
                      {s.seq}. {s.step}
                    </span>
                    {done && s.completedAt && (
                      <span className="text-[10px] text-text-muted">done {formatStepTime(s.completedAt)}</span>
                    )}
                  </div>
                  {!done && s.seq === 4 && (
                    <div className="text-[11px] text-text-muted">
                      Reflect on today — the journal is what builds discipline.
                    </div>
                  )}
                </div>
                {isNext && s.seq === 4 ? (
                  <span className="text-[10px] font-semibold text-accent uppercase tracking-wider">Now</span>
                ) : isNext ? (
                  <span className="text-[10px] font-semibold text-accent uppercase tracking-wider">Next</span>
                ) : null}
              </div>

              {/* Journal prompt surfaces only on the active final (4th) step. */}
              {isNext && s.seq === 4 && (
                <div className="mt-3 space-y-3 border-t border-border/30 pt-3">
                  {JOURNAL_QUESTIONS.map((q) => (
                    <div key={q.key}>
                      <div className="block text-xs font-medium text-text-primary mb-1">
                        <TermLink text={q.label} />
                      </div>
                      <textarea
                        value={journal[q.key] ?? ''}
                        onChange={(e) =>
                          setJournal((prev) => ({ ...prev, [q.key]: e.target.value }))
                        }
                        rows={2}
                        placeholder="Type your thoughts…"
                        className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50"
                      />
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleCompleteStep(4)}
                      className="btn-primary gap-1.5 px-3 py-2 text-sm"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      Complete Journal &amp; Routine
                    </button>
                    <span className="text-[11px] text-text-muted">
                      Saving to this device’s local storage
                    </span>
                  </div>
                </div>
              )}

              {/* Non-journal steps complete with a single action. */}
              {isNext && s.seq !== 4 && (
                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={() => handleCompleteStep(s.seq)}
                    className="btn-primary gap-1.5 px-3 py-1.5 text-sm"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    Mark {s.step} Done
                  </button>
                  {s.seq === 1 && (
                    <span className="text-[11px] text-text-muted">
                      Review regime pulse + watchlist before the open
                    </span>
                  )}
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
          {completedCount}/{steps.length} steps
        </span>
      </div>
    </section>
  );
}

/**
 * Paper-Trade Logger modal (Phase 1, Sprint 5 — gap #4, the learning loop).
 *
 * Launched from the Execution Engine ("Log Paper Trade") once a position is
 * sized. It:
 *   1. Records the plan as an OPEN paper trade via `workflowStore.openPaperTrade`
 *      (localStorage, no backend).
 *   2. Presents the shared 13-step plan-steps checklist (see `workflow/planSteps.ts`)
 *      grouped by category, seeded sensibly from the execution plan.
 *   3. On close, scores the checked steps into `(stepsFollowed, stepsTotal)` and
 *      persists the trade + adherence via `workflowStore.closePaperTrade`, then
 *      shows the resulting adherence %. The rolling 20-trade meter derives from
 *      these stored trades (`useAdherence`).
 */

import { useState } from 'react';
import { X, PlayCircle, ClipboardList, CheckCircle2, Flag } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useWorkflowStore, useAdherence, ADHERENCE_WINDOW } from '@/store/workflowStore';
import { PLAN_STEP_DEFS, PLAN_STEP_COUNT, scorePlanSteps, planStepGroups } from '@/workflow/planSteps';
import { adherencePct } from '@/workflow/adherence';
import type { ExecutionPlan } from '@/workflow/execution';
import type { ExecutionSetup, PaperTradeOutcome } from '@/types/workflow';
import { TermLink } from '@/components/learn/TermLink';

export interface PaperTradeLoggerProps {
  open: boolean;
  onClose: () => void;
  /** Execution setup (symbol, entry/stop, time stop) for the paper-trade record. */
  setup: ExecutionSetup;
  /** Computed execution plan (tranches/targets/OCO) from the Execution Engine. */
  plan: ExecutionPlan;
}

type CloseOutcome = Exclude<PaperTradeOutcome, 'open'>;

const CLOSE_OUTCOMES: Array<{ value: CloseOutcome; label: string }> = [
  { value: 'target_hit', label: 'Hit target(s)' },
  { value: 'stop_hit', label: 'Hit stop' },
  { value: 'time_stop', label: 'Time stop' },
  { value: 'flat', label: 'Closed flat / manual' },
];

/** Seed the 13-step checklist from the plan: gate + entries assumed followed. */
function defaultChecked(plan: ExecutionPlan): boolean[] {
  return PLAN_STEP_DEFS.map((s, i) => {
    if (s.key === 'validation_gate') return true;
    if (s.key === 'entry_tranches') {
      const idx = PLAN_STEP_DEFS.slice(0, i).filter((x) => x.key === s.key).length;
      return (plan.tranches[idx]?.qty ?? 0) > 0;
    }
    return false;
  });
}

export function PaperTradeLogger({ open, onClose, setup, plan }: PaperTradeLoggerProps) {
  const openTrade = useWorkflowStore((s) => s.openPaperTrade);
  const closeTrade = useWorkflowStore((s) => s.closePaperTrade);
  const adherence = useAdherence();

  const [phase, setPhase] = useState<'draft' | 'live' | 'closed'>('draft');
  const [tradeId, setTradeId] = useState<string | null>(null);
  const [checked, setChecked] = useState<boolean[]>(() => defaultChecked(plan));
  const [outcome, setOutcome] = useState<CloseOutcome>('target_hit');
  const [resultPct, setResultPct] = useState(0);

  if (!open) return null;

  const toggleStep = (i: number) =>
    setChecked((prev) => prev.map((v, idx) => (idx === i ? !v : v)));

  const handleOpen = () => {
    const trade = openTrade({
      symbol: setup.symbol,
      plan: {
        entryMid: setup.entryMid,
        stopLoss: setup.stopLoss,
        timeStopDays: plan.timeStopDays,
        convictionLevel: plan.convictionLevel,
        totalShares: plan.totalShares,
        tranches: plan.tranches,
        targets: plan.targets,
        oco: plan.oco,
      },
      fills: {},
      stepsFollowed: 0,
      stepsTotal: PLAN_STEP_COUNT,
    });
    setTradeId(trade.id);
    setChecked(defaultChecked(plan));
    setPhase('live');
  };

  const handleClose = () => {
    if (!tradeId) return;
    const { stepsFollowed, stepsTotal } = scorePlanSteps(checked);
    closeTrade(tradeId, outcome, stepsFollowed, stepsTotal);
    setResultPct(adherencePct(stepsFollowed, stepsTotal));
    setPhase('closed');
  };

  const groups = planStepGroups();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-border/50 bg-surface-elevated p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between mb-1">
          <div className="flex items-center gap-2">
            <ClipboardList className="h-5 w-5 text-accent" />
            <h2 className="text-base font-semibold text-text-primary">
              Paper Trade — {setup.symbol}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="text-xs text-text-muted mb-4">
          Record your plan, then check off what actually happened. Your adherence
          score is what the 20-trade dashboard measures.
        </p>

        {phase === 'draft' && (
          <>
            <PlanSummary setup={setup} plan={plan} />
            <div className="mt-4 flex items-center gap-3">
              <button onClick={handleOpen} className="btn-primary gap-1.5 px-4 py-2 text-sm">
                <PlayCircle className="h-4 w-4" />
                Record open trade
              </button>
              <button
                onClick={onClose}
                className="px-3 py-2 text-sm text-text-muted hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
            </div>
          </>
        )}

        {phase === 'live' && (
          <>
            <p className="text-sm mb-2">
              Check the <span className="font-semibold text-text-primary">13 plan steps</span> you
              followed while this trade was open.
            </p>
            <div className="space-y-4">
              {groups.map((g) => (
                <fieldset key={g.group}>
                  <legend className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-1.5">
                    {g.group}
                  </legend>
                  <div className="space-y-1">
                    {g.steps.map((step) => {
                      const globalIdx = PLAN_STEP_DEFS.indexOf(step);
                      const on = checked[globalIdx] === true;
                      return (
                        <label
                          key={step.label}
                          className={cn(
                            'flex items-start gap-2.5 rounded-md border px-3 py-2 text-sm cursor-pointer transition-colors',
                            on
                              ? 'border-accent/30 bg-accent/5'
                              : 'border-border/20 bg-border/5 hover:bg-border/10'
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={on}
                            onChange={() => toggleStep(globalIdx)}
                            className="mt-0.5 accent-accent"
                          />
                          <span className="flex flex-col">
                            <span className="text-text-primary">{step.label}</span>
                            {step.help && (
                              <span className="text-[11px] text-text-muted">{step.help}</span>
                            )}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </fieldset>
              ))}
            </div>

            {/* Outcome */}
            <div className="mt-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-1.5">
                How did it close?
              </div>
              <div className="flex flex-wrap gap-2">
                {CLOSE_OUTCOMES.map((o) => (
                  <button
                    key={o.value}
                    onClick={() => setOutcome(o.value)}
                    className={cn(
                      'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                      outcome === o.value
                        ? 'bg-accent/10 border-accent/30 text-accent'
                        : 'border-border/40 text-text-muted hover:text-text-primary'
                    )}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 flex items-center gap-3">
              <button onClick={handleClose} className="btn-primary gap-1.5 px-4 py-2 text-sm">
                <Flag className="h-4 w-4" />
                Close &amp; score
              </button>
              <button
                onClick={onClose}
                className="px-3 py-2 text-sm text-text-muted hover:text-text-primary transition-colors"
              >
                Close
              </button>
            </div>
          </>
        )}

        {phase === 'closed' && (
          <>
            <div className="rounded-lg border border-accent/30 bg-accent/5 p-4 text-center">
              <CheckCircle2 className="h-8 w-8 text-accent mx-auto mb-2" />
              <div className="text-3xl font-bold text-text-primary">{resultPct}%</div>
              <div className="text-xs text-text-muted mt-1">
                plan adherence for {setup.symbol}
              </div>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Rolling {ADHERENCE_WINDOW}-trade adherence:{' '}
              <span className="font-semibold text-text-primary">
                {adherence.rolling.pct}% ({adherence.rolling.count} trades)
              </span>
              {' · '}streak:{' '}
              <span className="font-semibold text-text-primary">{adherence.streak}</span>
            </p>
            <div className="mt-4">
              <button onClick={onClose} className="btn-primary px-4 py-2 text-sm">
                Done
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function PlanSummary({ setup, plan }: { setup: ExecutionSetup; plan: ExecutionPlan }) {
  return (
    <div className="rounded-lg border border-border/40 bg-surface/20 p-3 space-y-1 text-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-1">
        Plan you’re logging
      </div>
      <div className="flex justify-between">
        <span className="text-text-muted">Shares</span>
        <span className="font-mono text-text-primary">{plan.totalShares}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-text-muted">Entry mid</span>
        <span className="font-mono text-text-primary">${setup.entryMid.toFixed(2)}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-text-muted">Stop</span>
        <span className="font-mono text-text-primary">${setup.stopLoss.toFixed(2)}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-text-muted">Time stop</span>
        <span className="font-mono text-text-primary">{plan.timeStopDays} days</span>
      </div>
      <div className="flex justify-between">
        <span className="text-text-muted">Tranches filled</span>
        <span className="font-mono text-text-primary">
          {plan.tranches.filter((t) => t.qty > 0).length}/3
        </span>
      </div>
      <p className="text-[11px] text-text-muted pt-1">
        Adherence = plan steps followed / 13. <TermLink text="Adherence" /> rewards discipline, not
        outcome — a stopped-out trade can still score high if you followed the plan.
      </p>
    </div>
  );
}

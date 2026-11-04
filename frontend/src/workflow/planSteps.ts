/**
 * Paper-trade plan-step taxonomy (Phase 1, Sprint 5 — gap #4, guided loop).
 *
 * Expands the shared `PAPER_TRADE_PLAN_STEPS` constant from `types/workflow.ts`
 * into 13 labeled, grouped checklist items a beginner ticks off against what
 * actually happened, and scores them into `(stepsFollowed, stepsTotal)` for the
 * store's `closePaperTrade`. Kept pure so the 13-step count and scoring are
 * unit-testable without a DOM or React.
 */

import { PAPER_TRADE_PLAN_STEPS } from '../types/workflow';

export type PlanStepGroup =
  | 'Validation Gate'
  | 'Entry'
  | 'Execution Discipline';

export interface PlanStepDef {
  /** Stable key (one of the five taxonomy categories). */
  key: keyof typeof PAPER_TRADE_PLAN_STEPS;
  /** Human label for the checklist item. */
  label: string;
  /** Short plain-English explainer (TermLink-friendly host passes glosses). */
  help?: string;
  /** UI grouping for rendering. */
  group: PlanStepGroup;
}

/**
 * The full 13-step checklist, in display order, grouped by category.
 * Length must equal ADHERENCE_MAX_STEPS (13).
 */
export const PLAN_STEP_DEFS: PlanStepDef[] = [
  // Validation Gate (5)
  {
    key: 'validation_gate',
    group: 'Validation Gate',
    label: 'Liquidity check passed',
    help: 'Enough daily volume to get in/out without moving price',
  },
  {
    key: 'validation_gate',
    group: 'Validation Gate',
    label: 'Structure aligned (W>D)',
    help: 'Weekly and daily trends agree with your direction',
  },
  {
    key: 'validation_gate',
    group: 'Validation Gate',
    label: 'Risk/Reward reached 2.5R',
    help: 'Upside to target at least 2.5x the risk at the stop',
  },
  {
    key: 'validation_gate',
    group: 'Validation Gate',
    label: 'Edge check (conviction + catalyst)',
    help: 'Positioning and a catalyst supported the entry',
  },
  {
    key: 'validation_gate',
    group: 'Validation Gate',
    label: 'Conviction scored',
    help: 'You committed to a 0-10 conviction score',
  },
  // Entry (3)
  {
    key: 'entry_tranches',
    group: 'Entry',
    label: 'Entered tranche 1 (40%)',
    help: 'First piece filled at the trigger',
  },
  {
    key: 'entry_tranches',
    group: 'Entry',
    label: 'Entered tranche 2 (30%)',
    help: 'Second piece filled at the trigger',
  },
  {
    key: 'entry_tranches',
    group: 'Entry',
    label: 'Entered tranche 3 (30%)',
    help: 'Final piece filled at the trigger',
  },
  // Execution Discipline (stop respected 1, target hits 3, time stop 1)
  {
    key: 'stop_respected',
    group: 'Execution Discipline',
    label: 'Stop respected (no lowering)',
    help: 'You did not widen the protective stop',
  },
  {
    key: 'target_hits',
    group: 'Execution Discipline',
    label: 'Scaled out at target 1',
    help: 'Banked the first piece of profit',
  },
  {
    key: 'target_hits',
    group: 'Execution Discipline',
    label: 'Scaled out at target 2',
    help: 'Banked the second piece of profit',
  },
  {
    key: 'target_hits',
    group: 'Execution Discipline',
    label: 'Scaled out at target 3',
    help: 'Banked the final piece of profit',
  },
  {
    key: 'time_stop_honored',
    group: 'Execution Discipline',
    label: 'Time stop honored',
    help: 'Exited when the thesis had its allotted days',
  },
];

/** Total checklist length — must equal the 13-step taxonomy. */
export const PLAN_STEP_COUNT: number = PLAN_STEP_DEFS.length;

/**
 * Score a completed checklist into adherence counts. `completed` is indexed to
 * `PLAN_STEP_DEFS`; a shorter array treats missing entries as not followed.
 * stepsTotal is always the full taxonomy (13) so the metric is comparable
 * across trades.
 */
export function scorePlanSteps(completed: boolean[]): {
  stepsFollowed: number;
  stepsTotal: number;
} {
  const total = PLAN_STEP_DEFS.length;
  let followed = 0;
  for (let i = 0; i < total; i++) {
    if (completed[i] === true) followed += 1;
  }
  return { stepsFollowed: followed, stepsTotal: total };
}

/** Group the defs by their UI group, preserving order. */
export function planStepGroups(): Array<{
  group: PlanStepGroup;
  steps: PlanStepDef[];
}> {
  const order: PlanStepGroup[] = [
    'Validation Gate',
    'Entry',
    'Execution Discipline',
  ];
  return order.map((group) => ({
    group,
    steps: PLAN_STEP_DEFS.filter((s) => s.group === group),
  }));
}

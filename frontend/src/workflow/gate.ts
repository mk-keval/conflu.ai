/**
 * Validation Gate renderer (Phase 1 — Sprint 3, gap #4).
 *
 * The gate is a **backend-owned** advisory assessment. The frontend ONLY renders
 * the backend's computed result — it does NOT re-evaluate the gate steps.
 *
 * This follows the single-decider principle: the gate logic lives in
 * `backend/app/domain/workflow/gate.py` and the frontend displays it with
 * teach-first copy. Two implementations of the same rule would drift silently.
 *
 * Data availability is honest — when a signal is missing the backend returns
 * CONDITIONAL (not a false pass), so a beginner is never misled into thinking a
 * step "passed" when we couldn't actually verify it.
 */

import type { GateStepName, GateVerdict } from '../types/workflow';
import type { ValidationGate } from '../types/workflow';

export type { ValidationGate };

/** Plain-English question for each gate step, in order (7 steps, mirrors backend). */
export const GATE_STEPS: readonly {
  name: GateStepName;
  question: string;
}[] = [
  {
    name: 'Liquidity',
    question: 'Is there enough trading volume to get in and out easily?',
  },
  {
    name: 'Structure',
    question: 'Is the higher-timeframe trend lining up with the setup?',
  },
  {
    name: 'Positioning',
    question:
      'Is crowded positioning (short interest / institutional flow) a headwind?',
  },
  {
    name: 'Catalyst',
    question: 'Does a near-term catalyst support the trade?',
  },
  {
    name: 'Risk/Reward',
    question: 'Is the potential reward at least 2.5× the risk I am taking?',
  },
  {
    name: 'Portfolio Fit',
    question: 'Does size fit my open book, account risk, and current exposure?',
  },
  {
    name: 'Conviction',
    question: 'How confident am I overall, on a 0–10 scale?',
  },
];

/** Practical floor for "liquid enough to swing" — average daily $ volume. */
export const LIQUIDITY_MIN_AVG_DAILY_USD = 10_000_000;

/** Minimum reward:risk for a PASS (elite swing floor). */
export const RISK_REWARD_PASS = 2.5;

/** Reward:risk between this and the PASS floor is CONDITIONAL (D1 tier: half-size). */
export const RISK_REWARD_CONDITIONAL = 2.0;

/** Conviction >= this, with a non-negative catalyst, earns a strong Edge. */
export const CONVICTION_HIGH = 7;

/** Conviction below this is a weak edge. */
export const CONVICTION_LOW = 4;

/**
 * Render a backend GateResult into a display-friendly format.
 * The backend owns the evaluation logic; this function only formats for UI.
 */
export function renderGateResult(backendGate: ValidationGate): {
  overall: GateVerdict;
  steps: Array<{
    name: GateStepName;
    status: 'pass' | 'fail' | 'conditional';
    note: string;
    question: string;
  }>;
  convictionScore: number;
  dataGaps: string[];
  evaluatedAt: string;
} {
  const stepMap = new Map(GATE_STEPS.map((s) => [s.name, s.question]));

  const steps = backendGate.stepResults.map((step) => ({
    name: step.name,
    status:
      step.passed && !step.conditional
        ? ('pass' as const)
        : step.conditional
          ? ('conditional' as const)
          : ('fail' as const),
    note: step.note ?? '',
    question: stepMap.get(step.name) ?? '',
  }));

  return {
    overall: backendGate.overall,
    steps,
    convictionScore: backendGate.convictionScore,
    dataGaps: backendGate.dataGaps,
    evaluatedAt: backendGate.evaluatedAt,
  };
}

/**
 * Get a human-readable summary of the gate verdict for display in lists/cards.
 */
export function gateSummary(backendGate: ValidationGate): string {
  const { overall, convictionScore } = backendGate;
  const passedSteps = backendGate.stepResults.filter(
    (s) => s.passed && !s.conditional
  ).length;
  const totalSteps = backendGate.stepResults.length;

  if (overall === 'PASS') {
    return `✅ PASS (${passedSteps}/${totalSteps} steps) • Conviction ${convictionScore}/10`;
  }
  if (overall === 'CONDITIONAL') {
    const conditionalSteps = backendGate.stepResults.filter(
      (s) => s.conditional
    ).length;
    return `⚠️ CONDITIONAL (${passedSteps}/${totalSteps} pass, ${conditionalSteps} conditional) • Conviction ${convictionScore}/10 — half-size`;
  }
  return `❌ FAIL (${passedSteps}/${totalSteps} pass) • Conviction ${convictionScore}/10`;
}

/**
 * Check if a gate result has any data gaps (steps that were CONDITIONAL due to missing inputs).
 */
export function hasDataGaps(backendGate: ValidationGate): boolean {
  return backendGate.dataGaps.length > 0;
}

/**
 * Get the "nearest miss" message for days when nothing passes.
 * Mirrors the backend's explained empty-day message (Sec.7, Slice 3).
 */
export function nearestMissMessage(backendGate: ValidationGate): string | null {
  if (backendGate.overall === 'PASS') return null;

  // Find the step that came closest to passing
  const conditionalSteps = backendGate.stepResults.filter((s) => s.conditional);
  if (conditionalSteps.length === 0) return null;

  // For now, return the first conditional step's note as the nearest miss
  // In the future, this could be more sophisticated (e.g., R:R closest to 2.5)
  const step = conditionalSteps[0];
  return `Nearest miss: ${step.name} — ${step.note}`;
}

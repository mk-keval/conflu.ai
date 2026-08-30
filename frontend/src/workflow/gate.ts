/**
 * Validation Gate domain logic (Phase 1 — Sprint 3, gap #4).
 *
 * A 5-step guided check that teaches the working-professional beginner the
 * questions behind a trade, answered automatically from the ticker's live
 * verdict + trade-plan data. Pure functions so the gate rules are unit-testable
 * without a DOM (mirrors `routine.ts` / `adherence.ts`).
 *
 * The gate is intentionally "teach-first": each step surfaces a plain-English
 * question, the app's auto-answer, and (in the component) a "why this matters"
 * note. The result is persisted via `workflowStore.recordGate`.
 *
 * Data availability is honest — when a signal is missing we return a
 * CONDITIONAL (not a false pass), so a beginner is never misled into thinking a
 * step "passed" when we couldn't actually verify it.
 */

import type { GateStepName, GateStepResult, GateVerdict } from '../types/workflow';

/** Plain-English question for each gate step, in order. */
export const GATE_STEPS: readonly {
  name: GateStepName;
  question: string;
}[] = [
  { name: 'Liquidity', question: 'Is there enough trading volume to get in and out easily?' },
  { name: 'Structure', question: 'Is the higher-timeframe trend lining up with the setup?' },
  { name: 'Risk/Reward', question: 'Is the potential reward at least 2.5× the risk I am taking?' },
  { name: 'Edge Check', question: 'Do conviction and near-term catalysts support the trade?' },
  { name: 'Conviction', question: 'How confident am I overall, on a 0–10 scale?' },
];

/** Practical floor for "liquid enough to swing" — average daily $ volume. */
export const LIQUIDITY_MIN_AVG_DAILY_USD = 10_000_000;

/** Minimum reward:risk for a PASS (elite swing floor). */
export const RISK_REWARD_PASS = 2.5;

/** Reward:risk between this and the PASS floor is CONDITIONAL. */
export const RISK_REWARD_CONDITIONAL = 2.0;

/** Conviction >= this, with a non-negative catalyst, earns a strong Edge. */
export const CONVICTION_HIGH = 7;

/** Conviction below this is a weak edge. */
export const CONVICTION_LOW = 4;

/**
 * Inputs for the gate, drawn from the ticker page's live verdict + trade plan.
 * Every field is optional because a given setup may not expose all of them —
 * missing fields yield a CONDITIONAL (see module doc).
 */
export interface GateInput {
  symbol: string;
  /** Average daily dollar volume (ADV), if known. */
  avgDailyVolumeUsd?: number | null;
  /** Volume ratio (1.0 = average) as a secondary liquidity confirmation. */
  volumeRatio?: number | null;
  /** Trend label per timeframe ("bullish" | "bearish" | "mixed" | ...). Null if unknown. */
  dailyTrend?: string | null;
  weeklyTrend?: string | null;
  /** A structural key level near the setup (usually the entry/stop anchor). */
  keyLevel?: number | null;
  /** Current price, to judge the setup against levels. */
  price?: number | null;
  entryLow?: number | null;
  entryHigh?: number | null;
  stopLoss?: number | null;
  targets?: number[] | null;
  /** Backend-computed R:R (preferred when present). */
  riskReward?: number | null;
  /** 0-10 conviction from the verdict. */
  conviction?: number | null;
  /** Catalyst bias ("bullish" | "bearish" | "neutral" | ...). */
  catalystBias?: string | null;
}

// ── Step evaluators ──

export function evaluateLiquidity(input: GateInput): GateStepResult {
  const { avgDailyVolumeUsd, volumeRatio } = input;
  if (avgDailyVolumeUsd == null && volumeRatio == null) {
    return {
      name: 'Liquidity',
      passed: false,
      conditional: true,
      note: 'Liquidity data is not available for this setup right now — confirm volume is healthy before entering.',
    };
  }
  if (avgDailyVolumeUsd != null) {
    if (avgDailyVolumeUsd >= LIQUIDITY_MIN_AVG_DAILY_USD) {
      return {
        name: 'Liquidity',
        passed: true,
        note: `Average daily volume ≈ $${(avgDailyVolumeUsd / 1_000_000).toFixed(0)}M — well above the $10M swing liquidity floor.`,
      };
    }
    if (avgDailyVolumeUsd >= LIQUIDITY_MIN_AVG_DAILY_USD / 2) {
      return {
        name: 'Liquidity',
        passed: false,
        conditional: true,
        note: `Average daily volume ≈ $${(avgDailyVolumeUsd / 1_000_000).toFixed(0)}M — below the $10M floor; trade only with a tight, small position.`,
      };
    }
    return {
      name: 'Liquidity',
      passed: false,
      note: `Average daily volume ≈ $${(avgDailyVolumeUsd / 1_000_000).toFixed(0)}M — too thin to enter and exit cleanly.`,
    };
  }
  // Only volumeRatio available (a confirmation signal, not a level).
  if ((volumeRatio ?? 0) >= 1.2) {
    return {
      name: 'Liquidity',
      passed: true,
      conditional: true,
      note: `Volume is running at ${(volumeRatio ?? 0).toFixed(1)}× average — active participation. Confirm average daily $ volume is adequate before entering.`,
    };
  }
  return {
    name: 'Liquidity',
    passed: false,
    conditional: true,
    note: 'Volume looks quiet relative to average — execute with care and confirm participation. ',
  };
}

/**
 * Structure: do the weekly (higher-TF) and daily (entry-TF) trends agree, and
 * is there a key level to anchor the invalidation?
 */
export function evaluateStructure(input: GateInput): GateStepResult {
  const { dailyTrend, weeklyTrend, keyLevel, price, entryLow, stopLoss } = input;
  const weeklyBias = weeklyTrend == null ? null : weeklyTrend.toLowerCase();
  const dailyBias = dailyTrend == null ? null : dailyTrend.toLowerCase();

  const bull = (b: string | null) => b === 'bullish' || b === 'bull' || b === 'strong_bullish';
  const bear = (b: string | null) => b === 'bearish' || b === 'bear' || b === 'strong_bearish';
  const alignedBull = bull(weeklyBias) && bull(dailyBias);
  const alignedBear = bear(weeklyBias) && bear(dailyBias);

  const hasKeyLevel = keyLevel != null || (entryLow != null && stopLoss != null) || price != null;

  if (weeklyBias == null || dailyBias == null) {
    return {
      name: 'Structure',
      passed: false,
      conditional: true,
      note: 'We could not confirm both timeframes\u2019 trends — multi-timeframe structure is a core part of the checklist, so confirm trend alignment yourself.',
    };
  }
  if (alignedBull || alignedBear) {
    return {
      name: 'Structure',
      passed: true,
      note: hasKeyLevel
        ? `Weekly and daily ${weeklyBias} trends are aligned, and a clear level anchors your invalidation.`
        : `Weekly and daily ${weeklyBias} trends are aligned — a clean trend-following setup.`,
    };
  }
  if (bull(dailyBias) && bear(weeklyBias)) {
    return {
      name: 'Structure',
      passed: false,
      conditional: true,
      note: 'The daily setup is bullish but the weekly trend is down — this is a counter-trend trade. Only consider it small and tight.',
    };
  }
  return {
    name: 'Structure',
    passed: false,
    conditional: true,
    note: 'Trends are mixed across timeframes — the higher timeframe does not clearly support the setup. Reduce size or wait for alignment.',
  };
}

/**
 * Risk/Reward from entry/stop/targets. Prefers the backend-computed `riskReward`
 * when present; otherwise derives it from the raw levels.
 */
export function evaluateRiskReward(input: GateInput): GateStepResult {
  let rr = input.riskReward;
  if (rr == null && input.entryLow != null && input.entryHigh != null && input.stopLoss != null && input.targets && input.targets.length > 0) {
    const entry = (input.entryLow + input.entryHigh) / 2;
    const risk = Math.abs(entry - input.stopLoss);
    const reward = Math.abs((input.targets[0] ?? 0) - entry);
    if (risk > 0) rr = reward / risk;
  }
  if (rr == null) {
    return {
      name: 'Risk/Reward',
      passed: false,
      conditional: true,
      note: 'We could not compute a reward:risk here — use the stop and first target from the trade plan to check it is at least 2.5:1.',
    };
  }
  if (rr >= RISK_REWARD_PASS) {
    return { name: 'Risk/Reward', passed: true, note: `Reward:risk is ${rr.toFixed(1)}:1 — above the 2.5:1 elite floor.` };
  }
  if (rr >= RISK_REWARD_CONDITIONAL) {
    return {
      name: 'Risk/Reward',
      passed: false,
      conditional: true,
      note: `Reward:risk is ${rr.toFixed(1)}:1 — below the 2.5:1 elite floor but still positive; trade it smaller.`,
    };
  }
  return {
    name: 'Risk/Reward',
    passed: false,
    note: `Reward:risk is only ${rr.toFixed(1)}:1 — the potential reward does not justify the risk. Skip or wait for a better entry.`,
  };
}

/**
 * Edge = conviction + near-term catalyst. A strong conviction with a
 * non-negative catalyst passes; a cautionary catalyst or weak conviction is a
 * conditional / fail.
 */
export function evaluateEdge(input: GateInput): GateStepResult {
  const conviction = input.conviction ?? 0;
  const cat = input.catalystBias == null ? null : input.catalystBias.toLowerCase();
  const catalystVaried = cat == null;
  const catalystAgainst = cat != null && (cat === 'bearish' || cat === 'cautious' || cat === 'slightly_negative' || cat === 'negative');

  if (conviction >= CONVICTION_HIGH && !catalystAgainst) {
    return {
      name: 'Edge Check',
      passed: true,
      conditional: catalystVaried,
      note: catalystVaried
        ? `Conviction is ${conviction}/10 — a strong edge. No explicit catalyst signal detected; confirm the reason this setup is special.`
        : `Conviction is ${conviction}/10 and the near-term catalyst ${cat} supports the trade.`,
    };
  }
  if (conviction >= CONVICTION_LOW && conviction < CONVICTION_HIGH) {
    return {
      name: 'Edge Check',
      passed: false,
      conditional: true,
      note: `Conviction is ${conviction}/10 — a moderate edge. Size the trade smaller until conviction builds.`,
    };
  }
  return {
    name: 'Edge Check',
    passed: false,
    note: catalystAgainst
      ? `Conviction is ${conviction}/10 with a ${cat} catalyst — there is no edge here; skip this setup.`
      : `Conviction is only ${conviction}/10 — too weak to justify a position right now.`,
  };
}

/**
 * Roll up the four evaluated steps + the (user-confirmed, or auto-seeded)
 * conviction score into an overall verdict.
 *
 * - Any hard fail (passed=false, not conditional) → FAIL
 * - Else any conditional → CONDITIONAL
 * - Else → PASS
 */
export function computeGate(stepResults: GateStepResult[]): { overall: GateVerdict } {
  const hasHardFail = stepResults.some((s) => !s.passed && !s.conditional);
  if (hasHardFail) return { overall: 'FAIL' };
  const hasConditional = stepResults.some((s) => s.conditional);
  if (hasConditional) return { overall: 'CONDITIONAL' };
  return { overall: 'PASS' };
}

/**
 * Convenience: evaluate all four data-driven steps and add the conviction step,
 * returning the full ordered result list. The conviction step is seeded from
 * `input.conviction`, and passes if the user (or the seed) scores ≥ the high
 * bar; otherwise it acts as a conditional.
 */
export function buildGateResults(
  input: GateInput,
  convictionScore: number
): GateStepResult[] {
  const steps: GateStepResult[] = [
    evaluateLiquidity(input),
    evaluateStructure(input),
    evaluateRiskReward(input),
    evaluateEdge(input),
  ];
  const conviction = Math.max(0, Math.min(10, Math.round(convictionScore)));
  const convictionResult: GateStepResult =
    conviction >= CONVICTION_HIGH
      ? { name: 'Conviction', passed: true, note: `Conviction ${conviction}/10 — a strong, tradeable signal.` }
      : conviction >= CONVICTION_LOW
        ? { name: 'Conviction', passed: false, conditional: true, note: `Conviction ${conviction}/10 — moderate; only take this small.` }
        : { name: 'Conviction', passed: false, note: `Conviction ${conviction}/10 — below the bar; skip this setup.` };
  return [...steps, convictionResult];
}

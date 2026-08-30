/**
 * Execution Engine pure logic (Phase 1, Sprint 4 — gap #4, in-flow guided learning).
 *
 * Turns a validated `ExecutionSetup` into a broker-ready tranche plan:
 *   - Splits the backend-computed total share count into a 40/30/30 ladder.
 *   - Maps the 0-10 gate conviction onto the API's `high|medium|low` level
 *     (Momus Major #5: `/professional/position-size` expects the string enum).
 *   - Assigns trigger + limit prices per tranche (preferring the trade plan's
 *     scale-in levels) and a structure-based stop.
 *   - Builds the copyable OCO bracket JSON for the user's broker.
 *
 * Kept pure (no React, no network) so it is unit-testable in isolation — the
 * component `ExecutionEngine.tsx` only wires this to the position-size API and
 * renders the result.
 */

import type {
  ExecutionSetup,
  OcoBracket,
  ScaleOutTarget,
  TrancheAllocation,
} from '../types/workflow';

/** Standard elite tranche ladder (40 / 30 / 30). */
export const TRANCHES = [0.4, 0.3, 0.3] as const;

/**
 * Map a 0-10 gate conviction onto the API's string enum (Momus Major #5).
 * Score >= 8 → "high", >= 5 → "medium", else "low". Mirrors the gate's own
 * thresholds (CONVICTION_HIGH=7 / CONVICTION_LOW=4) but tilted slightly so only
 * strong conviction gets full size.
 */
export function convictionToLevel(score: number): 'high' | 'medium' | 'low' {
  if (score >= 8) return 'high';
  if (score >= 5) return 'medium';
  return 'low';
}

/**
 * Distribute a whole-share count across the 40/30/30 tranches, flooring each
 * tranche's qty and giving any remaining shares to the first tranche so the
 * tranche qty always sums exactly to the total.
 */
export function splitShares(totalShares: number): number[] {
  if (!Number.isFinite(totalShares) || totalShares <= 0) return [0, 0, 0];
  const base = Math.floor(totalShares);
  const first = Math.floor(base * TRANCHES[0]);
  const second = Math.floor(base * TRANCHES[1]);
  const third = base - first - second;
  return [first, second, third];
}

/**
 * Compute the absolute price for an r-multiple target: a move of `r` × the
 * per-share risk added to the reference price (long side default).
 */
export function targetPriceAtRMul(
  entryMid: number,
  stopLoss: number,
  rMultiple: number
): number {
  const riskPerShare = Math.abs(entryMid - stopLoss);
  if (!Number.isFinite(riskPerShare) || riskPerShare === 0) return entryMid;
  const direction = entryMid >= stopLoss ? 1 : -1;
  return entryMid + direction * rMultiple * riskPerShare;
}

/** Build the scale-out target list from raw targets + the plan's r-multiples. */
export function scaleOutTargets(
  setup: ExecutionSetup
): ScaleOutTarget[] {
  const { targets, scaleOut, entryMid, stopLoss } = setup;
  if (scaleOut && scaleOut.length > 0) {
    return scaleOut
      .map((s, i) => ({
        rMultiple: s.r_multiple,
        sizePct: s.size_pct,
        targetPrice: targets[i] ?? targetPriceAtRMul(entryMid, stopLoss, s.r_multiple),
      }))
      .filter((t) => t.rMultiple > 0);
  }
  // No explicit scale-out plan — one full-exit at the nearest target above entry.
  const best = targets
    .filter((t) => Number.isFinite(t) && t > entryMid)
    .sort((a, b) => a - b)[0];
  return [
    {
      rMultiple: 1,
      sizePct: 100,
      targetPrice: best ?? entryMid,
    },
  ];
}

/**
 * build the full tranche ladder from the backend share count + setup.
 * Trigger/limit prices prefer the plan's scale-in levels; stop is the setup's
 * structure stop for the first tranche and moved to breakeven for later ones
 * (a simple, teachable default).
 */
export function buildTranches(
  totalShares: number,
  setup: ExecutionSetup
): TrancheAllocation[] {
  const qty = splitShares(totalShares);
  const triggers = setup.triggerPrices && setup.triggerPrices.length >= 3
    ? setup.triggerPrices
    : [setup.entryMid, setup.entryMid, setup.entryHigh];
  return qty.map((n, i) => ({
    seq: (i + 1) as 1 | 2 | 3,
    weight: TRANCHES[i],
    qty: n,
    triggerPrice: triggers[i] ?? setup.entryMid,
    limitPrice: triggers[i] ?? setup.entryMid,
    // First tranche sits at the structure stop; later pieces tighten to break-even.
    stopPrice: i === 0 ? setup.stopLoss : setup.entryMid,
  }));
}

/** Build the broker-ready OCO bracket object for copy/export. */
export function buildOcoBracket(totalShares: number, setup: ExecutionSetup): OcoBracket {
  const tranches = buildTranches(totalShares, setup);
  const targets = scaleOutTargets(setup);
  return {
    symbol: setup.symbol,
    tranches: tranches.map((t) => ({
      qty: t.qty,
      limit_price: t.limitPrice,
      stop_price: t.stopPrice,
    })),
    stop_loss: setup.stopLoss,
    targets,
    time_stop_days: setup.timeStopDays,
  };
}

/** Convenience: everything the Execution Engine tab needs from a setup. */
export interface ExecutionPlan {
  tranches: TrancheAllocation[];
  targets: ScaleOutTarget[];
  oco: OcoBracket;
  totalShares: number;
  convictionLevel: 'high' | 'medium' | 'low';
  timeStopDays: number;
}

export function buildExecutionPlan(totalShares: number, setup: ExecutionSetup): ExecutionPlan {
  return {
    tranches: buildTranches(totalShares, setup),
    targets: scaleOutTargets(setup),
    oco: buildOcoBracket(totalShares, setup),
    totalShares,
    convictionLevel: convictionToLevel(setup.conviction),
    timeStopDays: setup.timeStopDays,
  };
}

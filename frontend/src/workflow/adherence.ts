/**
 * Adherence math for the guided-workflow (Phase 1, gap #4).
 *
 * Pure, browser-free functions so they are unit-testable in isolation and so a
 * future backend/hydrated store can reuse the same rolling-window logic without
 * importing Zustand or touching localStorage (see D-A v2.1).
 *
 * A trade's adherence is `stepsFollowed / stepsTotal`, where the denominator is
 * capped by the 13-step plan-steps taxonomy (see `types/workflow.ts`).
 */

import { ADHERENCE_MAX_STEPS, type PaperTrade } from '../types/workflow';

/** Default rolling window for the 20-trade adherence metric. */
export const DEFAULT_ROLLING_WINDOW = 20;

/** Benchmark used to count an "adherent" trade for streak purposes. */
export const ADHERENT_THRESHOLD = 80;

export interface AdherencePoint {
  adherencePct: number;
  stepsFollowed: number;
  stepsTotal: number;
  closedAt: string;
  symbol: string;
}

export interface RollingAdherence {
  /** Average adherence over the window (0 if no trades). */
  pct: number;
  /** Number of trades included in the window. */
  count: number;
  /** Whether enough trades exist to be statistically meaningful (== window). */
  full: boolean;
}

/**
 * Compute rounded adherence % from raw step counts, clamped to [0, 100].
 *
 * @param stepsFollowed numerator (0..stepsTotal)
 * @param stepsTotal    denominator, clamped to at most ADHERENCE_MAX_STEPS
 */
export function adherencePct(
  stepsFollowed: number,
  stepsTotal: number
): number {
  const total = Math.max(
    1,
    Math.min(ADHERENCE_MAX_STEPS, Math.round(stepsTotal))
  );
  const followed = Math.max(0, Math.min(total, Math.round(stepsFollowed)));
  const pct = (followed / total) * 100;
  return Math.round(pct * 100) / 100;
}

/** Build an adherence point from a paper trade (pure helper). */
export function toAdherencePoint(trade: PaperTrade): AdherencePoint {
  return {
    adherencePct: trade.adherencePct,
    stepsFollowed: trade.stepsFollowed,
    stepsTotal: trade.stepsTotal,
    closedAt: trade.closedAt ?? trade.openedAt,
    symbol: trade.symbol,
  };
}

/** Closed trades sorted oldest → newest (stable, pure). */
function closedTradesChronological(trades: PaperTrade[]): PaperTrade[] {
  return trades
    .filter((t) => t.status === 'closed' && t.closedAt != null)
    .slice()
    .sort((a, b) =>
      a.closedAt! < b.closedAt! ? -1 : a.closedAt! > b.closedAt! ? 1 : 0
    );
}

/**
 * Rolling average adherence over the most recent `window` closed trades
 * (default 20 — the "20-trade adherence" metric).
 */
export function rollingAdherence(
  trades: PaperTrade[],
  window: number = DEFAULT_ROLLING_WINDOW
): RollingAdherence {
  const closed = closedTradesChronological(trades);
  const slice = closed.slice(-Math.max(1, window));
  if (slice.length === 0) {
    return { pct: 0, count: 0, full: false };
  }
  const sum = slice.reduce((acc, t) => acc + t.adherencePct, 0);
  return {
    pct: Math.round((sum / slice.length) * 100) / 100,
    count: slice.length,
    full: slice.length >= Math.max(1, window),
  };
}

/**
 * Number of consecutive most-recent closed trades that met the adherence
 * benchmark (>= ADHERENT_THRESHOLD). A complement to the rolling average that
 * rewards consistency, which is the point of the workflow for a beginner.
 */
export function adherenceStreak(trades: PaperTrade[]): number {
  const closed = closedTradesChronological(trades);
  let streak = 0;
  for (let i = closed.length - 1; i >= 0; i--) {
    if (closed[i].adherencePct >= ADHERENT_THRESHOLD) {
      streak += 1;
    } else {
      break;
    }
  }
  return streak;
}

/**
 * Convenience selector-style accessor: given an array of paper trades, return
 * both the rolling metric and the streak. Used by the AdherenceDashboard and
 * the store's derived selectors.
 */
export function selectAdherence(
  trades: PaperTrade[],
  window: number = DEFAULT_ROLLING_WINDOW
): { rolling: RollingAdherence; streak: number } {
  return {
    rolling: rollingAdherence(trades, window),
    streak: adherenceStreak(trades),
  };
}

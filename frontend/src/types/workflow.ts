/**
 * Guided-workflow domain types (Phase 1 — gap #4, in-flow learning).
 *
 * These model the four workflow surfaces in a single implicit user's session:
 *   - Daily Routine (4 sequential steps, user-paced)
 *   - Validation Gate (5-step setup check)
 *   - Paper Trade + adherence (13-step plan-steps taxonomy)
 *
 * The corresponding state lives in a thin, abstracted Zustand store persisted to
 * localStorage (`frontend/src/store/workflowStore.ts`). Keeping these as plain
 * types decouples the UI (Sprints 2-8) from the storage backend, so a server
 * store can be introduced later without touching components (see D-A v2.1).
 */

// ── Daily Routine (Slice 3: 2 touchpoints) ──

export type RoutineStepSeq = 1 | 2;

export type RoutineStepLabel =
  | 'Pre-Market (Touchpoint A)'
  | 'After-Close (Touchpoint B)';

export type RoutineStepStatus = 'pending' | 'completed';

export interface RoutineStep {
  seq: RoutineStepSeq;
  step: RoutineStepLabel;
  status: RoutineStepStatus;
  /** ISO timestamp when the user completed this step, or null if pending. */
  completedAt: string | null;
  /** Optional per-step payload (journal answers, order list, etc.). */
  data?: Record<string, unknown>;
}

export type RoutineStatus = 'in_progress' | 'completed';

export interface DailyRoutine {
  /** Local date key, e.g. "2026-08-28". */
  date: string;
  /** 0-based index of the next step the user must complete (0..3). */
  currentStep: number;
  status: RoutineStatus;
  steps: RoutineStep[];
  /** ISO timestamp of the most recent step completion. */
  updatedAt: string;
}

// ── Validation Gate ──

export type GateVerdict = 'PASS' | 'FAIL' | 'CONDITIONAL';

export type GateStepName =
  | 'Liquidity'
  | 'Structure'
  | 'Positioning'
  | 'Catalyst'
  | 'Risk/Reward'
  | 'Portfolio Fit'
  | 'Conviction';

export interface GateStepResult {
  name: GateStepName;
  passed: boolean;
  conditional?: boolean;
  note?: string;
}

export interface ValidationGate {
  id: string;
  symbol: string;
  stepResults: GateStepResult[];
  overall: GateVerdict;
  /** 0-10 conviction score produced by the final step. */
  convictionScore: number;
  /** Steps where data was missing (CONDITIONAL due to missing inputs). */
  dataGaps: string[];
  /** ISO timestamp when the gate was evaluated. */
  evaluatedAt: string;
  createdAt: string;
}

// ── Paper Trade + Adherence ──

export type PaperTradeStatus = 'open' | 'closed';

export type PaperTradeOutcome =
  | 'target_hit'
  | 'stop_hit'
  | 'time_stop'
  | 'open'
  | 'flat';

export interface PaperTrade {
  id: string;
  symbol: string;
  plan: Record<string, unknown>;
  fills: Record<string, unknown>;
  status: PaperTradeStatus;
  outcome: PaperTradeOutcome;
  /** Adherence numerator: plan steps this trade adhered to (see taxonomy). */
  stepsFollowed: number;
  /** Adherence denominator: plan steps applicable to this trade (max 13). */
  stepsTotal: number;
  /** stepsFollowed / stepsTotal * 100, clamped to [0, 100]. */
  adherencePct: number;
  /** Realized R-multiple for closed trades (from exit inference). */
  realizedR?: number;
  /** Entry price (for open position tracking). */
  entryPrice?: number;
  /** Stop loss price (for open position tracking). */
  stopLoss?: number;
  /** Gate verdict at entry (PASS/CONDITIONAL/FAIL). */
  gateVerdict?: 'PASS' | 'FAIL' | 'CONDITIONAL';
  /** Plan adherence score (0-1) for closed trades (from sync-exits). */
  planAdherence?: number;
  /** True for pre-instrumentation rows that must not enter the forward scorecard. */
  excludeFromStats?: boolean;
  openedAt: string;
  closedAt: string | null;
}

/**
 * Plan-steps taxonomy (Momus Major #6). Each paper trade can be scored against
 * up to 13 discrete plan steps, so the 20-trade adherence metric is meaningful
 * to a beginner. Kept as a shared constant (here, rather than in the store) so
 * the adherence module is testable in isolation.
 */
export const PAPER_TRADE_PLAN_STEPS = {
  validation_gate: 5,
  entry_tranches: 3,
  stop_respected: 1,
  target_hits: 3,
  time_stop_honored: 1,
} as const;

export const ADHERENCE_MAX_STEPS: number =
  PAPER_TRADE_PLAN_STEPS.validation_gate +
  PAPER_TRADE_PLAN_STEPS.entry_tranches +
  PAPER_TRADE_PLAN_STEPS.stop_respected +
  PAPER_TRADE_PLAN_STEPS.target_hits +
  PAPER_TRADE_PLAN_STEPS.time_stop_honored;

// ── Execution Engine ──

/**
 * Raw inputs the Execution Engine needs to size + bracket a trade. Pre-filled
 * from the ticker's verdict + trade-plan, then user-editable (account equity in
 * particular). Consumers derive this from `AnalysisVerdict` + `TradePlan` on the
 * ticker page; the pure module `workflow/execution.ts` turns it into tranches.
 */
export interface ExecutionSetup {
  symbol: string;
  /** 0-10 gate conviction — mapped to the API's high/medium/low level. */
  conviction: number;
  /** User account equity in USD (editable). */
  accountEquity: number;
  entryLow: number;
  entryHigh: number;
  /** Midpoint of the entry zone — the reference trigger when scale-in is absent. */
  entryMid: number;
  stopLoss: number;
  /** Absolute price targets (from the verdict). */
  targets: number[];
  /** Scale-out r-multiples from the trade plan (`scale_out`). */
  scaleOut: Array<{ r_multiple: number; size_pct: number; reason?: string }>;
  /** Cap on holding time in calendar days (from trade-plan `max_hold_days`). */
  timeStopDays: number;
  /** Entry trigger prices in order (from trade-plan `scale_in`, length ≤ 3). */
  triggerPrices: number[];
}

/** One 40/30/30 tranche with broker prices. */
export interface TrancheAllocation {
  /** 1-based tranche ordinal. */
  seq: 1 | 2 | 3;
  /** Fraction of the full position this tranche takes (0.4/0.3/0.3). */
  weight: number;
  /** Whole shares in this tranche. */
  qty: number;
  /** Trigger price — where this piece gets filled. */
  triggerPrice: number;
  /** Broker limit price (fill-or-skip). */
  limitPrice: number;
  /** Protective stop for this tranche. */
  stopPrice: number;
}

export interface ScaleOutTarget {
  rMultiple: number;
  /** % of position sold at this target. */
  sizePct: number;
  /** Absolute price at this r-multiple. */
  targetPrice: number;
}

/**
 * Broker-ready one-cancels-other bracket. Copyable JSON for the user's broker
 * (Sprint 4 demo output). Tranches include their per-piece qty + limit/stop.
 */
export interface OcoBracket {
  symbol: string;
  tranches: Array<{
    qty: number;
    limit_price: number;
    stop_price: number;
  }>;
  stop_loss: number;
  targets: ScaleOutTarget[];
  time_stop_days: number;
}

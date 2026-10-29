import { apiGet, apiPost } from './client';

// ── Types ──

export interface SymbolAllocation {
  symbol: string;
  sector?: string | null;
  price?: number | null;
  beta?: number | null;
  conviction: number;
  action: string;
  suggested_pct?: number | null;
}

export interface CorrelationPair {
  a: string;
  b: string;
  r: number;
}

export interface PortfolioResponse {
  symbols: string[];
  symbol_count: number;
  analyses: SymbolAllocation[];
  sector_allocation: Record<string, number>;
  combined_beta: number | null;
  portfolio_volatility: number | null;
  equal_risk_pct: number | null;
  correlation_matrix: CorrelationPair[];
  high_correlation_pairs: CorrelationPair[];
  max_single_position_pct: number;
  timestamp: string;
}

// ── Journal (D-68): the SQLite journal of record, surfaced to the UI ──

/**
 * One journal row as returned by `/workflow/journal*`. The backend serializes
 * store cells as strings (CSV parity), so numeric fields arrive as strings —
 * parse at the edge before display/math.
 */
export interface JournalRow {
  // entry side
  date_entered: string | null;
  symbol: string | null;
  sector: string | null;
  action: string | null;
  entry_type: string | null;
  entry_price: string | null;
  stop_loss: string | null;
  target_1: string | null;
  target_2: string | null;
  position_size_pct: string | null;
  account_value: string | null;
  shares: string | null;
  confluence_count: string | null;
  signal_at_entry: string | null;
  gate_verdict: string | null;
  gate_failed_step: string | null;
  entry_low: string | null;
  entry_high: string | null;
  risk_reward_planned: string | null;
  gate_version: string | null;
  notes: string | null;
  // exit side
  date_closed: string | null;
  exit_price: string | null;
  exit_reason: string | null;
  realized_r: string | null;
  pnl_usd: string | null;
  mfe_r: string | null;
  mae_r: string | null;
  plan_adherence: string | null;
  // extras
  template: string | null;
  regime: string | null;
  entry_timing: string | null;
  max_hold_days?: string | null;
  /** '1' for the 3 pre-instrumentation rows excluded from the forward scorecard. */
  exclude_from_stats?: string | number | boolean | null;
  /** '1' when the recorded fill never traded (phantom fill) — visible, not a position. */
  voided?: string | number | boolean | null;
  void_reason?: string | null;
  /** Forward-sample version (D-76): 'v0.1' reference, 'interim' loop data, 'v0.2' scored. */
  sample_version?: string | null;
}

/** An after-close order waiting for (or resolved by) a T+1 fill. */
export interface PendingOrder {
  id: number;
  signal_date: string;
  symbol: string;
  sector: string | null;
  action: string | null;
  order_type: 'limit' | 'moo' | string;
  limit_price: number | null;
  entry_low: number | null;
  entry_high: number | null;
  stop_loss: number | null;
  target_1: number | null;
  target_2: number | null;
  position_size_pct: number | null;
  account_value: number | null;
  shares: number | null;
  gate_verdict: string | null;
  template: string | null;
  regime: string | null;
  notes: string | null;
  status: 'pending' | 'filled' | 'expired' | 'cancelled' | string;
  status_date: string | null;
  status_reason: string | null;
  expires_after_sessions: number | null;
  /** Forward-sample version inherited by the journal row when this order fills (D-76). */
  sample_version?: string | null;
  created_at: string | null;
}

export interface WorkflowRun {
  id: number;
  run_date: string;
  ran_at: string;
  mode: string;
  apply: boolean;
  accepted: number | null;
  rejected: number | null;
  updated: number | null;
  skipped: number | null;
  status: string;
  message: string | null;
  details: Record<string, unknown> | null;
}

export interface JournalRejection {
  id: number;
  date_seen: string;
  symbol: string;
  sector: string | null;
  action: string | null;
  conviction: number | null;
  failed_step: string | null;
  gate_verdict: string | null;
  reason: string | null;
  notes: string | null;
  template?: string | null;
  regime?: string | null;
  created_at: string;
}

export interface EnforceResultItem {
  symbol: string;
  gate_verdict?: string;
  entry_price?: number | null;
  stop_loss?: number | null;
  position_size_pct?: number | null;
  target_1?: number | null;
  target_2?: number | null;
  rejected?: boolean;
  failed_step?: string | null;
  reason?: string | null;
  order_type?: 'limit' | 'moo' | string | null;
  limit_price?: number | null;
  order_status?: string | null;
  expires_after_sessions?: number | null;
}

/** An order that filled from an actual next-session bar (D-73). */
export interface PendingFillResult {
  symbol: string;
  order_id: number;
  fill_date: string | null;
  fill_price: number | null;
  same_day_stop: boolean;
  note: string | null;
}

/** An order that closed without a fill. */
export interface ClosedOrderResult {
  symbol: string;
  order_id: number;
  status: string;
  note: string | null;
}

export interface SyncExitsResultItem {
  symbol: string;
  exit_date?: string | null;
  exit_price?: number | null;
  exit_reason?: string | null;
  realized_r?: number | null;
  pnl_usd?: number | null;
  mfe_r?: number | null;
  mae_r?: number | null;
  plan_adherence?: number | null;
  applied?: boolean;
  skipped?: boolean;
  skip_reason?: string | null;
}

export interface RunCloseResult {
  run_id: number;
  enforce: {
    accepted: EnforceResultItem[];
    rejected: EnforceResultItem[];
    message: string;
    pending?: PendingOrder[];
    fills?: PendingFillResult[];
    closed_orders?: ClosedOrderResult[];
  };
  exits: {
    updated: number;
    skipped: number;
    items: SyncExitsResultItem[];
    message: string;
  };
  message: string;
}

// ── Replay ledger (D-71): simulated screen replay, separate from the journal ──

export interface ReplayTrade {
  id: number;
  run_id: number;
  signal_date: string | null;
  date_entered: string;
  symbol: string;
  template: string | null;
  regime: string | null;
  regime_key: string | null;
  screen_rank: number | null;
  screen_weight: number | null;
  direction: string | null;
  entry_price: number | null;
  stop_loss: number | null;
  target_1: number | null;
  exit_date: string | null;
  exit_price: number | null;
  exit_reason: string | null;
  realized_r: number | null;
  pnl_usd: number | null;
  risk_pct: number | null;
  position_size_pct: number | null;
  shares: number | null;
  account_value: number | null;
  hold_bars: number | null;
  rvol: number | null;
  also_signaled_by: string | null;
  notes: string | null;
}

export interface ReplayStats {
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  expectancy_r: number;
  avg_win_r: number;
  avg_loss_r: number;
  profit_factor_r: number | null;
  pnl_usd: number;
  avg_hold_bars: number;
}

export interface ReplayRun {
  id: number;
  generated_at: string;
  window_start: string;
  window_end: string;
  universe_count: number;
  templates_count: number;
  params: Record<string, number>;
  summary: ReplayStats & {
    templates?: Record<string, ReplayStats>;
    regimes?: Record<string, ReplayStats>;
    exit_reasons?: Record<string, number>;
    total_r?: number;
  };
  metadata: {
    counts?: {
      raw_signals?: number;
      after_regime_gate?: number;
      after_dedupe?: number;
      rows?: number;
    };
    regime_days?: Record<string, number>;
    templates?: string[];
    caveats?: string[];
    [key: string]: unknown;
  };
}

/** Latest replay payload; `run` is null until run_paper_replay.py has run. */
export async function getReplayJournal(): Promise<{
  run: ReplayRun | null;
  rows: ReplayTrade[];
  summary: ReplayStats | null;
}> {
  return apiGet<{ run: ReplayRun | null; rows: ReplayTrade[]; summary: ReplayStats | null }>(
    '/api/v1/workflow/replay'
  );
}

// ── API calls ──

export async function analyzePortfolio(
  symbols: string[]
): Promise<PortfolioResponse> {
  return apiPost<PortfolioResponse>('/api/v1/portfolio/analyze', { symbols });
}

/** All journal rows (open + closed), most recent first. */
export async function getJournalAll(): Promise<{
  rows: JournalRow[];
  count: number;
}> {
  return apiGet<{ rows: JournalRow[]; count: number }>('/api/v1/workflow/journal');
}

/** Recent workflow runs (UI runs strip). */
export async function getRuns(
  limit = 14
): Promise<{ items: WorkflowRun[]; count: number }> {
  return apiGet<{ items: WorkflowRun[]; count: number }>(
    `/api/v1/workflow/runs?limit=${limit}`
  );
}

/** After-close orders waiting for a T+1 fill (or their history). */
export async function getPendingOrders(
  limit = 50,
  status: 'pending' | 'filled' | 'expired' | 'cancelled' | 'all' = 'pending'
): Promise<{ items: PendingOrder[]; count: number }> {
  return apiGet<{ items: PendingOrder[]; count: number }>(
    `/api/v1/workflow/pending-orders?status=${status}&limit=${limit}`
  );
}

/** Recent rejection log rows (why candidates did not become trades). */
export async function getRejections(
  limit = 200
): Promise<{ items: JournalRejection[]; count: number }> {
  return apiGet<{ items: JournalRejection[]; count: number }>(
    `/api/v1/workflow/journal/rejections?limit=${limit}`
  );
}

/**
 * One-go after-close run: Touchpoint A (enforce entries) then Touchpoint B
 * (sync exits, applied) in a single call. Per-call timeout 300s: gate
 * enforcement fetches the brief + per-ticker analysis for the whole candidate
 * list (R12 — can legitimately run minutes).
 */
export async function runClose(
  body: { min_conviction?: number; only?: string; apply_exits?: boolean } = {}
): Promise<RunCloseResult> {
  return apiPost<RunCloseResult>(
    '/api/v1/workflow/paper-trades/run-close',
    { min_conviction: 5, ...body },
    { timeout: 300_000 }
  );
}

/** Direct download URL for the canonical journal CSV export. */
export const JOURNAL_EXPORT_URL = '/api/v1/workflow/journal/export';

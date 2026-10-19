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
  };
  exits: {
    updated: number;
    skipped: number;
    items: SyncExitsResultItem[];
    message: string;
  };
  message: string;
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

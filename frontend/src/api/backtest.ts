import { apiGet, apiPost } from './client';
import type {
  BacktestRequest,
  BacktestResultData,
  CompareRequest,
  EquityPoint,
  OptimizeRequest,
  OptimizeResponse,
  RegimeRequest,
  RegimeResult,
  ReportRequest,
  ReportResponse,
  StrategyComparisonResult,
  Trade,
  FilterSweepConfig,
  FilterSweepSummary,
  FilterSweepResult,
  FilterSweepListItem,
  FilterSweepPresetResponse,
  FilterSweepParamsResponse,
  FilterSweepRunResponse,
  FilterSweepStatusResponse,
} from '@/types/backtest';
import { fetchTVTemplate, fetchTVTemplates } from '@/api/screener';
import type { TVTemplate } from '@/types/screener';

// Re-export types for consumers
export type {
  FilterSweepConfig,
  FilterSweepSummary,
  FilterSweepResult,
  FilterSweepListItem,
  FilterSweepPresetResponse,
  FilterSweepParamsResponse,
  FilterSweepRunResponse,
  FilterSweepStatusResponse,
};

export async function runBacktest(
  body: BacktestRequest
): Promise<BacktestResultData> {
  return apiPost<BacktestResultData>('/api/v1/backtest', body);
}

export async function fetchBacktest(
  runId: string
): Promise<BacktestResultData> {
  return apiGet<BacktestResultData>(`/api/v1/backtest/${runId}`);
}

export async function fetchTrades(runId: string): Promise<Trade[]> {
  return apiGet<Trade[]>(`/api/v1/backtest/${runId}/trades`);
}

export async function fetchEquity(runId: string): Promise<EquityPoint[]> {
  return apiGet<EquityPoint[]>(`/api/v1/backtest/${runId}/equity`);
}

// ── Simple Backtest API (single run with template) ──

export interface SimpleBacktestRequest {
  template: string;
  symbols: string[];
  start: string;
  end: string;
  timeframe: string;
  initial_cash?: number;
  fees_bps?: number;
  slippage_bps?: number;
  position_sizing?: 'fixed' | 'atr' | 'kelly';
  sizing_params?: Record<string, unknown>;
}

export interface SimpleBacktestResponse {
  run_id: string;
  template: string;
  symbol: string;
  timeframe: string;
  metrics: {
    total_return: number;
    annualized_return: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    max_drawdown_pct: number;
    win_rate: number;
    profit_factor: number;
    expectancy: number;
    total_trades: number;
    avg_hold_days: number;
  };
  trades: Array<{
    trade_id: number;
    entry_date: string;
    exit_date: string;
    entry_price: number;
    exit_price: number;
    units: number;
    pnl: number;
    return_pct: number;
    hold_days: number;
  }>;
  equity_curve: Array<{ date: string; equity: number }>;
  duration_ms: number;
}

export async function runSimpleBacktest(
  request: SimpleBacktestRequest
): Promise<SimpleBacktestResponse> {
  // Use the ExternalBacktestEngine endpoint which uses Yahoo Finance + pandas (working)
  const templateResponse = await fetchTVTemplate(request.template);
  const signalParams: Record<string, unknown> = (templateResponse.signal_params || {}) as Record<string, unknown>;
  
  const sizingParams: Record<string, unknown> = request.sizing_params ? { ...request.sizing_params } : ({} as Record<string, unknown>);
  
  const backtestRequest = {
    template: request.template,
    symbols: request.symbols,
    start: request.start,
    end: request.end,
    timeframe: request.timeframe,
    initial_cash: request.initial_cash ?? 100_000,
    fees_bps: request.fees_bps ?? 10,
    slippage_bps: request.slippage_bps ?? 5,
    position_sizing: request.position_sizing ?? 'fixed',
    sizing_params: sizingParams,
    signal_params: signalParams,
  };
  
  const result = await apiPost<SimpleBacktestResponse>('/api/v1/backtest/external', backtestRequest);
  
  return result;
}

// Get available templates for backtest
export async function fetchBacktestTemplates(): Promise<TVTemplate[]> {
  return fetchTVTemplates();
}

// ── Phase 9: Advanced Backtest API Functions ──

export async function optimizeBacktest(
  body: OptimizeRequest
): Promise<OptimizeResponse> {
  return apiPost<OptimizeResponse>('/api/v1/backtest/optimize-v2', body);
}

export async function detectRegimes(
  body: RegimeRequest
): Promise<RegimeResult> {
  return apiPost<RegimeResult>('/api/v1/backtest/regimes', body);
}

export async function generateReport(
  runId: string,
  body: ReportRequest
): Promise<ReportResponse> {
  return apiPost<ReportResponse>(`/api/v1/backtest/${runId}/report`, body);
}

export async function compareBacktests(
  body: CompareRequest
): Promise<StrategyComparisonResult> {
  return apiPost<StrategyComparisonResult>('/api/v1/backtest/compare', body);
}

// ── Filter Sweep API Functions ──

export async function runFilterSweep(
  config: FilterSweepConfig
): Promise<{ sweep_id: string; status: string }> {
  return apiPost<{ sweep_id: string; status: string }>('/api/v1/filter-sweep/run', config);
}

export async function runPresetFilterSweep(
  presetName: string,
  overrides?: {
    symbols?: string[];
    start_date?: string;
    end_date?: string;
    optimization_metric?: string;
  }
): Promise<{ sweep_id: string; status: string }> {
  return apiPost<{ sweep_id: string; status: string }>(
    `/api/v1/filter-sweep/run-preset/${presetName}`,
    overrides
  );
}

export async function getFilterSweepStatus(sweepId: string): Promise<{ sweep_id: string; status: string }> {
  return apiGet<{ sweep_id: string; status: string }>(`/api/v1/filter-sweep/status/${sweepId}`);
}

export async function getFilterSweepResults(sweepId: string): Promise<FilterSweepSummary> {
  return apiGet<FilterSweepSummary>(`/api/v1/filter-sweep/result/${sweepId}`);
}

export async function listFilterSweeps(): Promise<FilterSweepListItem[]> {
  return apiGet<FilterSweepListItem[]>('/api/v1/filter-sweep/list');
}

export async function listFilterSweepPresets(): Promise<FilterSweepPresetResponse> {
  return apiGet<FilterSweepPresetResponse>('/api/v1/filter-sweep/presets');
}

export async function listFilterSweepParams(): Promise<FilterSweepParamsResponse> {
  return apiGet<FilterSweepParamsResponse>('/api/v1/filter-sweep/params');
}

export async function deleteFilterSweep(sweepId: string): Promise<{ message: string }> {
  return apiPost<{ message: string }>(`/api/v1/filter-sweep/${sweepId}/delete`, {});
}

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
} from '@/types/backtest';

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

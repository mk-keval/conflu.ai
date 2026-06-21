import apiClient from './client';
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

export async function runBacktest(body: BacktestRequest): Promise<BacktestResultData> {
  const response = await apiClient.post<BacktestResultData>(
    '/api/v1/backtest',
    body
  );
  return response.data;
}

export async function fetchBacktest(runId: string): Promise<BacktestResultData> {
  const response = await apiClient.get<BacktestResultData>(
    `/api/v1/backtest/${runId}`
  );
  return response.data;
}

export async function fetchTrades(runId: string): Promise<Trade[]> {
  const response = await apiClient.get<Trade[]>(
    `/api/v1/backtest/${runId}/trades`
  );
  return response.data;
}

export async function fetchEquity(runId: string): Promise<EquityPoint[]> {
  const response = await apiClient.get<EquityPoint[]>(
    `/api/v1/backtest/${runId}/equity`
  );
  return response.data;
}

// ── Phase 9: Advanced Backtest API Functions ──

export async function optimizeBacktest(body: OptimizeRequest): Promise<OptimizeResponse> {
  const response = await apiClient.post<OptimizeResponse>('/api/v1/backtest/optimize-v2', body);
  return response.data;
}

export async function detectRegimes(body: RegimeRequest): Promise<RegimeResult> {
  const response = await apiClient.post<RegimeResult>('/api/v1/backtest/regimes', body);
  return response.data;
}

export async function generateReport(runId: string, body: ReportRequest): Promise<ReportResponse> {
  const response = await apiClient.post<ReportResponse>(`/api/v1/backtest/${runId}/report`, body);
  return response.data;
}

export async function compareBacktests(body: CompareRequest): Promise<StrategyComparisonResult> {
  const response = await apiClient.post<StrategyComparisonResult>('/api/v1/backtest/compare', body);
  return response.data;
}

import apiClient from './client';
import type {
  BetaResult,
  CorrelationResult,
  VaRResult,
  PositionSizeRequest,
  PositionSizeResult,
  KellyRequest,
  KellyResult,
  RiskSummary,
} from '@/types/risk';

export async function fetchBeta(
  symbols: string[],
  benchmark?: string,
  window?: number
): Promise<BetaResult[]> {
  const params = new URLSearchParams();
  symbols.forEach((s) => params.append('symbols', s));
  if (benchmark) params.set('benchmark', benchmark);
  if (window) params.set('window', String(window));

  const response = await apiClient.get<BetaResult[]>(
    `/api/v1/risk/beta?${params.toString()}`
  );
  return response.data;
}

export async function fetchCorrelation(
  symbols: string[],
  window?: number,
  groupBy?: string
): Promise<CorrelationResult> {
  const params = new URLSearchParams();
  symbols.forEach((s) => params.append('symbols', s));
  if (window) params.set('window', String(window));
  if (groupBy) params.set('group_by', groupBy);

  const response = await apiClient.get<CorrelationResult>(
    `/api/v1/risk/correlation?${params.toString()}`
  );
  return response.data;
}

export async function fetchVaR(
  symbols: string[],
  confidence?: number,
  method?: string,
  horizon?: number
): Promise<VaRResult> {
  const params = new URLSearchParams();
  symbols.forEach((s) => params.append('symbols', s));
  if (confidence) params.set('confidence', String(confidence));
  if (method) params.set('method', method);
  if (horizon) params.set('horizon', String(horizon));

  const response = await apiClient.get<VaRResult>(
    `/api/v1/risk/var?${params.toString()}`
  );
  return response.data;
}

export async function postPositionSize(
  body: PositionSizeRequest
): Promise<PositionSizeResult> {
  const response = await apiClient.post<PositionSizeResult>(
    '/api/v1/risk/position-size',
    body
  );
  return response.data;
}

export async function postKelly(body: KellyRequest): Promise<KellyResult> {
  const response = await apiClient.post<KellyResult>(
    '/api/v1/risk/kelly',
    body
  );
  return response.data;
}

export async function fetchRiskSummary(
  portfolioId?: string,
  symbols?: string[]
): Promise<RiskSummary> {
  const params = new URLSearchParams();
  if (portfolioId) params.set('portfolio_id', portfolioId);
  if (symbols) symbols.forEach((s) => params.append('symbols', s));

  const response = await apiClient.get<RiskSummary>(
    `/api/v1/risk/summary?${params.toString()}`
  );
  return response.data;
}

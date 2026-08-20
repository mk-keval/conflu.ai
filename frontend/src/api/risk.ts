import { apiGet, apiPost } from './client';
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

  return apiGet<BetaResult[]>(`/api/v1/risk/beta?${params.toString()}`);
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

  return apiGet<CorrelationResult>(`/api/v1/risk/correlation?${params.toString()}`);
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

  return apiGet<VaRResult>(`/api/v1/risk/var?${params.toString()}`);
}

export async function postPositionSize(
  body: PositionSizeRequest
): Promise<PositionSizeResult> {
  return apiPost<PositionSizeResult>('/api/v1/risk/position-size', body);
}

export async function postKelly(body: KellyRequest): Promise<KellyResult> {
  return apiPost<KellyResult>('/api/v1/risk/kelly', body);
}

export async function fetchRiskSummary(
  portfolioId?: string,
  symbols?: string[]
): Promise<RiskSummary> {
  const params = new URLSearchParams();
  if (portfolioId) params.set('portfolio_id', portfolioId);
  if (symbols) symbols.forEach((s) => params.append('symbols', s));

  return apiGet<RiskSummary>(`/api/v1/risk/summary?${params.toString()}`);
}

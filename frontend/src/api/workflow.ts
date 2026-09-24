import { apiPost } from './client';

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

// ── API calls ──

export async function analyzePortfolio(
  symbols: string[]
): Promise<PortfolioResponse> {
  return apiPost<PortfolioResponse>('/api/v1/portfolio/analyze', { symbols });
}

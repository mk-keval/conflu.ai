export interface BetaResult {
  symbol: string;
  beta: number;
  r_squared: number;
  tracking_error: number;
}

export interface CorrelationResult {
  timestamp: string;
  window_days: number;
  symbols: string[];
  correlation_matrix: number[][];
  sector_matrix?: { rows: string[]; matrix: number[][] } | null;
  high_correlation_pairs: Array<{ symbols: [string, string]; correlation: number }>;
  diversification_score: number;
}

export interface VaRResult {
  var: number;
  cvar: number;
  confidence: number;
  method: string;
}

export interface PositionSizeRequest {
  symbols: string[];
  method: 'atr' | 'kelly' | 'fixed';
  cash: number;
  params: Record<string, unknown>;
}

export interface PositionSizeResult {
  sizes: Record<string, number>;
  method: string;
  cash: number;
}

export interface KellyRequest {
  backtest_run_id: string;
  max_dd_target: number;
}

export interface KellyResult {
  kelly_pct: number;
  half_kelly_pct: number;
  edge: number;
  odds: number;
}

export interface RiskSummary {
  portfolio_id: string;
  num_positions: number;
  total_exposure: number;
  var_95: number;
  cvar_95: number;
  beta_weighted: number;
  diversification_score: number;
}

export interface BacktestRequest {
  symbols: string[];
  start: string;
  end: string;
  initial_cash: number;
  fees_bps: number;
  slippage_bps: number;
  position_sizing: 'fixed' | 'atr' | 'kelly';
  sizing_params: Record<string, unknown>;
  signal_params: Record<string, unknown>;
}

export interface BacktestResultData {
  run_id: string;
  symbol: string;
  timeframe: string;
  metrics: Metrics | null;
  trades_count: number;
  duration_ms: number;
}

export interface Metrics {
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_return_pct: number;
  profit_factor: number;
  expectancy: number;
  sqn: number;
  ulcer_index: number;
}

export interface Trade {
  run_id: string;
  trade_index: number;
  symbol: string;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  size: number;
  direction: 'Long' | 'Short';
  pnl: number;
  fees: number;
  mae: number;
  mfe: number;
  hold_duration_bars: number;
  exit_reason: string;
}

export interface EquityPoint {
  timestamp: string;
  equity: number;
}

export interface OptimizationResult {
  fold: number;
  params: Record<string, unknown>;
  metrics: Metrics;
}

// ── Phase 9: Advanced Backtest Types ──

export interface OptimizeRequest {
  symbols: string[];
  start: string;
  end: string;
  initial_cash: number;
  fees_bps: number;
  slippage_bps: number;
  position_sizing: 'fixed' | 'atr' | 'kelly';
  sizing_params: Record<string, unknown>;
  signal_params: Record<string, unknown>;
  method: 'grid' | 'random' | 'bayesian';
  grid_params: Record<string, unknown[]>;
  param_distributions: Record<string, Record<string, unknown>>;
  objectives: string[];
  max_trials: number;
  timeout_s: number | null;
  n_jobs: number;
  early_stopping: boolean;
}

export interface OptimizeResponse {
  study_id: string;
  symbol: string;
  method: string;
  best_params: Record<string, unknown>;
  best_objectives: Record<string, number | null>;
  n_trials: number;
  duration_ms: number;
  param_importance: Record<string, number>;
}

export interface RegimeRequest {
  symbols: string[];
  start: string;
  end: string;
  method: 'hmm' | 'volatility_quantile';
  n_states: number;
  window_days: number;
}

export interface RegimeResult {
  symbol: string;
  method: string;
  n_states: number;
  regime_labels: number[];
  regime_names: string[];
  transition_matrix: number[][] | null;
  state_means: number[] | null;
  state_stds: number[] | null;
  timestamps: string[];
}

export interface ReportRequest {
  formats: ('html' | 'pdf' | 'json')[];
  template: string;
  include_equity_curve: boolean;
  include_drawdown: boolean;
  include_trade_analysis: boolean;
  include_regime_analysis: boolean;
  include_parameter_sensitivity: boolean;
}

export interface ReportResponse {
  report_id: string;
  formats: { format: string; download_url: string }[];
  size_bytes: number;
  created_at: string;
}

export interface CompareRequest {
  run_ids: string[];
  labels: string[] | null;
  include_significance: boolean;
  bootstrap_samples: number;
}

export interface StrategyComparisonResult {
  comparison_id: string;
  run_ids: string[];
  labels: string[];
  n_strategies: number;
  best_by_metric: Record<string, string>;
  metrics_table: Record<string, unknown>[];
  significance_matrix: (number | null)[][];
  equity_curves: Record<string, { timestamp: string; value: number }[]>;
  drawdown_curves: Record<string, { timestamp: string; value: number }[]>;
}

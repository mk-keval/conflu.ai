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

// ── Filter Sweep Types ──

export interface FilterParamRange {
  name: string;
  display_name: string;
  param_type: 'int' | 'float' | 'categorical';
  low?: number;
  high?: number;
  step?: number;
  choices?: string[];
  description: string;
}

export interface FilterSweepConfig {
  sweep_id?: string;
  name: string;
  description: string;
  screen_name: string;
  param_grid: Record<string, FilterParamRange>;
  symbols: string[];
  timeframe: string;
  start_date: string;
  end_date?: string;
  initial_cash: number;
  fees_bps: number;
  slippage_bps: number;
  position_sizing: 'fixed' | 'atr' | 'kelly';
  sizing_params: Record<string, unknown>;
  optimization_metric: 'sharpe' | 'sortino' | 'calmar' | 'win_rate' | 'profit_factor' | 'expectancy';
  max_combinations: number;
  parallel_jobs: number;
}

export interface FilterSweepResult {
  params: Record<string, unknown>;
  total_return: number | null;
  annualized_return: number | null;
  sharpe: number | null;
  sortino: number | null;
  calmar: number | null;
  max_drawdown: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  avg_hold_days: number | null;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  max_drawdown_pct: number | null;
  recovery_factor: number | null;
  payoff_ratio: number | null;
  best_trade: number | null;
  worst_trade: number | null;
  run_id: string;
  config_hash: string;
  valid: boolean;
  error_message?: string;
}

export interface FilterSweepSummary {
  sweep_id: string;
  name: string;
  screen_name: string;
  total_combinations: number;
  valid_results: number;
  failed_results: number;
  best_by_sharpe: FilterSweepResult | null;
  best_by_expectancy: FilterSweepResult | null;
  best_by_win_rate: FilterSweepResult | null;
  best_by_profit_factor: FilterSweepResult | null;
  best_by_calmar: FilterSweepResult | null;
  param_sensitivity: Record<string, Record<string, number>>;
  all_results: FilterSweepResult[];
  sweep_config: Record<string, unknown>;
  created_at: string;
  duration_ms: number;
  status: 'running' | 'completed' | 'failed';
  error_message?: string;
}

export interface FilterSweepPreset {
  name: string;
  description: string;
  screen_name: string;
  symbols: string[];
  timeframe: string;
  start_date: string;
  end_date: string;
  optimization_metric: string;
  max_combinations: number;
  params: Record<string, FilterParamRange>;
}

export interface FilterSweepListItem {
  sweep_id: string;
  name: string;
  screen_name: string;
  status: string;
  total_combinations: number;
  valid_results: number;
  failed_results: number;
  best_expectancy: number | null;
  best_sharpe: number | null;
  created_at: string;
  duration_ms: number;
}

export interface FilterSweepPresetResponse {
  [presetName: string]: {
    name: string;
    description: string;
    screen_name: string;
    symbols: string[];
    timeframe: string;
    start_date: string;
    end_date: string;
    optimization_metric: string;
    max_combinations: number;
    params: Record<string, FilterParamRange>;
  };
}

export interface FilterSweepParamsResponse {
  [paramName: string]: FilterParamRange;
}

export interface FilterSweepRunResponse {
  sweep_id: string;
  status: string;
}

export interface FilterSweepStatusResponse {
  sweep_id: string;
  status: string;
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

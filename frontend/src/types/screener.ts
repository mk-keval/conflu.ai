// ── TV Screener API Types ──

export interface TVScreenRequest {
  config: string | Record<string, unknown>;
  limit?: number;
  multi_timeframe?: boolean;
}

export interface TVScreenResponse {
  screen_name: string;
  total_matches: number;
  execution_ms: number;
  timeframe: string;
  results: TVScoredTicker[];
}

export interface TVScoredTicker {
  symbol: string;
  score: number;
  breakdown: Record<string, number>;
  entry: number;
  stop_loss: number;
  targets: number[];
  risk_reward: number;
  rating: string;
  tv_data: TVDataFields;
  /** Per-timeframe breakdown (populated for multi-TF screens only). */
  mtf_breakdown?: TVMTFBreakdown[];
}

export interface TVMTFBreakdown {
  timeframe: string;
  weight: number;
  matched: boolean;
  score: number;
}

/** Fields returned by TradingView screener in the `tv_data` envelope. */
export interface TVDataFields {
  ticker: string;
  /** Human-readable name (same as symbol for most stocks). */
  name: string;
  /** Last traded price. */
  close: number;
  /** Raw price change (close − previous_close). */
  change: number;
  /** 10-day average relative volume ratio. */
  relative_volume_10d_calc?: number;
  /** Total market capitalisation in USD. */
  market_cap_basic?: number;
  /** Trailing-twelve-months P/E ratio. */
  price_earnings_ttm?: number;
  /** TTM diluted EPS. */
  earnings_per_share_diluted_ttm?: number;
  /** Current dividend yield (%). */
  dividends_yield_current?: number;
  /** Sector classification. */
  sector?: string;
  /** TradingView-displayed exchange/country. */
  market?: string;
  /** Analyst consensus rating. */
  AnalystRating?: string;
  /** Trading currency. */
  currency?: string;
  /** TradingView price scale (default 100). */
  pricescale?: number;
  /** Number of shares traded. */
  volume?: number;
  /** Exchange suffix. */
  type?: string;
}

export interface TVTemplate {
  name: string;
  description: string;
}

export interface TVDeepAnalysisRequest {
  symbol: string;
  timeframe: string;
  include_backtest?: boolean;
  include_risk?: boolean;
  /** TV screener row data passed as fallback when OHLCV is unavailable. */
  tv_data?: TVDataFields;
}

export interface TVConfluenceFallback {
  confluence_score: number;
  breakdown: Record<string, number>;
  entry: number;
  stop_loss: number;
  targets: number[];
  risk_reward: number;
  rating: string;
}

export interface TVDeepAnalysisResponse {
  symbol: string;
  timeframe: string;
  confluence_score: number;
  entry: number;
  stop_loss: number;
  targets: number[];
  backtest: Record<string, unknown> | null;
  risk: Record<string, unknown> | null;
  execution_ms: number;
  /** Whether full OHLCV-backed deep analysis was available. */
  has_ohlcv?: boolean;
  /** TV-data-only fallback values (present when has_ohlcv=false). */
  tv_fallback?: TVConfluenceFallback | null;
}

// ── Legacy Types (for old architecture) ──

export interface ScreenRequest {
  config: string;
  symbols?: string[];
  timeframes?: string[];
  export_format?: 'json' | 'csv';
}

export interface ScreenSymbolResult {
  symbol: string;
  score: number;
  matched_filters: string[];
  indicator_values: Record<string, number>;
}

export interface SymbolInfo {
  symbol: string;
  asset_class: string;
  exchange: string;
  tv_ticker: string;
  name: string;
  active: boolean;
}

// --- Phase 8: Advanced Screener Types ---

export interface SavedScreen {
  id: string;
  user_id: string;
  name: string;
  description: string;
  filter_json: string;
  asset_classes: string[];
  timeframes: string[];
  tags: string[];
  version: number;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface SavedScreenListItem {
  id: string;
  name: string;
  description: string;
  version: number;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  tags: string[];
}

export interface ScreenVersionSummary {
  version: number;
  name: string;
  created_at: string;
}

export interface CreateScreenRequest {
  name: string;
  description?: string;
  filter_json: string;
  asset_classes?: string[];
  timeframes?: string[];
  tags?: string[];
  is_public?: boolean;
}

export interface UpdateScreenRequest {
  name?: string;
  description?: string;
  filter_json?: string;
  asset_classes?: string[];
  timeframes?: string[];
  tags?: string[];
  is_public?: boolean;
}

export interface AlertRule {
  id: string;
  user_id?: string;
  name: string;
  description: string;
  alert_type: AlertConditionType;
  condition_json: string;
  symbols: string[];
  timeframes: string[];
  is_active: boolean;
  cooldown_seconds: number;
  last_triggered_at: string | null;
  trigger_count: number;
  created_at: string;
  updated_at: string;
}

export type AlertConditionType =
  | 'price_threshold'
  | 'indicator_cross'
  | 'signal_trigger'
  | 'volume_spike'
  | 'trend_break'
  | 'compound';

export interface CreateAlertRequest {
  name: string;
  description?: string;
  alert_type: AlertConditionType;
  condition_json: string;
  symbols?: string[];
  timeframes?: string[];
  is_active?: boolean;
  cooldown_seconds?: number;
}

export interface UpdateAlertRequest {
  name?: string;
  description?: string;
  condition_json?: string;
  symbols?: string[];
  timeframes?: string[];
  is_active?: boolean;
  cooldown_seconds?: number;
}

export interface AlertHistoryEntry {
  id: string;
  alert_id: string;
  symbol: string | null;
  triggered_at: string;
  condition_matched: string | null;
  value_at_trigger: number | null;
  threshold: number | null;
  dismissed: boolean;
}

export interface ScreenReplayResult {
  id: string;
  screen_config_id: string;
  version: number;
  start_date: string;
  end_date: string;
  total_days: number;
  avg_match_count: number | null;
  max_match_count: number | null;
  min_match_count: number | null;
  total_signals: number | null;
  win_rate: number | null;
  avg_return: number | null;
  total_return: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  equity_curve: { date: string; equity: number }[];
  match_series: { date: string; match_count: number }[];
}

export interface ReplayRequest {
  screen_config_id: string;
  version?: number;
  start_date?: string;
  end_date?: string;
}

export interface ShareTokenResponse {
  token: string;
  url: string;
  expires_at: string;
}

export interface ScreenVersion {
  id: string;
  screen_config_id: string;
  version: number;
  name: string;
  filter_json: string;
  asset_classes: string[];
  timeframes: string[];
  tags: string[];
  created_at: string;
  snapshot_data: string | null;
}

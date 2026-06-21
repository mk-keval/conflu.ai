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

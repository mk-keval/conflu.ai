import type { ScreenSymbolResult } from './screener';

export type ConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'reconnecting';

export type WSChannelType =
  | 'price'
  | 'indicator'
  | 'signal'
  | 'screener'
  | 'risk'
  | 'backtest'
  | 'alert'
  | 'replay';

export interface WSSubscriptionMessage {
  type: 'subscribe' | 'unsubscribe';
  channels: string[];
}

export interface WSConnectedMessage {
  type: 'connected';
  connection_id: string;
  timestamp: string;
  server_version: string;
}

export interface WSPriceUpdate {
  type: 'price_update';
  channel: string;
  sequence: number;
  timestamp: string;
  data: {
    symbol: string;
    price: number;
    change_pct: number;
    volume: number;
    timestamp: string;
  };
}

export interface WSIndicatorUpdate {
  type: 'indicator_update';
  channel: string;
  sequence: number;
  data: {
    symbol: string;
    indicator: string;
    value: number;
    timestamp: string;
  };
}

export interface WSScreenUpdate {
  type: 'screen_update';
  channel: string;
  sequence: number;
  data: {
    screen_name: string;
    total_matched: number;
    total_symbols: number;
    symbols: ScreenSymbolResult[];
  };
}

export interface WSBacktestUpdate {
  type: 'backtest_update';
  channel: string;
  sequence: number;
  data: {
    run_id: string;
    status: 'running' | 'complete' | 'error';
    progress_pct: number;
    message: string;
  };
}

export interface WSErrorMessage {
  type: 'error';
  channel?: string;
  code: string;
  message: string;
}

export interface WSPongMessage {
  type: 'pong';
  timestamp: string;
}

export interface WSResyncRequiredMessage {
  type: 'resync_required';
  message: string;
  current_sequence: number;
}

// Phase 8: Alert & Replay WebSocket messages
export interface WSAlertTriggered {
  type: 'alert_triggered';
  channel: string;
  timestamp: string;
  data: {
    alert_id: string;
    alert_name: string;
    alert_type: string;
    symbol: string | null;
    timeframe: string | null;
    triggered_at: string;
    condition_matched: string | null;
    value_at_trigger: number | null;
    threshold: number | null;
    severity: string;
    message: string;
    deep_link: string;
  };
}

export interface WSReplayProgress {
  type: 'replay_progress';
  channel: string;
  data: {
    screen_config_id: string;
    progress_pct: number;
    current_day: number;
    total_days: number;
    status: 'running' | 'complete' | 'error';
  };
}

export interface WSReplayComplete {
  type: 'replay_complete';
  channel: string;
  data: {
    screen_config_id: string;
    result_id: string;
  };
}

export type WSMessage =
  | WSConnectedMessage
  | WSPriceUpdate
  | WSIndicatorUpdate
  | WSScreenUpdate
  | WSBacktestUpdate
  | WSAlertTriggered
  | WSReplayProgress
  | WSReplayComplete
  | WSErrorMessage
  | WSPongMessage
  | WSResyncRequiredMessage;

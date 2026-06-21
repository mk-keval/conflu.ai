export const TIMEFRAMES = ['1D', '4H', '1H', '15m'] as const;

export const INDICATOR_COLORS = {
  rsi: '#7B68EE',
  macd: '#22C55E',
  ema_20: '#F59E0B',
  ema_50: '#EF4444',
  bb_upper: '#60A5FA',
  bb_lower: '#60A5FA',
  atr: '#EC4899',
} as const;

export const SCREEN_TEMPLATES = [
  'trend-follower',
  'momentum-breakout',
  'mean-reversion',
  'high-volume',
  'low-volatility',
] as const;

export const ASSET_CLASSES = [
  'equities',
  'crypto',
  'forex',
  'commodities',
  'indices',
] as const;

export const WS_URL = 'ws://localhost:8000/ws/stream';

export const STALE_TIMES = {
  screen: 5000,
  ohlcv: 30000,
  indicators: 10000,
  backtest: Infinity,
  risk: 30000,
  symbols: Infinity,
} as const;

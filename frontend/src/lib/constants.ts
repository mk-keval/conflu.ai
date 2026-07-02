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
  'trend-follower-mtf',
  'breakout',
  'mean-reversion',
  'oversold-bounce',
  'volume-surge',
  '52week-breakout',
  'low-vol-setup',
] as const;

export interface FilterParam {
  key: string;
  label: string;
  type: 'number' | 'select' | 'boolean';
  defaultValue: string | number | boolean;
  options?: string[];
  min?: number;
  max?: number;
  step?: number;
}

export interface FilterRuleConfig {
  category: string;
  indicator: string;
  label: string;
  operator: string;
  timeframe: string;
  negate: boolean;
  params: Record<string, FilterParam>;
  compareTimeframe?: string; // For multi-timeframe filters
}

export interface ScreenTemplateConfig {
  name: string;
  description: string;
  assetClasses: string[];
  timeframes: string[];
  filters: FilterRuleConfig[];
}

export const SCREEN_TEMPLATE_CONFIGS: Record<string, ScreenTemplateConfig> = {
  'trend-follower': {
    name: 'Trend Follower',
    description: 'Uptrending assets with momentum and volume confirmation',
    assetClasses: ['equities', 'crypto'],
    timeframes: ['1D', '4h'],
    filters: [
      {
        category: 'trend',
        indicator: 'price_above_ema',
        label: 'Price Above EMA',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          period: { key: 'period', label: 'EMA Period', type: 'number', defaultValue: 200, min: 10, max: 500, step: 10 },
        },
      },
      {
        category: 'trend',
        indicator: 'adx_trending',
        label: 'ADX Trending',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'ADX Threshold', type: 'number', defaultValue: 25, min: 10, max: 50, step: 1 },
        },
      },
      {
        category: 'momentum',
        indicator: 'macd_bullish',
        label: 'MACD Bullish',
        operator: 'gt',
        timeframe: '4h',
        negate: false,
        params: {},
      },
      {
        category: 'volume',
        indicator: 'rvol_high',
        label: 'High Relative Volume',
        operator: 'gt',
        timeframe: '4h',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RVOL Threshold', type: 'number', defaultValue: 1.2, min: 0.5, max: 5, step: 0.1 },
        },
      },
    ],
  },
  'trend-follower-mtf': {
    name: 'Trend Follower (Multi-Timeframe)',
    description: 'EMA50 > EMA200 on daily, RSI > 60 daily, RSI > 550 > 55 weekly',
    assetClasses: ['equities', 'crypto'],
    timeframes: ['1D', '4h', '1W'],
    filters: [
      {
        category: 'trend',
        indicator: 'ema_compare',
        label: 'EMA50 > EMA200 (Daily)',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          fast_period: { key: 'fast_period', label: 'Fast EMA', type: 'number', defaultValue: 50, min: 5, max: 100, step: 5 },
          slow_period: { key: 'slow_period', label: 'Slow EMA', type: 'number', defaultValue: 200, min: 50, max: 500, step: 10 },
          operator: { key: 'operator', label: 'Operator', type: 'select', defaultValue: 'gt', options: ['gt', 'lt'] },
        },
      },
      {
        category: 'momentum',
        indicator: 'rsi_compare',
        label: 'RSI Daily > 60',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RSI Threshold', type: 'number', defaultValue: 60, min: 40, max: 80, step: 1 },
          operator: { key: 'operator', label: 'Operator', type: 'select', defaultValue: 'gt', options: ['gt', 'lt'] },
        },
      },
      {
        category: 'momentum',
        indicator: 'rsi_compare',
        label: 'RSI Weekly > 55',
        operator: 'gt',
        timeframe: '1W',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RSI Threshold', type: 'number', defaultValue: 55, min: 40, max: 80, step: 1 },
          operator: { key: 'operator', label: 'Operator', type: 'select', defaultValue: 'gt', options: ['gt', 'lt'] },
        },
      },
      {
        category: 'volume',
        indicator: 'rvol_high',
        label: 'High Relative Volume',
        operator: 'gt',
        timeframe: '4h',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RVOL Threshold', type: 'number', defaultValue: 1.2, min: 0.5, max: 5, step: 0.1 },
        },
      },
    ],
  },
  'breakout': {
    name: 'Breakout',
    description: 'Price breaking out with volume and momentum confirmation',
    assetClasses: ['equities', 'crypto'],
    timeframes: ['1D', '4h'],
    filters: [
      {
        category: 'trend',
        indicator: 'price_above_ema',
        label: 'Price Above EMA',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          period: { key: 'period', label: 'EMA Period', type: 'number', defaultValue: 50, min: 10, max: 200, step: 10 },
        },
      },
      {
        category: 'volume',
        indicator: 'rvol_high',
        label: 'High Relative Volume',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RVOL Threshold', type: 'number', defaultValue: 1.5, min: 0.5, max: 5, step: 0.1 },
        },
      },
      {
        category: 'momentum',
        indicator: 'macd_bullish',
        label: 'MACD Bullish',
        operator: 'gt',
        timeframe: '4h',
        negate: false,
        params: {},
      },
    ],
  },
  'mean-reversion': {
    name: 'Mean Reversion',
    description: 'Oversold assets near Bollinger Band lower with volume spike',
    assetClasses: ['equities', 'crypto', 'forex'],
    timeframes: ['1D', '1h'],
    filters: [
      {
        category: 'momentum',
        indicator: 'rsi_oversold',
        label: 'RSI Oversold',
        operator: 'lt',
        timeframe: '1D',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RSI Threshold', type: 'number', defaultValue: 30, min: 10, max: 50, step: 1 },
        },
      },
      {
        category: 'volatility',
        indicator: 'bb_touch',
        label: 'Bollinger Band Touch',
        operator: 'eq',
        timeframe: '1D',
        negate: false,
        params: {},
      },
      {
        category: 'volume',
        indicator: 'rvol_high',
        label: 'High Relative Volume',
        operator: 'gt',
        timeframe: '1h',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RVOL Threshold', type: 'number', defaultValue: 1.5, min: 0.5, max: 5, step: 0.1 },
        },
      },
    ],
  },
  'oversold-bounce': {
    name: 'Oversold Bounce',
    description: 'Deeply oversold with bullish reversal pattern',
    assetClasses: ['equities', 'crypto'],
    timeframes: ['1D', '4h'],
    filters: [
      {
        category: 'momentum',
        indicator: 'rsi_oversold',
        label: 'RSI Oversold',
        operator: 'lt',
        timeframe: '1D',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RSI Threshold', type: 'number', defaultValue: 25, min: 5, max: 40, step: 1 },
        },
      },
      {
        category: 'volatility',
        indicator: 'bb_touch',
        label: 'Bollinger Band Touch',
        operator: 'eq',
        timeframe: '1D',
        negate: false,
        params: {},
      },
      {
        category: 'pattern',
        indicator: 'candle_engulfing',
        label: 'Bullish Engulfing',
        operator: 'eq',
        timeframe: '1D',
        negate: false,
        params: {
          direction: { key: 'direction', label: 'Direction', type: 'select', defaultValue: 'bullish', options: ['bullish', 'bearish'] },
        },
      },
    ],
  },
  '52week-breakout': {
    name: '52-Week Breakout',
    description: 'Stocks near 52-week highs with momentum and volume confirmation',
    assetClasses: ['equities'],
    timeframes: ['1D', '4h'],
    filters: [
      {
        category: 'trend',
        indicator: 'price_above_ema',
        label: 'Price Above EMA200',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          period: { key: 'period', label: 'EMA Period', type: 'number', defaultValue: 200, min: 50, max: 500, step: 10 },
        },
      },
      {
        category: 'momentum',
        indicator: 'macd_bullish',
        label: 'MACD Bullish',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {},
      },
      {
        category: 'volume',
        indicator: 'rvol_high',
        label: 'High Relative Volume',
        operator: 'gt',
        timeframe: '4h',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RVOL Threshold', type: 'number', defaultValue: 1.2, min: 0.5, max: 5, step: 0.1 },
        },
      },
    ],
  },
  'low-vol-setup': {
    name: 'Low-Vol Setup',
    description: 'Low volatility stocks with steady trend and tight Bollinger Bands',
    assetClasses: ['equities'],
    timeframes: ['1D'],
    filters: [
      {
        category: 'trend',
        indicator: 'price_above_ema',
        label: 'Price Above EMA50',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          period: { key: 'period', label: 'EMA Period', type: 'number', defaultValue: 50, min: 10, max: 200, step: 10 },
        },
      },
      {
        category: 'volatility',
        indicator: 'bb_squeeze',
        label: 'Bollinger Band Squeeze',
        operator: 'eq',
        timeframe: '1D',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'BB Width', type: 'number', defaultValue: 1.15, min: 1.05, max: 2.0, step: 0.05 },
        },
      },
      {
        category: 'volume',
        indicator: 'rvol_high',
        label: 'Moderate Relative Volume',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RVOL Threshold', type: 'number', defaultValue: 1.0, min: 0.5, max: 5, step: 0.1 },
        },
      },
    ],
  },
  'volume-surge': {
    name: 'Volume Surge',
    description: 'High relative volume with above-average price movement',
    assetClasses: ['equities', 'crypto', 'forex'],
    timeframes: ['1D', '1h'],
    filters: [
      {
        category: 'volume',
        indicator: 'rvol_high',
        label: 'High Relative Volume',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          threshold: { key: 'threshold', label: 'RVOL Threshold', type: 'number', defaultValue: 2.0, min: 1, max: 10, step: 0.1 },
        },
      },
      {
        category: 'volatility',
        indicator: 'atr_percentile_high',
        label: 'ATR Percentile High',
        operator: 'gt',
        timeframe: '1D',
        negate: false,
        params: {
          percentile: { key: 'percentile', label: 'Percentile', type: 'number', defaultValue: 75, min: 50, max: 95, step: 5 },
        },
      },
      {
        category: 'momentum',
        indicator: 'macd_bullish',
        label: 'MACD Bullish',
        operator: 'gt',
        timeframe: '1h',
        negate: false,
        params: {},
      },
    ],
  },
};

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

export interface OHLCVCandle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OHLCVResponse {
  symbol: string;
  timeframe: string;
  candles: OHLCVCandle[];
}

export interface IndicatorPoint {
  timestamp: string;
  value: number;
}

export interface IndicatorResponse {
  symbol: string;
  timeframe: string;
  indicators: Record<string, IndicatorPoint[]>;
}

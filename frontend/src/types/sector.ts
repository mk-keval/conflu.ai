/** Sector rotation data types for the smart money flow tracker. */

export interface SectorPerformance {
  symbol: string;
  name: string;
  description: string;
  price: number;
  change_1d: number | null;
  change_1w: number | null;
  change_1m: number | null;
  volume_1d: number;
  volume_vs_avg: number | null;
  volume_vs_avg_1w: number | null;
  relative_strength_1d: number | null;
  relative_strength_1w: number | null;
  momentum_score: number | null;
  trend: 'bullish' | 'bearish' | 'neutral' | 'slight_bullish' | 'slight_bearish';
  flow_signal: 'inflow' | 'outflow' | 'neutral';
  flow_strength: number;
  flow_signal_1w: 'inflow' | 'outflow' | 'neutral';
  flow_strength_1w: number;
}

export interface SectorRotationResponse {
  sectors: SectorPerformance[];
  leaders: string[];
  laggards: string[];
  rotation_phase: string;
  market_regime: string;
  timestamp: string;
}

export interface RotationHistoryPoint {
  date: string;
  sector_rankings: Record<string, number>;
}

export interface SectorDetail {
  symbol: string;
  name: string;
  description: string;
  performance: SectorPerformance;
  price_history: Array<{ date: string; close: number; volume: number }>;
  relative_strength_history: Array<{ date: string; value: number }>;
  components: string[];
}

export type TimeframeOption = '1D' | '1W';

/** Market regime indicator with score and raw value. */
export interface RegimeIndicator {
  name: string;
  value: number;
  score: number;
  weight: number;
  status: string;
}

/** Full market regime snapshot from /api/v1/market/regime. */
export interface MarketRegimeResponse {
  composite_score: number;
  regime_label: string;
  regime_color: string;
  vix: RegimeIndicator;
  risk_appetite: RegimeIndicator;
  sector_breadth: RegimeIndicator;
  safe_haven: RegimeIndicator;
  yield_curve: RegimeIndicator;
  timestamp: string;
}

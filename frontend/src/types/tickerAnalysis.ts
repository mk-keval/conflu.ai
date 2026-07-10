// ── Ticker Analysis Types ──

export interface TechnicalAnalysis {
  score: number;
  ma_alignment: 'bullish' | 'bearish' | 'mixed';
  rsi: number | null;
  rsi_regime: string;
  adx: number | null;
  adx_verdict: string;
  atr_pct: number | null;
  volatility_regime: string;
  volume_ratio: number | null;
  bb_position: string | null;
  macd_status: string | null;
  findings: string[];
}

export interface FundamentalAnalysis {
  score: number;
  market_cap: number | null;
  pe_ratio: number | null;
  eps: number | null;
  profit_margin: number | null;
  debt_to_equity: number | null;
  revenue_growth_yoy: number | null;
  fcf_yield: number | null;
  dividend_yield: number | null;
  findings: string[];
}

export interface EarningsAnalysis {
  score: number;
  last_surprise_pct: number | null;
  beat_rate: string | null;
  avg_reaction_pct: number | null;
  next_earnings_date: string | null;
  findings: string[];
}

export interface SentimentAnalysis {
  score: number;
  analyst_consensus: string;
  insider_status: string;
  short_interest_pct: number | null;
  days_to_cover: number | null;
  findings: string[];
}

export interface RiskAssessment {
  score: number;
  volatility_regime: string;
  suggested_stop_pct: number;
  suggested_position_size_pct: number;
  max_risk_per_trade_pct: number;
  findings: string[];
}

export interface AnalysisVerdict {
  action: string;
  conviction: number;
  entry_zone_low: number | null;
  entry_zone_high: number | null;
  stop_loss: number | null;
  targets: number[];
  risk_reward: number | null;
  position_size_pct: number;
  key_red_flags: string[];
  buy_triggers: string[];
  sell_triggers: string[];
  thesis: string;
}

export interface TickerAnalysisResponse {
  symbol: string;
  price: number | null;
  change_pct: number | null;
  sector: string | null;
  technical: TechnicalAnalysis | null;
  fundamental: FundamentalAnalysis | null;
  earnings: EarningsAnalysis | null;
  sentiment: SentimentAnalysis | null;
  risk: RiskAssessment | null;
  verdict: AnalysisVerdict;
  execution_ms: number;
}

export interface TickerAnalysisRequest {
  symbol: string;
  timeframe?: string;
  tv_data?: Record<string, unknown> | null;
  regime?: string | null;
}

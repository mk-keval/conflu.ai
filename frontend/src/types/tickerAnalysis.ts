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
  // Market structure (new)
  structure: string | null;  // bullish / bearish / ranging / transition
  swing_highs: number[] | null;
  swing_lows: number[] | null;
  key_resistance: number[] | null;
  key_support: number[] | null;
  pullback_quality: string | null;  // A+ / A / B / C / D / F
  pullback_score: number | null;    // 0-100
  // Volume profile (TPO)
  volume_profile?: {
    poc: number;
    vah: number;
    val: number;
    hvn: number[];
    lvn: number[];
    distribution: Record<string, number>;
  };
  findings: string[];
}

export interface MultiTimeframeTechnical {
  daily: TechnicalAnalysis;
  weekly?: TechnicalAnalysis;
  '4h'?: TechnicalAnalysis;
  '1h'?: TechnicalAnalysis;
}

export interface FundamentalAnalysis {
  score: number;
  instrument_type: string;
  listing_exchange: string | null;
  exchange_category: string;
  asset_category: string;
  lifecycle_stage: string;
  market_cap: number | null;
  pe_ratio: number | null;
  eps: number | null;
  profit_margin: number | null;
  debt_to_equity: number | null;
  revenue_growth_yoy: number | null;
  fcf_yield: number | null;
  dividend_yield: number | null;
  return_on_equity: number | null;
  price_to_book: number | null;
  operating_margin: number | null;
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
  institutional_ownership: number | null;
  beta: number | null;
  target_price: number | null;
  target_upside_pct: number | null;
  undervalued: boolean;
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
  // Critical blocking issues (distinct from advisory red flags)
  dealbreakers?: string[];
  key_red_flags: string[];
  buy_triggers: string[];
  sell_triggers: string[];
  thesis: string;
  // Dynamic trade management (new)
  trade_plan?: TradePlan;
  // Catalyst bias
  catalyst_bias?: CatalystBias;
  // D-44: G14 — earnings binary risk
  binary_risk: boolean;
  earnings_date: string | null;
}

export interface TradePlan {
  scale_in: ScaleInStep[];
  scale_out: ScaleOutStep[];
  trail_type: string;  // "atr" / "structure" / "percent"
  trail_value: number;
  trail_activation_r: number;
  move_to_breakeven_at_r: number;
  max_hold_days: number | null;
  max_position_pct: number;
  daily_loss_limit_pct: number;
  notes: string[];
}

export interface ScaleInStep {
  price: number;
  size_pct: number;
  reason: string;
}

export interface ScaleOutStep {
  r_multiple: number;
  size_pct: number;
  reason: string;
}

export interface CatalystBias {
  bias: string;  // bullish / bearish / neutral / slightly_positive / slightly_negative / cautious
  score: number;  // -10 to +10
  notes: string[];
}

export interface TickerAnalysisResponse {
  symbol: string;
  price: number | null;
  change_pct: number | null;
  sector: string | null;
  technical: MultiTimeframeTechnical | null;
  fundamental: FundamentalAnalysis | null;
  earnings: EarningsAnalysis | null;
  sentiment: SentimentAnalysis | null;
  risk: RiskAssessment | null;
  verdict: AnalysisVerdict;
  execution_ms: number;
  analysis_timestamp: string | null;
  data_age_hours: number | null;
  // Data source attribution
  data_sources?: {
    technical_daily: string;  // "TV Screener + yfinance"
    technical_weekly: string; // "yfinance 2y weekly"
    fundamental: string;      // "yfinance info"
    sentiment: string;        // "yfinance info"
    earnings: string;         // "yfinance info"
  };
  // D-44: B3 — human-readable staleness message
  stale_warning: string | null;
  // D-44: B3 — list of data quality warnings (e.g. "Only 125 daily bars")
  data_quality_warnings: string[];
}

export interface TickerAnalysisRequest {
  symbol: string;
  timeframe?: string;
  tv_data?: Record<string, unknown> | null;
  regime?: string | null;
}

// ── Yahoo Finance Supplemental Types ──

export interface OptionsChainResponse {
  symbol: string;
  expiry: string;
  spot: number;
  calls: OptionsContract[];
  puts: OptionsContract[];
  ivRank: number;
  maxPain: number;
  gammaExposure: number;
  putCallRatio: number;
  totalCallOI: number;
  totalPutOI: number;
  availableExpiries: string[];
}

export interface OptionsContract {
  strike: number;
  lastPrice: number;
  bid: number;
  ask: number;
  impliedVolatility: number;
  volume: number;
  openInterest: number;
  delta?: number | null;
  gamma?: number | null;
  theta?: number | null;
  vega?: number | null;
}

export interface NewsResponse {
  symbol: string;
  items: NewsItem[];
  count: number;
}

export interface NewsItem {
  title: string;
  publisher: string;
  link: string;
  timestamp: number;
  date: string | null;
  sentiment: 'positive' | 'negative' | 'neutral';
}

export interface ChartDataResponse {
  symbol: string;
  interval: string;
  range: string;
  data: ChartDataPoint[];
}

export interface ChartDataPoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

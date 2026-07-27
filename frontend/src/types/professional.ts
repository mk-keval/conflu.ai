// ── Professional Mode Types ──
// Matches backend Pydantic models in backend/app/infrastructure/professional/models.py

export interface TickerBrief {
  symbol: string;
  screenName: string;
  screenScore: number;
  confluenceScore: number;
  entry: number;
  stopLoss: number;
  targets: number[];
  verdict: string;
  conviction: number;
  livePrice: number | null;
  premarketChangePct: number | null;
  educationHints: Record<string, string>;
}

export interface ScreenSection {
  screenName: string;
  screenLabel: string;
  regimeMatchScore: number;
  tickers: TickerBrief[];
}

export interface MarketInternals {
  vix: number | null;
  advanceDeclineRatio: number | null;
  dollarIndex: number | null;
  sp500Futures: number | null;
  nasdaqFutures: number | null;
}

export interface SectorRotationBrief {
  leadingSectors: string[];
  laggingSectors: string[];
  regimeAlignment: string;
}

export interface SectorBrief {
  symbol: string;
  name: string;
  changePct: number;
  rsRank: number;
}

export interface MorningBriefResponse {
  date: string;
  regime: string;
  regimeDescription: string;
  marketInternals: MarketInternals;
  sectorRotation: SectorRotationBrief;
  sectors: SectorBrief[];
  screenSections: ScreenSection[];
  generatedAt: string;
}

export interface SimplifiedVerdictResponse {
  symbol: string;
  action: string;
  conviction: number;
  verdictSummary: string;
  keyMetrics: Record<string, unknown>;
  entryZone: string;
  stopLoss: number;
  targets: number[];
  positionSize: PositionSizeInfo | null;
  education: EducationItem[];
}

export interface PositionSizeInfo {
  shares: number;
  amount: number;
  riskPct: number;
  cappedBy: 'position' | 'sector' | 'kelly';
}

export interface EducationItem {
  metric: string;
  explanation: string;
}

export interface EducationResponse {
  metric: string;
  symbol: string | null;
  plainEnglish: string;
  valueContext: string | null;
  actionable: string | null;
  source: 'template' | 'llm' | 'combined';
  cached: boolean;
}

export interface PositionSizeRequest {
  symbol: string;
  accountEquity: number;
  entry: number;
  stopLoss: number;
  conviction: 'high' | 'medium' | 'low';
  maxPositionPct?: number;
  maxSectorPct?: number;
  riskPerTradePct?: number;
}

export interface PositionSizeResponse {
  positionSize: number;
  shares: number;
  riskAmount: number;
  riskPct: number;
  convictionMultiplier: number;
  cappedBy: 'position' | 'sector' | 'kelly';
}

export interface AlertPreferences {
  morningBrief: boolean;
  stopHitEmail: boolean;
  stopHitPush: boolean;
  targetHitPush: boolean;
  earningsEmail: boolean;
  regimeChangeEmail: boolean;
  regimeChangePush: boolean;
  weeklyReview: boolean;
}

export interface InAppAlert {
  id: string;
  type: 'stop_hit' | 'target_hit' | 'earnings' | 'regime_change' | 'morning_brief' | 'weekly_review';
  symbol: string | null;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

export interface WatchlistAnalyzeItem {
  symbol: string;
  verdict: string;
  conviction: number;
  positionSize: PositionSizeInfo | null;
}

export interface WatchlistAnalyzeResponse {
  items: WatchlistAnalyzeItem[];
}

export interface ProModeSettings {
  enabled: boolean;
  startDate: string | null;
  daysActive: number;
  unlockedFeatures: string[];
  accountSize: number;
  riskTolerance: 'conservative' | 'moderate' | 'aggressive';
  alertPreferences: AlertPreferences;
}

export type VerdictAction = 'STRONG_BUY' | 'BUY' | 'WATCH' | 'AVOID';

export type RiskTolerance = 'conservative' | 'moderate' | 'aggressive';

export type ConvictionLevel = 'high' | 'medium' | 'low';

/** Feature unlock schedule (days from start) */
export const UNLOCK_SCHEDULE: Record<string, number> = {
  'morning-brief': 1,
  'one-click-verdict': 1,
  'watchlist-builder': 1,
  'screen-selector': 14,
  'deep-analysis': 30,
  'backtest-engine': 60,
  'portfolio-analytics': 60,
  'charts-full': 90,
} as const;

/** Get features unlocked by day N */
export function getUnlockedFeatures(daysActive: number): string[] {
  return Object.entries(UNLOCK_SCHEDULE)
    .filter(([_, day]) => daysActive >= day)
    .map(([feature]) => feature);
}

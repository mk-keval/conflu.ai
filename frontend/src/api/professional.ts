import { apiGet, apiPost, apiPut } from './client';
import type {
  MorningBriefResponse,
  SimplifiedVerdictResponse,
  EducationResponse,
  PositionSizeResponse,
  PositionSizeRequest,
  PositionSizeInfo,
  WatchlistAnalyzeResponse,
  AlertPreferences,
  InAppAlert,
} from '@/types/professional';

// ── Raw backend shapes (snake_case, as returned by the API) ──
// Mirrors backend/app/infrastructure/professional/models.py

interface RawTickerBrief {
  symbol: string;
  screen_name: string;
  screen_score: number;
  confluence_score: number;
  entry: number;
  stop_loss: number;
  targets: number[];
  verdict: string;
  conviction: number;
  live_price: number | null;
  premarket_change_pct: number | null;
  education_hints: Record<string, string>;
}

interface RawScreenSection {
  screen_name: string;
  screen_label: string;
  regime_match_score: number;
  tickers: RawTickerBrief[];
}

interface RawMarketInternals {
  vix: number | null;
  advance_decline_ratio: number | null;
  dollar_index: number | null;
  sp500_futures: number | null;
  nasdaq_futures: number | null;
}

interface RawSectorRotationSummary {
  leading_sectors: string[];
  lagging_sectors: string[];
  regime_alignment: string;
}

interface RawSectorBrief {
  symbol: string;
  name: string;
  change_pct: number;
  rs_rank: number;
}

interface RawMorningBrief {
  date: string;
  regime: string;
  regime_description: string;
  market_internals: RawMarketInternals;
  sector_rotation: RawSectorRotationSummary;
  sectors: RawSectorBrief[];
  screen_sections: RawScreenSection[];
  generated_at: string;
}

/** Verdict/watchlist position size — backend sends suggested pct + stop pct only. */
interface RawVerdictPositionSize {
  suggested_position_pct?: number;
  stop_pct?: number;
}

interface RawSimplifiedVerdict {
  symbol: string;
  action: string;
  conviction: number;
  verdict_summary: string;
  key_metrics: Record<string, unknown>;
  entry_zone: string;
  stop_loss: number;
  targets: number[];
  position_size: RawVerdictPositionSize | null;
  max_hold_days: number | null;
  education: Array<{ metric: string; explanation: string }>;
}

interface RawEducationResponse {
  metric: string;
  symbol: string | null;
  plain_english: string;
  value_context: string | null;
  actionable: string | null;
  source: string;
  cached: boolean;
}

interface RawWatchlistItem {
  symbol: string;
  verdict: string;
  conviction: number;
  position_size: RawVerdictPositionSize | null;
}

interface RawWatchlistAnalyzeResponse {
  items: RawWatchlistItem[];
}

interface RawPositionSizeResponse {
  position_size: number;
  shares: number;
  risk_amount: number;
  risk_pct: number;
  conviction_multiplier: number;
  capped_by: string;
}

interface RawAlertPreferences {
  email_morning_brief: boolean;
  email_stop_hit: boolean;
  push_stop_hit: boolean;
  push_target_hit: boolean;
  email_earnings_alert: boolean;
  email_regime_change: boolean;
  email_weekly_review: boolean;
}

interface RawInAppAlert {
  id: string;
  type: string;
  symbol?: string | null;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

// ── Mappers (snake_case → camelCase) ──

function mapTickerBrief(raw: RawTickerBrief) {
  return {
    symbol: raw.symbol,
    screenName: raw.screen_name,
    screenScore: raw.screen_score,
    confluenceScore: raw.confluence_score,
    entry: raw.entry,
    stopLoss: raw.stop_loss,
    targets: raw.targets,
    verdict: raw.verdict,
    conviction: raw.conviction,
    livePrice: raw.live_price,
    premarketChangePct: raw.premarket_change_pct,
    educationHints: raw.education_hints,
  };
}

function mapScreenSection(raw: RawScreenSection) {
  return {
    screenName: raw.screen_name,
    screenLabel: raw.screen_label,
    regimeMatchScore: raw.regime_match_score,
    tickers: raw.tickers.map(mapTickerBrief),
  };
}

function mapMorningBrief(raw: RawMorningBrief): MorningBriefResponse {
  return {
    date: raw.date ?? '',
    regime: raw.regime ?? '',
    regimeDescription: raw.regime_description ?? '',
    marketInternals: {
      vix: raw.market_internals?.vix ?? null,
      advanceDeclineRatio: raw.market_internals?.advance_decline_ratio ?? null,
      dollarIndex: raw.market_internals?.dollar_index ?? null,
      sp500Futures: raw.market_internals?.sp500_futures ?? null,
      nasdaqFutures: raw.market_internals?.nasdaq_futures ?? null,
    },
    sectorRotation: {
      leadingSectors: raw.sector_rotation?.leading_sectors ?? [],
      laggingSectors: raw.sector_rotation?.lagging_sectors ?? [],
      regimeAlignment: raw.sector_rotation?.regime_alignment ?? '',
    },
    sectors: (raw.sectors ?? []).map((s) => ({
      symbol: s.symbol ?? '',
      name: s.name ?? '',
      changePct: s.change_pct ?? 0,
      rsRank: s.rs_rank ?? 0,
    })),
    screenSections: (raw.screen_sections ?? []).map(mapScreenSection),
    generatedAt: raw.generated_at ?? '',
  };
}

function mapSimplifiedVerdict(
  raw: RawSimplifiedVerdict
): SimplifiedVerdictResponse {
  return {
    symbol: raw.symbol ?? '',
    action: raw.action ?? 'WATCH',
    conviction: raw.conviction ?? 0,
    verdictSummary: raw.verdict_summary ?? '',
    keyMetrics: raw.key_metrics ?? {},
    entryZone: raw.entry_zone ?? '',
    stopLoss: raw.stop_loss ?? 0,
    targets: raw.targets ?? [],
    maxHoldDays: raw.max_hold_days ?? null,
    // Backend sends suggested_position_pct/stop_pct on the verdict; surface the
    // suggested risk % (previously hardcoded to 0, hiding the real sizing).
    positionSize: raw.position_size
      ? {
          shares: 0,
          amount: 0,
          riskPct: raw.position_size.suggested_position_pct ?? 0,
          cappedBy: 'position' as PositionSizeInfo['cappedBy'],
        }
      : null,
    education: (raw.education ?? []).map((e) => ({
      metric: e.metric ?? '',
      explanation: e.explanation ?? '',
    })),
  };
}

function mapEducation(raw: RawEducationResponse): EducationResponse {
  return {
    metric: raw.metric,
    symbol: raw.symbol,
    plainEnglish: raw.plain_english,
    valueContext: raw.value_context,
    actionable: raw.actionable,
    source: (raw.source as EducationResponse['source']) ?? 'template',
    cached: raw.cached,
  };
}

function mapWatchlistAnalyze(
  raw: RawWatchlistAnalyzeResponse
): WatchlistAnalyzeResponse {
  return {
    items: (raw.items ?? []).map((item) => ({
      symbol: item.symbol,
      verdict: item.verdict,
      conviction: item.conviction,
      positionSize: item.position_size
        ? {
            shares: 0,
            amount: 0,
            riskPct: item.position_size.suggested_position_pct ?? 0,
            cappedBy: 'position' as PositionSizeInfo['cappedBy'],
          }
        : null,
    })),
  };
}

function mapPositionSizeResponse(
  raw: RawPositionSizeResponse
): PositionSizeResponse {
  return {
    positionSize: raw.position_size,
    shares: raw.shares,
    riskAmount: raw.risk_amount,
    riskPct: raw.risk_pct,
    convictionMultiplier: raw.conviction_multiplier,
    cappedBy: (raw.capped_by as PositionSizeResponse['cappedBy']) ?? 'position',
  };
}

function mapAlertPreferences(raw: RawAlertPreferences): AlertPreferences {
  return {
    morningBrief: raw.email_morning_brief,
    stopHitEmail: raw.email_stop_hit,
    stopHitPush: raw.push_stop_hit,
    targetHitPush: raw.push_target_hit,
    earningsEmail: raw.email_earnings_alert,
    regimeChangeEmail: raw.email_regime_change,
    // Backend has no push_regime_change field — default to disabled.
    regimeChangePush: false,
    weeklyReview: raw.email_weekly_review,
  };
}

function mapInAppAlert(raw: RawInAppAlert): InAppAlert {
  return {
    id: raw.id,
    type: (raw.type as InAppAlert['type']) ?? 'morning_brief',
    symbol: raw.symbol ?? null,
    title: raw.title,
    message: raw.message,
    timestamp: raw.timestamp,
    read: raw.read,
  };
}

// ── Professional Mode API ──

/** Get the complete morning brief (regime, market internals, sector rotation, top 9 picks).
 *  Unwraps ApiResponse envelope and maps snake_case to camelCase. */
export async function fetchMorningBrief(): Promise<MorningBriefResponse> {
  const raw = await apiGet<RawMorningBrief>(
    '/api/v1/professional/morning-brief'
  );
  return mapMorningBrief(raw);
}

/** Get simplified verdict for a single ticker.
 *  Unwraps ApiResponse envelope and maps snake_case to camelCase. */
export async function fetchSimplifiedVerdict(
  symbol: string
): Promise<SimplifiedVerdictResponse> {
  const raw = await apiGet<RawSimplifiedVerdict>(
    `/api/v1/professional/verdict/${symbol}`
  );
  return mapSimplifiedVerdict(raw);
}

/** Get plain-English explanation for a metric. */
export async function explainMetric(
  metric: string,
  symbol?: string
): Promise<EducationResponse> {
  const params = new URLSearchParams();
  if (symbol) params.set('symbol', symbol);
  const raw = await apiGet<RawEducationResponse>(
    `/api/v1/professional/education/${metric}?${params.toString()}`
  );
  return mapEducation(raw);
}

/** Batch analyze a watchlist. */
export async function analyzeWatchlist(
  symbols: string[]
): Promise<WatchlistAnalyzeResponse> {
  const raw = await apiPost<RawWatchlistAnalyzeResponse>(
    '/api/v1/professional/watchlist/analyze',
    { symbols }
  );
  return mapWatchlistAnalyze(raw);
}

/** Calculate position size from trade parameters. */
export async function calculatePositionSize(
  params: PositionSizeRequest
): Promise<PositionSizeResponse> {
  const queryParams = new URLSearchParams({
    symbol: params.symbol,
    account_equity: String(params.accountEquity),
    entry: String(params.entry),
    stop_loss: String(params.stopLoss),
    conviction: params.conviction,
  });
  if (params.maxPositionPct)
    queryParams.set('max_position_pct', String(params.maxPositionPct));
  if (params.maxSectorPct)
    queryParams.set('max_sector_pct', String(params.maxSectorPct));
  if (params.riskPerTradePct)
    queryParams.set('risk_per_trade_pct', String(params.riskPerTradePct));
  const raw = await apiGet<RawPositionSizeResponse>(
    `/api/v1/professional/position-size?${queryParams.toString()}`
  );
  return mapPositionSizeResponse(raw);
}

/** Get alert preferences. */
export async function fetchAlertPreferences(): Promise<AlertPreferences> {
  const raw = await apiGet<RawAlertPreferences>(
    '/api/v1/professional/alerts/preferences'
  );
  return mapAlertPreferences(raw);
}

/** Update alert preferences. */
export async function updateAlertPreferences(
  prefs: Partial<AlertPreferences>
): Promise<AlertPreferences> {
  const raw = await apiPut<RawAlertPreferences>(
    '/api/v1/professional/alerts/preferences',
    prefs
  );
  return mapAlertPreferences(raw);
}

/** Get recent in-app alerts. */
export async function fetchAlerts(
  limit?: number,
  unreadOnly?: boolean
): Promise<InAppAlert[]> {
  const params = new URLSearchParams();
  if (limit) params.set('limit', String(limit));
  if (unreadOnly) params.set('unread_only', 'true');
  const raw = await apiGet<RawInAppAlert[]>(
    `/api/v1/professional/alerts?${params.toString()}`
  );
  return raw.map(mapInAppAlert);
}

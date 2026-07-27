import apiClient from './client';
import type {
  MorningBriefResponse,
  SimplifiedVerdictResponse,
  EducationResponse,
  PositionSizeResponse,
  PositionSizeRequest,
  WatchlistAnalyzeResponse,
  AlertPreferences,
  InAppAlert,
} from '@/types/professional';

// ── Professional Mode API ──

/** Get the complete morning brief (regime, market internals, sector rotation, top 9 picks). */
export async function fetchMorningBrief(): Promise<MorningBriefResponse> {
  return apiClient.get('/api/v1/professional/morning-brief') as Promise<MorningBriefResponse>;
}

/** Get simplified verdict for a single ticker. */
export async function fetchSimplifiedVerdict(symbol: string): Promise<SimplifiedVerdictResponse> {
  return apiClient.get(`/api/v1/professional/verdict/${symbol}`) as Promise<SimplifiedVerdictResponse>;
}

/** Get plain-English explanation for a metric. */
export async function explainMetric(metric: string, symbol?: string): Promise<EducationResponse> {
  const params = new URLSearchParams();
  if (symbol) params.set('symbol', symbol);
  return apiClient.get(`/api/v1/professional/education/${metric}?${params.toString()}`) as Promise<EducationResponse>;
}

/** Batch analyze a watchlist. */
export async function analyzeWatchlist(symbols: string[]): Promise<WatchlistAnalyzeResponse> {
  return apiClient.post('/api/v1/professional/watchlist/analyze', { symbols }) as Promise<WatchlistAnalyzeResponse>;
}

/** Calculate position size from trade parameters. */
export async function calculatePositionSize(
  params: PositionSizeRequest,
): Promise<PositionSizeResponse> {
  const queryParams = new URLSearchParams({
    symbol: params.symbol,
    account_equity: String(params.accountEquity),
    entry: String(params.entry),
    stop_loss: String(params.stopLoss),
    conviction: params.conviction,
  });
  if (params.maxPositionPct) queryParams.set('max_position_pct', String(params.maxPositionPct));
  if (params.maxSectorPct) queryParams.set('max_sector_pct', String(params.maxSectorPct));
  if (params.riskPerTradePct) queryParams.set('risk_per_trade_pct', String(params.riskPerTradePct));
  return apiClient.get(`/api/v1/professional/position-size?${queryParams.toString()}`) as Promise<PositionSizeResponse>;
}

/** Get alert preferences. */
export async function fetchAlertPreferences(): Promise<AlertPreferences> {
  return apiClient.get('/api/v1/professional/alerts/preferences') as Promise<AlertPreferences>;
}

/** Update alert preferences. */
export async function updateAlertPreferences(prefs: Partial<AlertPreferences>): Promise<AlertPreferences> {
  return apiClient.put('/api/v1/professional/alerts/preferences', prefs) as Promise<AlertPreferences>;
}

/** Get recent in-app alerts. */
export async function fetchAlerts(limit?: number, unreadOnly?: boolean): Promise<InAppAlert[]> {
  const params = new URLSearchParams();
  if (limit) params.set('limit', String(limit));
  if (unreadOnly) params.set('unread_only', 'true');
  return apiClient.get(`/api/v1/professional/alerts?${params.toString()}`) as Promise<InAppAlert[]>;
}

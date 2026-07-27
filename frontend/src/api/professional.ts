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

/** Get the complete morning brief (regime, market internals, sector rotation, top 9 picks).
 *  Unwraps ApiResponse envelope and maps snake_case to camelCase. */
export async function fetchMorningBrief(): Promise<MorningBriefResponse> {
  const res: any = await apiClient.get('/api/v1/professional/morning-brief');
  const d = res?.data ?? res ?? {};
  const source = d.regime !== undefined ? d : res;
  return {
    date: source.date ?? '',
    regime: source.regime ?? '',
    regimeDescription: source.regime_description ?? '',
    marketInternals: {
      vix: source.market_internals?.vix ?? null,
      advanceDeclineRatio: source.market_internals?.advance_decline_ratio ?? null,
      dollarIndex: source.market_internals?.dollar_index ?? null,
      sp500Futures: source.market_internals?.sp500_futures ?? null,
      nasdaqFutures: source.market_internals?.nasdaq_futures ?? null,
    },
    sectorRotation: {
      leadingSectors: source.sector_rotation?.leading_sectors ?? [],
      laggingSectors: source.sector_rotation?.lagging_sectors ?? [],
      regimeAlignment: source.sector_rotation?.regime_alignment ?? '',
    },
    sectors: (source.sectors ?? []).map((s: any) => ({
      symbol: s.symbol ?? '',
      name: s.name ?? '',
      changePct: s.change_pct ?? 0,
      rsRank: s.rs_rank ?? 0,
    })),
    screenSections: (source.screen_sections ?? []).map((sec: any) => ({
      screenName: sec.screen_name ?? '',
      screenLabel: sec.screen_label ?? '',
      regimeMatchScore: sec.regime_match_score ?? 0,
      tickers: (sec.tickers ?? []).map((t: any) => ({
        symbol: t.symbol ?? '',
        screenName: t.screen_name ?? '',
        screenScore: t.screen_score ?? 0,
        confluenceScore: t.confluence_score ?? 0,
        entry: t.entry ?? 0,
        stopLoss: t.stop_loss ?? 0,
        targets: t.targets ?? [],
        verdict: t.verdict ?? '',
        conviction: t.conviction ?? 0,
        livePrice: t.live_price ?? null,
        premarketChangePct: t.premarket_change_pct ?? null,
        educationHints: t.education_hints ?? {},
      })),
    })),
    generatedAt: source.generated_at ?? '',
  } as MorningBriefResponse;
}

/** Get simplified verdict for a single ticker.
 *  Unwraps ApiResponse envelope and maps snake_case to camelCase. */
export async function fetchSimplifiedVerdict(symbol: string): Promise<SimplifiedVerdictResponse> {
  const res: any = await apiClient.get(`/api/v1/professional/verdict/${symbol}`);
  const d = res?.data ?? res ?? {};
  // Handle both ApiResponse<T> envelope { data: {...} } and direct response
  const source = d.key_metrics !== undefined ? d : res;
  return {
    symbol: source.symbol ?? '',
    action: source.action ?? 'WATCH',
    conviction: source.conviction ?? 0,
    verdictSummary: source.verdict_summary ?? '',
    keyMetrics: source.key_metrics ?? {},
    entryZone: source.entry_zone ?? '',
    stopLoss: source.stop_loss ?? 0,
    targets: source.targets ?? [],
    positionSize: source.position_size ? {
      shares: source.position_size.shares ?? 0,
      amount: source.position_size.amount ?? 0,
      riskPct: source.position_size.risk_pct ?? 0,
      cappedBy: source.position_size.capped_by ?? '',
    } : null,
    education: (source.education ?? []).map((e: any) => ({
      metric: e.metric ?? '',
      explanation: e.explanation ?? '',
    })),
  } as SimplifiedVerdictResponse;
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

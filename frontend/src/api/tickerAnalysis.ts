import { apiGet, apiPost } from './client';
import type {
  TickerAnalysisRequest,
  TickerAnalysisResponse,
  OptionsChainResponse,
  NewsResponse,
  ChartDataResponse,
} from '@/types/tickerAnalysis';

// ── Existing analysis endpoint ──

export async function fetchTickerAnalysis(
  symbol: string,
  request?: Partial<TickerAnalysisRequest>,
): Promise<TickerAnalysisResponse> {
  const body: TickerAnalysisRequest = {
    symbol,
    timeframe: request?.timeframe ?? '1D',
    tv_data: request?.tv_data ?? null,
    regime: request?.regime ?? null,
  };

  return apiPost<TickerAnalysisResponse>(`/api/v1/ticker/${symbol}/analyze`, body);
}

// ── New Yahoo Finance supplemental endpoints ──

export async function fetchOptionsChain(
  symbol: string,
  expiry?: string,
): Promise<OptionsChainResponse> {
  const params = expiry ? `?expiry=${expiry}` : '';
  return apiGet<OptionsChainResponse>(`/api/v1/ticker/${symbol}/options${params}`);
}

export async function fetchNews(
  symbol: string,
  limit = 20,
): Promise<NewsResponse> {
  return apiGet<NewsResponse>(`/api/v1/ticker/${symbol}/news?limit=${limit}`);
}

export async function fetchChartData(
  symbol: string,
  interval = '5m',
  range = '1d',
): Promise<ChartDataResponse> {
  return apiGet<ChartDataResponse>(
    `/api/v1/ticker/${symbol}/chart?interval=${interval}&range=${range}`,
  );
}

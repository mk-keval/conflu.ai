import apiClient from './client';
import type { ApiResponse } from '@/types/api';
import type { TickerAnalysisRequest, TickerAnalysisResponse } from '@/types/tickerAnalysis';

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

  const response = await apiClient.post<ApiResponse<TickerAnalysisResponse>>(
    `/api/v1/ticker/${symbol}/analyze`,
    body,
  ) as unknown as ApiResponse<TickerAnalysisResponse>;
  return response.data;
}

// ── New Yahoo Finance supplemental endpoints ──

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

export async function fetchOptionsChain(
  symbol: string,
  expiry?: string,
): Promise<OptionsChainResponse> {
  const params = expiry ? `?expiry=${expiry}` : '';
  const response = await apiClient.get<ApiResponse<OptionsChainResponse>>(
    `/api/v1/ticker/${symbol}/options${params}`,
  ) as unknown as ApiResponse<OptionsChainResponse>;
  return response.data;
}

export async function fetchNews(
  symbol: string,
  limit = 20,
): Promise<NewsResponse> {
  const response = await apiClient.get<ApiResponse<NewsResponse>>(
    `/api/v1/ticker/${symbol}/news?limit=${limit}`,
  ) as unknown as ApiResponse<NewsResponse>;
  return response.data;
}

export async function fetchChartData(
  symbol: string,
  interval = '5m',
  range = '1d',
): Promise<ChartDataResponse> {
  const response = await apiClient.get<ApiResponse<ChartDataResponse>>(
    `/api/v1/ticker/${symbol}/chart?interval=${interval}&range=${range}`,
  ) as unknown as ApiResponse<ChartDataResponse>;
  return response.data;
}

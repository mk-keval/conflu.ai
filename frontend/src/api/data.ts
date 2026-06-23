import apiClient from './client';
import type { OHLCVCandle, OHLCVResponse, IndicatorResponse } from '@/types/data';
import type { ApiResponse } from '@/types/api';

export async function fetchOHLCV(
  symbol: string,
  timeframe: string,
  start?: string,
  end?: string,
  limit?: number
): Promise<OHLCVCandle[]> {
  const params = new URLSearchParams({ timeframe });
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  if (limit) params.set('limit', String(limit));

  // The apiClient interceptor returns the full response body (ApiResponse<OHLCVResponse>)
  const response = await apiClient.get<ApiResponse<OHLCVResponse>>(
    `/api/v1/data/${symbol}?${params.toString()}`
  ) as unknown as ApiResponse<OHLCVResponse>;
  return response.data.candles;
}

export async function fetchIndicators(
  symbol: string,
  timeframe: string,
  indicators?: string,
  limit?: number
): Promise<IndicatorResponse> {
  const params = new URLSearchParams({ timeframe });
  if (indicators) params.set('indicators', indicators);
  if (limit) params.set('limit', String(limit));

  const response = await apiClient.get<ApiResponse<IndicatorResponse>>(
    `/api/v1/data/indicators/${symbol}?${params.toString()}`
  ) as unknown as ApiResponse<IndicatorResponse>;
  return response.data;
}

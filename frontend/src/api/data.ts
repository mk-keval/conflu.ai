import { apiGet } from './client';
import type { OHLCVCandle, OHLCVResponse, IndicatorResponse } from '@/types/data';

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

  const response = await apiGet<OHLCVResponse>(
    `/api/v1/data/${symbol}?${params.toString()}`
  );
  return response.candles;
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

  return apiGet<IndicatorResponse>(
    `/api/v1/data/indicators/${symbol}?${params.toString()}`
  );
}

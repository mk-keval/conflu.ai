import apiClient from './client';
import type { ApiResponse } from '@/types/api';
import type { TickerAnalysisRequest, TickerAnalysisResponse } from '@/types/tickerAnalysis';

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

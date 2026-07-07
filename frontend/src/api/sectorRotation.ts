import apiClient from './client';
import type { ApiResponse } from '@/types/api';
import type { MarketRegimeResponse, SectorRotationResponse, SectorDetail, RotationHistoryPoint } from '@/types/sector';

export async function fetchSectorRotation(): Promise<SectorRotationResponse> {
  const response = await apiClient.get<ApiResponse<SectorRotationResponse>>(
    '/api/v1/sector-rotation'
  ) as unknown as ApiResponse<SectorRotationResponse>;
  return response.data;
}

export async function fetchSectorDetail(symbol: string): Promise<SectorDetail | null> {
  const response = await apiClient.get<ApiResponse<SectorDetail | null>>(
    `/api/v1/sector-rotation/${symbol}`
  ) as unknown as ApiResponse<SectorDetail | null>;
  return response.data;
}

export async function fetchRotationHistory(): Promise<RotationHistoryPoint[]> {
  const response = await apiClient.get<ApiResponse<RotationHistoryPoint[]>>(
    '/api/v1/sector-rotation/history'
  ) as unknown as ApiResponse<RotationHistoryPoint[]>;
  return response.data;
}

export async function fetchMarketRegime(): Promise<MarketRegimeResponse> {
  const response = await apiClient.get<ApiResponse<MarketRegimeResponse>>(
    '/api/v1/market/regime'
  ) as unknown as ApiResponse<MarketRegimeResponse>;
  return response.data;
}

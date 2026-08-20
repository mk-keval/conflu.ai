import { apiGet } from './client';
import type { MarketRegimeResponse, SectorRotationResponse, SectorDetail, RotationHistoryPoint } from '@/types/sector';

export async function fetchSectorRotation(): Promise<SectorRotationResponse> {
  return apiGet<SectorRotationResponse>('/api/v1/sector-rotation');
}

export async function fetchSectorDetail(symbol: string): Promise<SectorDetail | null> {
  return apiGet<SectorDetail | null>(`/api/v1/sector-rotation/${symbol}`);
}

export async function fetchRotationHistory(): Promise<RotationHistoryPoint[]> {
  return apiGet<RotationHistoryPoint[]>('/api/v1/sector-rotation/history');
}

export async function fetchMarketRegime(): Promise<MarketRegimeResponse> {
  return apiGet<MarketRegimeResponse>('/api/v1/market/regime');
}

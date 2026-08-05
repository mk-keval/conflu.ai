import apiClient from './client';
import type { ApiResponse } from '@/types/api';

export interface MarketEvent {
  date: string;
  title: string;
  description: string;
  days_until: number;
  importance: 'high' | 'medium' | 'low';
}

export interface MarketEventsResponse {
  events: MarketEvent[];
  count: number;
}

export interface MarketNarrativeResponse {
  narrative: string;
  generated_at: string;
}

export async function fetchMarketEvents(): Promise<MarketEventsResponse> {
  const response = await apiClient.get<ApiResponse<MarketEventsResponse>>(
    '/api/v1/market/events'
  ) as unknown as ApiResponse<MarketEventsResponse>;
  return response.data;
}

export async function fetchMarketNarrative(): Promise<MarketNarrativeResponse> {
  const response = await apiClient.get<ApiResponse<MarketNarrativeResponse>>(
    '/api/v1/market/narrative'
  ) as unknown as ApiResponse<MarketNarrativeResponse>;
  return response.data;
}

import { apiGet } from './client';

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
  return apiGet<MarketEventsResponse>('/api/v1/market/events');
}

export async function fetchMarketNarrative(): Promise<MarketNarrativeResponse> {
  return apiGet<MarketNarrativeResponse>('/api/v1/market/narrative');
}

import apiClient from './client';
import type { ScreenSymbolResult, SymbolInfo } from '@/types/screener';

export async function fetchScreen(
  config: string,
  symbols?: string[],
  timeframes?: string[],
  exportFormat?: 'json' | 'csv'
): Promise<ScreenSymbolResult[]> {
  const response = await apiClient.post<ScreenSymbolResult[]>('/api/v1/screen', {
    config,
    symbols,
    timeframes,
    export_format: exportFormat,
  });
  return response.data;
}

export async function fetchSymbols(
  assetClass?: string,
  activeOnly?: boolean
): Promise<SymbolInfo[]> {
  const params = new URLSearchParams();
  if (assetClass) params.set('asset_class', assetClass);
  if (activeOnly !== undefined) params.set('active_only', String(activeOnly));

  const response = await apiClient.get<SymbolInfo[]>(
    `/api/v1/data/symbols?${params.toString()}`
  );
  return response.data;
}

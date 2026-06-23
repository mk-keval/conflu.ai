import apiClient from './client';
import type { ScreenSymbolResult, SymbolInfo } from '@/types/screener';
import type { FilterRuleConfig } from '@/lib/constants';

export interface CustomScreenConfig {
  name: string;
  description: string;
  asset_classes: string[];
  timeframes: string[];
  filters: FilterRuleConfig[];
}

type FilterOperator = 'gt' | 'lt' | 'eq' | 'crosses_above' | 'crosses_below';

export interface ApiFilterRule {
  category: string;
  indicator: string;
  params: Record<string, unknown>;
  operator: FilterOperator;
  timeframe: string;
  negate: boolean;
  compare_timeframe?: string;
}

export interface ApiScreenConfig {
  name: string;
  description: string;
  asset_classes: string[];
  timeframes: string[];
  filters: ApiFilterRule[];
}

export type ScreenConfigInput = string | CustomScreenConfig;

const convertToApiConfig = (config: CustomScreenConfig) => ({
  name: config.name,
  description: config.description,
  asset_classes: config.asset_classes,
  timeframes: config.timeframes,
  filters: config.filters.map((f) => ({
    category: f.category,
    indicator: f.indicator,
    params: Object.fromEntries(
      Object.entries(f.params).map(([k, p]) => [k, p.defaultValue])
    ),
    operator: f.operator,
    timeframe: f.timeframe,
    negate: f.negate,
    compare_timeframe: f.compareTimeframe,
  })),
});

export async function fetchScreen(
  config: ScreenConfigInput,
  symbols?: string[],
  timeframes?: string[],
  exportFormat?: 'json' | 'csv'
): Promise<ScreenSymbolResult[]> {
  const apiConfig = typeof config === 'string' ? config : convertToApiConfig(config);
  const response = await apiClient.post<ScreenSymbolResult[]>('/api/v1/screen', {
    config: apiConfig,
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

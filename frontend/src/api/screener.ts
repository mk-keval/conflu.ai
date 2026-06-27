import apiClient from './client';
import type {
  TVScreenResponse,
  TVTemplate,
  TVDeepAnalysisResponse,
  TVDeepAnalysisRequest,
  SymbolInfo,
} from '@/types/screener';

// ── TV Screener API (v1) ──

/** Run a screen by template name or inline config. */
export async function fetchScreenTV(
  config: string | Record<string, unknown>,
  limit?: number,
): Promise<TVScreenResponse> {
  return apiClient.post('/api/v1/screen/tv', { config, limit }) as Promise<TVScreenResponse>;
}

/** Multi-timeframe screen. */
export async function fetchScreenTVMultiTF(
  config: string | Record<string, unknown>,
): Promise<TVScreenResponse> {
  return apiClient.post('/api/v1/screen/tv/multi-tf', { config }) as Promise<TVScreenResponse>;
}

/** Deep analysis for a single ticker. */
export async function fetchDeepAnalysis(
  req: TVDeepAnalysisRequest,
): Promise<TVDeepAnalysisResponse> {
  return apiClient.post('/api/v1/screen/tv/analyze', req) as Promise<TVDeepAnalysisResponse>;
}

/** List available screen templates. */
export async function fetchTVTemplates(): Promise<TVTemplate[]> {
  return apiClient.get('/api/v1/screen/tv/templates') as Promise<TVTemplate[]>;
}

/** Load a specific template by name. */
export async function fetchTVTemplate(name: string): Promise<Record<string, unknown>> {
  return apiClient.get(`/api/v1/screen/tv/templates/${name}`) as Promise<Record<string, unknown>>;
}

// ── Legacy API (old architecture) ──

export async function fetchSymbols(
  assetClass?: string,
  activeOnly?: boolean
): Promise<SymbolInfo[]> {
  const params = new URLSearchParams();
  if (assetClass) params.set('asset_class', assetClass);
  if (activeOnly !== undefined) params.set('active_only', String(activeOnly));
  return apiClient.get(`/api/v1/data/symbols?${params.toString()}`) as Promise<SymbolInfo[]>;
}

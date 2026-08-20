import { apiGet, apiPost } from './client';
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
  return apiPost<TVScreenResponse>('/api/v1/screen/tv', { config, limit });
}

/** Multi-timeframe screen. */
export async function fetchScreenTVMultiTF(
  config: string | Record<string, unknown>,
): Promise<TVScreenResponse> {
  return apiPost<TVScreenResponse>('/api/v1/screen/tv/multi-tf', { config });
}

/** Deep analysis for a single ticker. */
export async function fetchDeepAnalysis(
  req: TVDeepAnalysisRequest,
): Promise<TVDeepAnalysisResponse> {
  return apiPost<TVDeepAnalysisResponse>('/api/v1/screen/tv/analyze', req);
}

/** List available screen templates. */
export async function fetchTVTemplates(): Promise<TVTemplate[]> {
  return apiGet<TVTemplate[]>('/api/v1/screen/tv/templates');
}

/** Load a specific template by name. */
export async function fetchTVTemplate(name: string): Promise<Record<string, unknown>> {
  return apiGet<Record<string, unknown>>(`/api/v1/screen/tv/templates/${name}`);
}

// ── Legacy API (old architecture) ──

export async function fetchSymbols(
  assetClass?: string,
  activeOnly?: boolean
): Promise<SymbolInfo[]> {
  const params = new URLSearchParams();
  if (assetClass) params.set('asset_class', assetClass);
  if (activeOnly !== undefined) params.set('active_only', String(activeOnly));
  return apiGet<SymbolInfo[]>(`/api/v1/data/symbols?${params.toString()}`);
}

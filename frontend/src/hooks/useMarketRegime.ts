import { useQuery } from '@tanstack/react-query';
import { fetchMarketRegime, fetchSectorRotation } from '@/api/sectorRotation';
import { queryKeys } from '@/lib/queryKeys';
import type { MarketRegimeResponse, SectorRotationResponse } from '@/types/sector';

const REGIME_STALE_MS = 3_600_000; // daily data changes at market close
const REGIME_REFRESH_MS = 3_600_000; // matching the old RegimeBar setInterval(1h)

/**
 * Shared market-regime query (FIX C).
 * Single source of truth for regime data — replaces the per-component
 * `['market-regime']` inline queries AND the manual setInterval polling
 * that previously lived in RegimeBar + the zustand market store.
 */
export function useMarketRegime(enabled = true) {
  return useQuery<MarketRegimeResponse>({
    queryKey: queryKeys.marketRegime(),
    queryFn: fetchMarketRegime,
    staleTime: REGIME_STALE_MS,
    refetchInterval: enabled ? REGIME_REFRESH_MS : false,
    refetchIntervalInBackground: false,
  });
}

/**
 * Shared sector-rotation query (FIX C).
 * Consolidates the 5+ `fetchSectorRotation` call sites onto one react-query
 * cache so pages share the same fetched result instead of each fetching.
 */
export function useSectorRotation(enabled = true) {
  return useQuery<SectorRotationResponse>({
    queryKey: queryKeys.sectorRotation(),
    queryFn: fetchSectorRotation,
    staleTime: 300_000, // matches the backend _SECTOR_CACHE TTL (5 min)
    enabled,
  });
}
import { create } from 'zustand';
import type { MarketRegimeResponse } from '@/types/sector';

interface MarketStore {
  regime: MarketRegimeResponse | null;
  isLoading: boolean;
  error: string | null;

  setRegime: (regime: MarketRegimeResponse | null) => void;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useMarketStore = create<MarketStore>()((set) => ({
  regime: null,
  isLoading: false,
  error: null,

  setRegime: (regime) => set({ regime }),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));

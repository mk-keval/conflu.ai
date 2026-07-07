import { create } from 'zustand';
import type { SectorPerformance, TimeframeOption } from '@/types/sector';

interface SectorRotationStore {
  sectors: SectorPerformance[];
  selectedSector: string | null;
  timeframe: TimeframeOption;
  isLoading: boolean;
  error: string | null;
  rotationPhase: string;
  marketRegime: string;

  setSectors: (sectors: SectorPerformance[]) => void;
  setSelectedSector: (symbol: string | null) => void;
  setTimeframe: (tf: TimeframeOption) => void;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setRotationPhase: (phase: string) => void;
  setMarketRegime: (regime: string) => void;
}

export const useSectorRotationStore = create<SectorRotationStore>()((set) => ({
  sectors: [],
  selectedSector: null,
  timeframe: '1D',
  isLoading: false,
  error: null,
  rotationPhase: 'unknown',
  marketRegime: 'unknown',

  setSectors: (sectors) => set({ sectors }),
  setSelectedSector: (symbol) => set({ selectedSector: symbol }),
  setTimeframe: (timeframe) => set({ timeframe }),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setRotationPhase: (phase) => set({ rotationPhase: phase }),
  setMarketRegime: (regime) => set({ marketRegime: regime }),
}));

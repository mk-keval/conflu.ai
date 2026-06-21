import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ChartStore {
  selectedSymbol: string;
  activeTimeframes: string[];
  activeIndicators: string[];
  chartLayout: 'grid' | 'stacked';
  setSymbol: (symbol: string) => void;
  toggleTimeframe: (tf: string) => void;
  toggleIndicator: (name: string) => void;
  setChartLayout: (layout: 'grid' | 'stacked') => void;
}

export const useChartStore = create<ChartStore>()(
  persist(
    (set) => ({
      selectedSymbol: 'AAPL',
      activeTimeframes: ['1D', '4H', '1H', '15m'],
      activeIndicators: ['rsi', 'macd', 'ema_20', 'bb'],
      chartLayout: 'grid',
      setSymbol: (symbol) => set({ selectedSymbol: symbol }),
      toggleTimeframe: (tf) =>
        set((state) => ({
          activeTimeframes: state.activeTimeframes.includes(tf)
            ? state.activeTimeframes.filter((t) => t !== tf)
            : [...state.activeTimeframes, tf],
        })),
      toggleIndicator: (name) =>
        set((state) => ({
          activeIndicators: state.activeIndicators.includes(name)
            ? state.activeIndicators.filter((n) => n !== name)
            : [...state.activeIndicators, name],
        })),
      setChartLayout: (layout) => set({ chartLayout: layout }),
    }),
    { name: 'chart-store' }
  )
);

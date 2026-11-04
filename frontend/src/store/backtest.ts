import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface TradeFilter {
  symbol?: string;
  dateRange?: [string, string];
  direction?: 'Long' | 'Short';
}

interface BacktestStore {
  recentRunIds: string[];
  selectedRunId: string | null;
  tradeFilter: TradeFilter;
  comparisonRunIds: string[];
  optimizationParams: Record<string, unknown>;
  addRunId: (runId: string) => void;
  setSelectedRunId: (runId: string | null) => void;
  setTradeFilter: (filter: TradeFilter) => void;
  clearTradeFilter: () => void;
  setComparisonRunIds: (ids: string[]) => void;
  addComparisonRunId: (runId: string) => void;
  removeComparisonRunId: (runId: string) => void;
  clearComparisonRunIds: () => void;
  setOptimizationParams: (params: Record<string, unknown>) => void;
}

const MAX_RECENT_RUNS = 10;

export const useBacktestStore = create<BacktestStore>()(
  persist(
    (set) => ({
      recentRunIds: [],
      selectedRunId: null,
      tradeFilter: {},
      comparisonRunIds: [],
      optimizationParams: {},
      addRunId: (runId) =>
        set((state) => ({
          recentRunIds: [
            runId,
            ...state.recentRunIds.filter((id) => id !== runId),
          ].slice(0, MAX_RECENT_RUNS),
        })),
      setSelectedRunId: (runId) => set({ selectedRunId: runId }),
      setTradeFilter: (filter) => set({ tradeFilter: filter }),
      clearTradeFilter: () => set({ tradeFilter: {} }),
      setComparisonRunIds: (ids) => set({ comparisonRunIds: ids }),
      addComparisonRunId: (runId) =>
        set((state) => ({
          comparisonRunIds: state.comparisonRunIds.includes(runId)
            ? state.comparisonRunIds
            : [...state.comparisonRunIds, runId].slice(0, 10),
        })),
      removeComparisonRunId: (runId) =>
        set((state) => ({
          comparisonRunIds: state.comparisonRunIds.filter((id) => id !== runId),
        })),
      clearComparisonRunIds: () => set({ comparisonRunIds: [] }),
      setOptimizationParams: (params) => set({ optimizationParams: params }),
    }),
    { name: 'backtest-store' }
  )
);

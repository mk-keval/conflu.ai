import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface PortfolioItem {
  symbol: string;
  addedAt: string;
}

interface PortfolioStore {
  items: PortfolioItem[];
  addSymbol: (symbol: string) => void;
  removeSymbol: (symbol: string) => void;
  hasSymbol: (symbol: string) => boolean;
  clearAll: () => void;
}

export const usePortfolioStore = create<PortfolioStore>()(
  persist(
    (set, get) => ({
      items: [],
      addSymbol: (symbol) =>
        set((state) => {
          if (state.items.some((i) => i.symbol === symbol)) return state;
          return {
            items: [...state.items, { symbol: symbol.toUpperCase(), addedAt: new Date().toISOString() }],
          };
        }),
      removeSymbol: (symbol) =>
        set((state) => ({
          items: state.items.filter((i) => i.symbol !== symbol),
        })),
      hasSymbol: (symbol) => get().items.some((i) => i.symbol === symbol),
      clearAll: () => set({ items: [] }),
    }),
    { name: 'portfolio-store' }
  )
);

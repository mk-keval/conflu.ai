import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type RiskView = 'correlation' | 'position-size' | 'beta' | 'var';
type VaRMethod = 'historical' | 'parametric' | 'monte_carlo';

interface RiskStore {
  selectedSymbols: string[];
  activeView: RiskView;
  varConfidence: number;
  varMethod: VaRMethod;
  setSymbols: (symbols: string[]) => void;
  setActiveView: (view: RiskView) => void;
  setVarConfidence: (confidence: number) => void;
  setVarMethod: (method: VaRMethod) => void;
}

export const useRiskStore = create<RiskStore>()(
  persist(
    (set) => ({
      selectedSymbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
      activeView: 'correlation',
      varConfidence: 0.95,
      varMethod: 'historical',
      setSymbols: (symbols) => set({ selectedSymbols: symbols }),
      setActiveView: (view) => set({ activeView: view }),
      setVarConfidence: (confidence) => set({ varConfidence: confidence }),
      setVarMethod: (method) => set({ varMethod: method }),
    }),
    { name: 'risk-store' }
  )
);

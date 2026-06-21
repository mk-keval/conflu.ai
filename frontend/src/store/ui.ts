import { create } from 'zustand';

type AppView = 'screener' | 'charts' | 'backtest' | 'risk';
type Theme = 'dark' | 'light';

interface UIStore {
  sidebarOpen: boolean;
  activeView: AppView;
  theme: Theme;
  toggleSidebar: () => void;
  setActiveView: (view: AppView) => void;
  setTheme: (theme: Theme) => void;
}

export const useUIStore = create<UIStore>()((set) => ({
  sidebarOpen: true,
  activeView: 'screener',
  theme: 'dark',
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setActiveView: (view) => set({ activeView: view }),
  setTheme: (theme) => set({ theme }),
}));

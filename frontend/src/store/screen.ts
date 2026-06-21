import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SavedScreenListItem, AlertRule } from '@/types/screener';

interface ScreenStore {
  selectedConfig: string;
  timeframes: string[];
  columnVisibility: Record<string, boolean>;
  columnOrder: string[];
  // Phase 8: Saved screens
  savedScreens: SavedScreenListItem[];
  selectedScreenId: string | null;
  isSaving: boolean;
  isLoading: boolean;
  // Phase 8: Alerts
  activeAlerts: AlertRule[];
  showAlertsPanel: boolean;
  lastAlertId: string | null;
  // Phase 8: Draft auto-save
  draftFilterJson: string;
  lastSavedAt: string | null;
  hasUnsavedChanges: boolean;

  // Setters
  setConfig: (config: string) => void;
  setTimeframes: (timeframes: string[]) => void;
  toggleColumn: (column: string) => void;
  setColumnOrder: (order: string[]) => void;

  // Phase 8 setters
  setSavedScreens: (screens: SavedScreenListItem[]) => void;
  setSelectedScreenId: (id: string | null) => void;
  setIsSaving: (saving: boolean) => void;
  setIsLoading: (loading: boolean) => void;
  setActiveAlerts: (alerts: AlertRule[]) => void;
  setShowAlertsPanel: (show: boolean) => void;
  setLastAlertId: (id: string | null) => void;
  setDraftFilterJson: (json: string) => void;
  setLastSavedAt: (at: string | null) => void;
  setHasUnsavedChanges: (changed: boolean) => void;
}

export const useScreenStore = create<ScreenStore>()(
  persist(
    (set) => ({
      selectedConfig: 'trend-follower',
      timeframes: ['1D', '4h'],
      columnVisibility: {},
      columnOrder: [],
      savedScreens: [],
      selectedScreenId: null,
      isSaving: false,
      isLoading: false,
      activeAlerts: [],
      showAlertsPanel: false,
      lastAlertId: null,
      draftFilterJson: '',
      lastSavedAt: null,
      hasUnsavedChanges: false,
      setConfig: (config) => set({ selectedConfig: config }),
      setTimeframes: (timeframes) => set({ timeframes }),
      toggleColumn: (column) =>
        set((state) => ({
          columnVisibility: {
            ...state.columnVisibility,
            [column]: !state.columnVisibility[column],
          },
        })),
      setColumnOrder: (order) => set({ columnOrder: order }),
      setSavedScreens: (screens) => set({ savedScreens: screens }),
      setSelectedScreenId: (id) => set({ selectedScreenId: id }),
      setIsSaving: (saving) => set({ isSaving: saving }),
      setIsLoading: (loading) => set({ isLoading: loading }),
      setActiveAlerts: (alerts) => set({ activeAlerts: alerts }),
      setShowAlertsPanel: (show) => set({ showAlertsPanel: show }),
      setLastAlertId: (id) => set({ lastAlertId: id }),
      setDraftFilterJson: (json) =>
        set({ draftFilterJson: json, hasUnsavedChanges: true }),
      setLastSavedAt: (at) => set({ lastSavedAt: at }),
      setHasUnsavedChanges: (changed) => set({ hasUnsavedChanges: changed }),
    }),
    {
      name: 'screen-store',
      partialize: (state) => ({
        selectedConfig: state.selectedConfig,
        timeframes: state.timeframes,
        columnVisibility: state.columnVisibility,
        columnOrder: state.columnOrder,
        selectedScreenId: state.selectedScreenId,
        draftFilterJson: state.draftFilterJson,
        lastSavedAt: state.lastSavedAt,
      }),
    }
  )
);

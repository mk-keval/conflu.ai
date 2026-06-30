import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SavedScreenListItem, AlertRule } from '@/types/screener';
import type { ScreenTemplateConfig } from '@/lib/constants';

interface CustomTemplateConfig {
  templateKey: string;
  config: ScreenTemplateConfig;
  isModified: boolean;
}

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
  // Custom template configs (user modifications to predefined templates)
  customTemplateConfigs: Record<string, CustomTemplateConfig>;

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

  // Custom template config setters
  setCustomTemplateConfig: (templateKey: string, config: ScreenTemplateConfig) => void;
  resetCustomTemplateConfig: (templateKey: string) => void;
  getCustomTemplateConfig: (templateKey: string) => ScreenTemplateConfig | null;
  isTemplateModified: (templateKey: string) => boolean;
}

export const useScreenStore = create<ScreenStore>()(
  persist(
    (set, get) => ({
      selectedConfig: 'Trend Follower',
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
      customTemplateConfigs: {},
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
      setCustomTemplateConfig: (templateKey, config) =>
        set((state) => {
          const newCustomTemplates = {
            ...state.customTemplateConfigs,
            [templateKey]: { templateKey, config, isModified: true },
          };
          // Manual persistence as fallback
          if (typeof window !== 'undefined') {
            try {
              let parsed: any = { state: {}, version: 0 };
              const store = localStorage.getItem('screen-store');
              if (store) {
                parsed = JSON.parse(store);
              }
              if (!parsed.state) parsed.state = {};
              parsed.state.customTemplateConfigs = newCustomTemplates;
              localStorage.setItem('screen-store', JSON.stringify(parsed));
            } catch {}
          }
          return { customTemplateConfigs: newCustomTemplates };
        }),
      resetCustomTemplateConfig: (templateKey) =>
        set((state) => {
          const { [templateKey]: removed, ...rest } = state.customTemplateConfigs;
          // Manual persistence as fallback
          if (typeof window !== 'undefined') {
            try {
              let parsed: any = { state: {}, version: 0 };
              const store = localStorage.getItem('screen-store');
              if (store) {
                parsed = JSON.parse(store);
              }
              if (!parsed.state) parsed.state = {};
              parsed.state.customTemplateConfigs = rest;
              localStorage.setItem('screen-store', JSON.stringify(parsed));
            } catch {}
          }
          return { customTemplateConfigs: rest };
        }),
      getCustomTemplateConfig: (templateKey) => {
        const custom = get().customTemplateConfigs[templateKey];
        return custom?.config ?? null;
      },
      isTemplateModified: (templateKey) => {
        const custom = get().customTemplateConfigs[templateKey];
        return custom?.isModified ?? false;
      },
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
        customTemplateConfigs: state.customTemplateConfigs,
      }),
    }
  )
);
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  AlertPreferences,
  InAppAlert,
  RiskTolerance,
} from '@/types/professional';

// ── Default Alert Preferences ──

const DEFAULT_ALERT_PREFS: AlertPreferences = {
  morningBrief: true,
  stopHitEmail: true,
  stopHitPush: true,
  targetHitPush: true,
  earningsEmail: true,
  regimeChangeEmail: true,
  regimeChangePush: true,
  weeklyReview: false,
};

// ── Store Interface ──

interface NotificationItem {
  id: string;
  type: InAppAlert['type'];
  symbol: string | null;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

interface ProModeStore {
  // Professional Mode state
  enabled: boolean;
  startDate: string | null;
  accountSize: number;
  riskTolerance: RiskTolerance;
  alertPreferences: AlertPreferences;
  notifications: NotificationItem[];

  // Actions
  toggleProMode: () => void;
  setAccountSize: (size: number) => void;
  setRiskTolerance: (tol: RiskTolerance) => void;
  updateAlertPreferences: (prefs: Partial<AlertPreferences>) => void;
  addNotification: (n: Omit<NotificationItem, 'id' | 'timestamp'>) => void;
  dismissNotification: (id: string) => void;
  markAllNotificationsRead: () => void;
  clearNotifications: () => void;
  resetProgress: () => void;
}

// ── Store ──

export const useProModeStore = create<ProModeStore>()(
  persist(
    (set) => ({
      // Default state
      enabled: true,
      startDate: new Date().toISOString(),
      accountSize: 100_000,
      riskTolerance: 'moderate',
      alertPreferences: DEFAULT_ALERT_PREFS,
      notifications: [],

      // Actions
      toggleProMode: () =>
        set((state) => ({
          enabled: !state.enabled,
          // Set start date when first enabling
          startDate: state.startDate || new Date().toISOString(),
        })),

      setAccountSize: (size) => set({ accountSize: Math.max(5000, size) }),

      setRiskTolerance: (tol) => set({ riskTolerance: tol }),

      updateAlertPreferences: (prefs) =>
        set((state) => ({
          alertPreferences: { ...state.alertPreferences, ...prefs },
        })),

      addNotification: (n) =>
        set((state) => ({
          notifications: [
            {
              ...n,
              id: crypto.randomUUID(),
              timestamp: new Date().toISOString(),
            },
            ...state.notifications,
          ].slice(0, 100), // Keep max 100 notifications
        })),

      dismissNotification: (id) =>
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
        })),

      markAllNotificationsRead: () =>
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
        })),

      clearNotifications: () => set({ notifications: [] }),

      resetProgress: () =>
        set({
          startDate: new Date().toISOString(),
          enabled: true,
        }),
    }),
    {
      name: 'pro-mode-store',
      partialize: (state) => ({
        enabled: state.enabled,
        startDate: state.startDate,
        accountSize: state.accountSize,
        riskTolerance: state.riskTolerance,
        alertPreferences: state.alertPreferences,
      }),
    }
  )
);

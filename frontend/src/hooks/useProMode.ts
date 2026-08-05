import { useMemo } from 'react';
import { useProModeStore } from '@/store/professional';
import { getUnlockedFeatures, UNLOCK_SCHEDULE } from '@/types/professional';

export function useProMode() {
  const store = useProModeStore();

  const daysActive = useMemo(() => {
    if (!store.startDate) return 0;
    const start = new Date(store.startDate).getTime();
    const now = Date.now();
    return Math.floor((now - start) / (1000 * 60 * 60 * 24));
  }, [store.startDate]);

  const unlockedFeatures = useMemo(
    () => getUnlockedFeatures(daysActive),
    [daysActive]
  );

  const isFeatureUnlocked = (feature: string): boolean =>
    unlockedFeatures.includes(feature);

  const featureLockDays = (feature: string): number => {
    const unlockDay = UNLOCK_SCHEDULE[feature];
    if (!unlockDay) return 0;
    return Math.max(0, unlockDay - daysActive);
  };

  const unreadCount = useMemo(
    () => store.notifications.filter((n) => !n.read).length,
    [store.notifications]
  );

  return {
    enabled: store.enabled,
    daysActive,
    unlockedFeatures,
    isFeatureUnlocked,
    featureLockDays,
    unreadCount,
    notifications: store.notifications,
    accountSize: store.accountSize,
    riskTolerance: store.riskTolerance,
    toggle: store.toggleProMode,
    dismissNotification: store.dismissNotification,
    markAllNotificationsRead: store.markAllNotificationsRead,
    addNotification: store.addNotification,
    setAccountSize: store.setAccountSize,
    setRiskTolerance: store.setRiskTolerance,
  };
}

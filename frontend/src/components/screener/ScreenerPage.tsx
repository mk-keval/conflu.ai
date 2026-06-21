import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchScreen, fetchSymbols } from '@/api/screener';
import { useScreenStore } from '@/store/screen';
import { useWS } from '@/ws/WebSocketProvider';
import { screenerChannel } from '@/ws/channels';
import { STALE_TIMES } from '@/lib/constants';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { SkeletonTable } from '@/components/layout/LoadingSkeleton';
import { useAlerts } from '@/hooks/useAlerts';
import { ScreenSelector } from './ScreenSelector';
import { ColumnToggle } from './ColumnToggle';
import { ExportButtons } from './ExportButtons';
import { ScreenerTable } from './ScreenerTable';
import { SaveScreenModal } from './SaveScreenModal';
import { LoadScreenModal } from './LoadScreenModal';
import { AlertsPanel } from './AlertsPanel';
import { AlertToast } from './AlertToast';
import { ShareModal } from './ShareModal';
import type { WSScreenUpdate, WSMessage } from '@/types/ws';
import type { ScreenSymbolResult, SavedScreenListItem, AlertRule } from '@/types/screener';

function ScreenerContent() {
  const { selectedConfig, timeframes, showAlertsPanel, setShowAlertsPanel, lastAlertId, draftFilterJson } = useScreenStore();
  const { subscribe, unsubscribe, onMessage } = useWS();
  const queryClient = useQueryClient();
  const { alerts } = useAlerts();

  // Modal state
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [showLoadModal, setShowLoadModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [currentScreenId, setCurrentScreenId] = useState('');
  const [toastAlert, setToastAlert] = useState<AlertRule | null>(null);

  // Track last triggered alert for toast
  useEffect(() => {
    if (lastAlertId) {
      const triggered = alerts.find((a) => a.id === lastAlertId);
      if (triggered) {
        setToastAlert(triggered);
      }
    }
  }, [lastAlertId, alerts]);

  const handleLoadScreen = (screen: SavedScreenListItem) => {
    useScreenStore.getState().setConfig(screen.name);
    useScreenStore.getState().setSelectedScreenId(screen.id);
    setCurrentScreenId(screen.id);
  };

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['screen', selectedConfig, timeframes],
    queryFn: () => fetchScreen(selectedConfig, undefined, timeframes),
    staleTime: STALE_TIMES.screen,
    refetchInterval: 30_000,
  });

  // Prefetch symbols for autocomplete
  useQuery({
    queryKey: ['symbols'],
    queryFn: () => fetchSymbols(),
    staleTime: STALE_TIMES.symbols,
  });

  // WS subscription for real-time screen updates
  useEffect(() => {
    const channel = screenerChannel(selectedConfig);
    subscribe(channel);
    return () => unsubscribe(channel);
  }, [selectedConfig, subscribe, unsubscribe]);

  // Handle WS messages
  useEffect(() => {
    const unsub = onMessage((message: WSMessage) => {
      if (message.type === 'screen_update') {
        const update = message as WSScreenUpdate;
        queryClient.setQueryData<ScreenSymbolResult[]>(
          ['screen', update.data.screen_name, timeframes],
          (oldData) => {
            if (!oldData) return oldData;
            return mergeScreenResults(oldData, update.data.symbols);
          }
        );
      }
    });
    return unsub;
  }, [onMessage, queryClient, timeframes]);

  if (isLoading) {
    return <SkeletonTable rows={8} className="p-4" />;
  }

  if (isError) {
    return (
      <div className="flex h-full items-center justify-center text-loss">
        Error loading screener data: {(error as Error)?.message}
      </div>
    );
  }

  const results = data || [];

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-dark-600 px-4 py-3">
        <ScreenSelector />
        <div className="flex-1" />

        {/* Phase 8: Screen Save/Load */}
        <button
          onClick={() => setShowSaveModal(true)}
          className="rounded px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-dark-600 hover:text-white"
          title="Save current configuration"
          disabled={!draftFilterJson}
        >
          Save
        </button>
        <button
          onClick={() => setShowLoadModal(true)}
          className="rounded px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-dark-600 hover:text-white"
          title="Load saved configuration"
        >
          Load
        </button>

        {/* Phase 8: Share */}
        <button
          onClick={() => {
            const screenId = useScreenStore.getState().selectedScreenId;
            if (screenId) {
              setCurrentScreenId(screenId);
              setShowShareModal(true);
            }
          }}
          className="rounded px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-dark-600 hover:text-white"
          title="Share screen configuration"
        >
          Share
        </button>

        {/* Phase 8: Alerts */}
        <button
          onClick={() => setShowAlertsPanel(!showAlertsPanel)}
          className="relative rounded px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-dark-600 hover:text-white"
          title="View alerts"
        >
          Alerts
          {alerts.filter((a) => a.is_active).length > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-accent text-[10px] text-white">
              {alerts.filter((a) => a.is_active).length}
            </span>
          )}
        </button>

        <ColumnToggle data={results} />
        <ExportButtons />
      </div>
      <ScreenerTable data={results} />

      {/* Phase 8: Modals */}
      <SaveScreenModal
        open={showSaveModal}
        onClose={() => setShowSaveModal(false)}
        filterJson={draftFilterJson}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ['screens'] })}
      />
      <LoadScreenModal
        open={showLoadModal}
        onClose={() => setShowLoadModal(false)}
        onLoad={handleLoadScreen}
      />
      <AlertsPanel
        open={showAlertsPanel}
        onClose={() => setShowAlertsPanel(false)}
      />
      <AlertToast
        alert={toastAlert}
        onDismiss={() => setToastAlert(null)}
      />
      <ShareModal
        open={showShareModal}
        onClose={() => setShowShareModal(false)}
        screenId={currentScreenId}
      />
    </div>
  );
}

export function ScreenerPage() {
  return (
    <ErrorBoundary>
      <ScreenerContent />
    </ErrorBoundary>
  );
}

function mergeScreenResults(
  existing: ScreenSymbolResult[],
  incoming: ScreenSymbolResult[]
): ScreenSymbolResult[] {
  const merged = new Map<string, ScreenSymbolResult>();
  for (const item of existing) {
    merged.set(item.symbol, item);
  }
  for (const item of incoming) {
    merged.set(item.symbol, item);
  }
  return Array.from(merged.values());
}

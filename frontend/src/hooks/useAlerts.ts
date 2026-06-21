import { useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listAlerts,
  createAlert,
  updateAlert,
  deleteAlert,
  toggleAlert,
} from '@/api/alerts';
import { useScreenStore } from '@/store/screen';
import { useWS } from '@/ws/WebSocketProvider';
import { alertUserChannel } from '@/ws/channels';
import type { CreateAlertRequest, UpdateAlertRequest } from '@/types/screener';
import type { WSAlertTriggered, WSMessage } from '@/types/ws';

export function useAlerts() {
  const queryClient = useQueryClient();
  const { subscribe, unsubscribe, onMessage } = useWS();
  const { setLastAlertId, setShowAlertsPanel } = useScreenStore();
  const handledAlertsRef = useRef<Set<string>>(new Set());

  // Fetch all alerts
  const { data: alerts, isLoading, isError, error } = useQuery({
    queryKey: ['alerts'],
    queryFn: listAlerts,
    refetchInterval: 60_000,
  });

  // Subscribe to user alert channel
  useEffect(() => {
    const channel = alertUserChannel('default');
    subscribe(channel);
    return () => unsubscribe(channel);
  }, [subscribe, unsubscribe]);

  // Handle real-time alert triggers
  useEffect(() => {
    const unsub = onMessage((message: WSMessage) => {
      if (message.type === 'alert_triggered') {
        const alertMsg = message as WSAlertTriggered;

        // Deduplicate
        const dedupKey = `${alertMsg.data.alert_id}:${alertMsg.data.triggered_at}`;
        if (handledAlertsRef.current.has(dedupKey)) return;
        handledAlertsRef.current.add(dedupKey);

        // Update store
        setLastAlertId(alertMsg.data.alert_id);
        setShowAlertsPanel(true);

        // Invalidate alerts query to refresh data
        queryClient.invalidateQueries({ queryKey: ['alerts'] });
      }
    });
    return unsub;
  }, [onMessage, queryClient, setLastAlertId, setShowAlertsPanel]);

  // Create alert mutation
  const createMutation = useMutation({
    mutationFn: (data: CreateAlertRequest) => createAlert(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  // Update alert mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateAlertRequest }) =>
      updateAlert(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  // Delete alert mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAlert(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  // Toggle alert mutation
  const toggleMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      toggleAlert(id, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  const handleCreate = useCallback(
    (data: CreateAlertRequest) => createMutation.mutateAsync(data),
    [createMutation]
  );

  const handleUpdate = useCallback(
    (id: string, data: UpdateAlertRequest) => updateMutation.mutateAsync({ id, data }),
    [updateMutation]
  );

  const handleDelete = useCallback(
    (id: string) => deleteMutation.mutateAsync(id),
    [deleteMutation]
  );

  const handleToggle = useCallback(
    (id: string, isActive: boolean) => toggleMutation.mutateAsync({ id, isActive }),
    [toggleMutation]
  );

  return {
    alerts: alerts || [],
    isLoading,
    isError,
    error,
    createAlert: handleCreate,
    updateAlert: handleUpdate,
    deleteAlert: handleDelete,
    toggleAlert: handleToggle,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  };
}

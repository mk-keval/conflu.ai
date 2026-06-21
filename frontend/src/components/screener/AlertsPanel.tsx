import { useAlerts } from '@/hooks/useAlerts';
import type { AlertRule } from '@/types/screener';

interface AlertsPanelProps {
  open: boolean;
  onClose: () => void;
}

export function AlertsPanel({ open, onClose }: AlertsPanelProps) {
  const {
    alerts,
    isLoading,
    toggleAlert,
    deleteAlert,
    isUpdating,
  } = useAlerts();

  if (!open) return null;

  const getAlertTypeBadge = (type: string) => {
    const colors: Record<string, string> = {
      price_threshold: 'bg-blue-900 text-blue-300',
      indicator_cross: 'bg-purple-900 text-purple-300',
      signal_trigger: 'bg-green-900 text-green-300',
      volume_spike: 'bg-orange-900 text-orange-300',
      trend_break: 'bg-red-900 text-red-300',
      compound: 'bg-yellow-900 text-yellow-300',
    };
    return colors[type] || 'bg-gray-700 text-gray-300';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl rounded-lg bg-dark-800 p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Active Alerts</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            ✕
          </button>
        </div>

        {isLoading ? (
          <div className="py-8 text-center text-gray-400">Loading alerts...</div>
        ) : alerts.length === 0 ? (
          <div className="py-8 text-center text-gray-400">
            No alerts configured. Create alerts from the screener toolbar.
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert: AlertRule) => (
              <div
                key={alert.id}
                className={`rounded border p-3 ${
                  alert.is_active ? 'border-dark-600' : 'border-dark-700 opacity-60'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white">{alert.name}</span>
                      <span
                        className={`rounded px-2 py-0.5 text-xs ${getAlertTypeBadge(alert.alert_type)}`}
                      >
                        {alert.alert_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    {alert.description && (
                      <div className="mt-1 text-xs text-gray-400">{alert.description}</div>
                    )}
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
                      <span>Triggered: {alert.trigger_count}x</span>
                      <span>Cooldown: {alert.cooldown_seconds}s</span>
                      {alert.symbols.length > 0 && (
                        <span>Symbols: {alert.symbols.join(', ')}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleAlert(alert.id, !alert.is_active)}
                      disabled={isUpdating}
                      className={`rounded px-2 py-1 text-xs font-medium ${
                        alert.is_active
                          ? 'bg-green-900 text-green-300 hover:bg-green-800'
                          : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                      }`}
                    >
                      {alert.is_active ? 'Active' : 'Paused'}
                    </button>
                    <button
                      onClick={() => deleteAlert(alert.id)}
                      className="text-xs text-gray-500 hover:text-loss"
                      title="Delete alert"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

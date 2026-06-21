import { useEffect, useState } from 'react';
import type { AlertRule } from '@/types/screener';

interface AlertToastProps {
  alert: AlertRule | null;
  onDismiss: () => void;
  autoHideMs?: number;
}

export function AlertToast({ alert, onDismiss, autoHideMs = 8000 }: AlertToastProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (alert) {
      setVisible(true);
      const timer = setTimeout(() => {
        setVisible(false);
        setTimeout(onDismiss, 300);
      }, autoHideMs);
      return () => clearTimeout(timer);
    }
  }, [alert, onDismiss, autoHideMs]);

  if (!visible || !alert) return null;

  const getSeverityColor = (severity?: string) => {
    switch (severity) {
      case 'critical':
        return 'border-red-500 bg-red-900/20';
      case 'warning':
        return 'border-yellow-500 bg-yellow-900/20';
      default:
        return 'border-accent bg-dark-700';
    }
  };

  const getSeverityIcon = (severity?: string) => {
    switch (severity) {
      case 'critical':
        return '🔴';
      case 'warning':
        return '🟡';
      default:
        return '🔔';
    }
  };

  return (
    <div
      className={`fixed bottom-4 right-4 z-50 w-80 rounded-lg border p-4 shadow-lg transition-all duration-300 ${getSeverityColor(alert.alert_type)}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{getSeverityIcon(alert.alert_type)}</span>
          <div>
            <div className="font-medium text-white">{alert.name}</div>
            {alert.description && (
              <div className="text-xs text-gray-400">{alert.description}</div>
            )}
          </div>
        </div>
        <button
          onClick={() => {
            setVisible(false);
            setTimeout(onDismiss, 300);
          }}
          className="text-gray-500 hover:text-white"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

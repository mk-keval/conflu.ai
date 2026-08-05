import { useState, useRef, useCallback, useEffect } from 'react';
import { Bell, BellDot, CheckCheck, TrendingUp, TrendingDown, AlertTriangle, Calendar } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useProModeStore } from '@/store/professional';

const ALERT_ICONS: Record<string, React.ReactNode> = {
  stop_hit: <TrendingDown className="h-4 w-4 text-red-400" />,
  target_hit: <TrendingUp className="h-4 w-4 text-green-400" />,
  earnings: <Calendar className="h-4 w-4 text-yellow-400" />,
  regime_change: <AlertTriangle className="h-4 w-4 text-blue-400" />,
  morning_brief: <Bell className="h-4 w-4 text-accent" />,
  weekly_review: <CheckCheck className="h-4 w-4 text-text-muted" />,
};

function timeAgo(timestamp: string): string {
  const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const notifications = useProModeStore((s) => s.notifications);
  const dismissNotification = useProModeStore((s) => s.dismissNotification);
  const markAllNotificationsRead = useProModeStore((s) => s.markAllNotificationsRead);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const toggle = useCallback(() => setOpen((prev) => !prev), []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={toggle}
        className="relative p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-tertiary transition-colors"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
      >
        {unreadCount > 0 ? (
          <>
            <BellDot className="h-5 w-5" />
            <span className="absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-red-500 text-2xs font-bold text-white flex items-center justify-center">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          </>
        ) : (
          <Bell className="h-5 w-5" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-lg border border-border bg-surface shadow-xl z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <span className="text-sm font-semibold text-text-primary">Notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={markAllNotificationsRead}
                className="text-xs text-accent hover:text-accent-light transition-colors"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="text-center py-6 text-sm text-text-muted">
                No notifications
              </div>
            ) : (
              notifications.slice(0, 50).map((n) => (
                <div
                  key={n.id}
                  className={cn(
                    'flex items-start gap-3 px-3 py-2.5 border-b border-border/50 last:border-0',
                    'hover:bg-surface-tertiary/50 transition-colors cursor-pointer',
                    !n.read && 'bg-accent/5'
                  )}
                  onClick={() => dismissNotification(n.id)}
                >
                  <div className="mt-0.5 flex-shrink-0">
                    {ALERT_ICONS[n.type] || <Bell className="h-4 w-4 text-text-muted" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-text-primary truncate">
                      {n.title}
                    </p>
                    <p className="text-2xs text-text-muted line-clamp-2 mt-0.5">
                      {n.message}
                    </p>
                    <span className="text-2xs text-text-muted mt-0.5 block">
                      {timeAgo(n.timestamp)}
                    </span>
                  </div>
                  {!n.read && (
                    <span className="h-2 w-2 rounded-full bg-accent flex-shrink-0 mt-1.5" />
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

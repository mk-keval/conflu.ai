import { useRef, useCallback } from 'react';
import { useWS } from '@/ws/WebSocketProvider';
import { useKeyboard } from '@/hooks/useKeyboard';
import { cn } from '@/lib/cn';

function ConnectionStatus() {
  const { connectionState } = useWS();

  const statusConfig: Record<string, { label: string; dot: string }> = {
    connected: { label: 'Connected', dot: 'bg-gain' },
    disconnected: { label: 'Disconnected', dot: 'bg-loss' },
    connecting: { label: 'Connecting...', dot: 'bg-yellow-400' },
    reconnecting: { label: 'Reconnecting...', dot: 'bg-yellow-400' },
  };

  const status = statusConfig[connectionState] || statusConfig.disconnected;

  return (
    <div className="flex items-center gap-2 rounded bg-dark-700 px-3 py-1.5">
      <span className={cn('h-2 w-2 rounded-full', status.dot)} />
      <span className="text-xs text-dark-200">{status.label}</span>
    </div>
  );
}

export function Header() {
  const searchRef = useRef<HTMLInputElement>(null);

  const handleSearchFocus = useCallback(() => {
    searchRef.current?.focus();
  }, []);

  const handleSearchBlur = useCallback(() => {
    searchRef.current?.blur();
  }, []);

  useKeyboard({
    '/': handleSearchFocus,
    Escape: handleSearchBlur,
  });

  return (
    <header className="flex h-14 items-center gap-4 border-b border-dark-600 bg-dark-900 px-4">
      <h1 className="text-lg font-semibold text-dark-50">conflu.ai</h1>

      <div className="flex-1" />

      <div className="relative">
        <input
          ref={searchRef}
          type="text"
          placeholder="Search symbols... (/)"
          className="w-64 rounded border border-dark-400 bg-dark-600 px-3 py-1.5 text-sm text-dark-50 placeholder-dark-300 outline-none focus:border-accent"
        />
      </div>

      <ConnectionStatus />
    </header>
  );
}

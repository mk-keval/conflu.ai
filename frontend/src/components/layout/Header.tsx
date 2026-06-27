import { useRef, useCallback, useState } from 'react';
import { useWS } from '@/ws/WebSocketProvider';
import { useKeyboard } from '@/hooks/useKeyboard';
import { cn } from '@/lib/cn';
import { Search, X } from 'lucide-react';

function ConnectionStatus() {
  const { connectionState } = useWS();

  const statusConfig: Record<string, { label: string; dot: string }> = {
    connected: { label: 'Connected', dot: 'bg-gain' },
    disconnected: { label: 'Disconnected', dot: 'bg-loss' },
    connecting: { label: 'Connecting...', dot: 'bg-warning' },
    reconnecting: { label: 'Reconnecting...', dot: 'bg-warning' },
  };

  const status = statusConfig[connectionState] || statusConfig.disconnected;

  return (
    <div className="flex items-center gap-2 rounded bg-surface px-3 py-1.5">
      <span className={cn('h-2 w-2 rounded-full', status.dot)} />
      <span className="text-xs text-text-muted capitalize">{status.label}</span>
    </div>
  );
}

export function Header() {
  const searchRef = useRef<HTMLInputElement>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearchFocus = useCallback(() => {
    searchRef.current?.focus();
  }, []);

  const handleSearchBlur = useCallback(() => {
    searchRef.current?.blur();
  }, []);

  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
    searchRef.current?.focus();
  }, []);

  useKeyboard({
    '/': handleSearchFocus,
    Escape: handleSearchBlur,
  });

  return (
    <header className="flex h-14 items-center gap-4 border-b border-border bg-surface px-4">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold text-accent">conflu.ai</span>
        <span className="hidden md:block h-6 w-px bg-border" />
        <nav className="flex items-center gap-1">
          <a href="/screener" className="px-3 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors">
            Screener
          </a>
          <a href="/charts" className="px-3 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors">
            Charts
          </a>
          <a href="/backtest" className="px-3 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors">
            Backtest
          </a>
          <a href="/risk" className="px-3 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors">
            Risk
          </a>
        </nav>
      </div>

      <div className="flex-1" />

      <div className="relative w-72 max-w-[300px]">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            ref={searchRef}
            type="text"
            placeholder="Search symbols... (/)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-10 rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-accent focus:ring-2 focus:ring-accent/30 transition-all duration-150"
          />
          {searchQuery && (
            <button
              onClick={handleClearSearch}
              className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <ConnectionStatus />
    </header>
  );
}

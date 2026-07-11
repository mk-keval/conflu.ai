import { useRef, useCallback, useState } from 'react';
import { useKeyboard } from '@/hooks/useKeyboard';
import { Search, X } from 'lucide-react';
import { RegimeBar } from './RegimeBar';

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
    <header className="relative z-30 flex h-14 items-center justify-between border-b border-border bg-surface/80 backdrop-blur-sm px-4 gap-4">
      <div className="relative w-full max-w-md">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            ref={searchRef}
            type="text"
            placeholder="Search symbols... (/)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-10 rounded-lg border border-border/60 bg-background px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all duration-150"
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

      {/* Market Regime indicator — always visible */}
      <RegimeBar />
    </header>
  );
}

import { useRef, useCallback, useState } from 'react';
import { useKeyboard } from '@/hooks/useKeyboard';
import { Search, X, GraduationCap, User } from 'lucide-react';
import { RegimeBar } from './RegimeBar';
import { NotificationBell } from '@/components/professional/NotificationBell';
import { useProModeStore } from '@/store/professional';
import { cn } from '@/lib/cn';

export function Header() {
  const searchRef = useRef<HTMLInputElement>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const enabled = useProModeStore((s) => s.enabled);
  const toggleProMode = useProModeStore((s) => s.toggleProMode);

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
    <header className="relative z-30 flex h-14 items-center justify-between border-b border-white/10 bg-surface/60 backdrop-blur-xl px-4 gap-4">
      <div className="relative w-full max-w-[140px] sm:max-w-[180px] lg:max-w-md">
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

      {/* Right side controls */}
      <div className="flex items-center gap-3">
        {/* Professional Mode toggle */}
        <button
          onClick={toggleProMode}
          className={cn(
            'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors',
            enabled
              ? 'border-accent/30 bg-accent/10 text-accent'
              : 'border-border/60 bg-white/[0.04] text-text-muted hover:text-text-primary'
          )}
          title={enabled ? 'Switch to Explorer mode' : 'Switch to Guided mode'}
        >
          {enabled ? (
            <GraduationCap className="h-3.5 w-3.5" />
          ) : (
            <User className="h-3.5 w-3.5" />
          )}
          <span className="hidden sm:inline">{enabled ? 'Guided' : 'Explorer'}</span>
        </button>

        {/* Notification bell */}
        <NotificationBell />

        {/* Market Regime indicator — always visible */}
        <RegimeBar />
      </div>
    </header>
  );
}

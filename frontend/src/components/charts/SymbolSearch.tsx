import { useState, useRef, useCallback } from 'react';
import { Search } from 'lucide-react';
import { useChartStore } from '@/store/chart';

export function SymbolSearch() {
  const [search, setSearch] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const { selectedSymbol, setSymbol } = useChartStore();

  const handleSubmit = useCallback(() => {
    if (!search.trim()) return;
    setSymbol(search.trim().toUpperCase());
    setSearch('');
    inputRef.current?.blur();
  }, [search, setSymbol]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="relative flex items-center gap-2">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <input
          ref={inputRef}
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={selectedSymbol || 'Search symbols...'}
          className="w-64 rounded-lg border border-border/60 bg-background pl-10 pr-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-all duration-150"
        />
      </div>
      <button
        onClick={handleSubmit}
        disabled={!search.trim()}
        className="btn-primary gap-1.5 px-3 py-2 text-sm disabled:opacity-40 disabled:cursor-not-allowed"
        title="Load chart"
      >
        <Search className="h-4 w-4" />
        <span>Load</span>
      </button>
    </div>
  );
}

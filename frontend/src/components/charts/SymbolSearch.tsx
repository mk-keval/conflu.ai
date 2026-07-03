import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchSymbols } from '@/api/screener';
import { useChartStore } from '@/store/chart';
import { cn } from '@/lib/cn';

export function SymbolSearch() {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { selectedSymbol, setSymbol } = useChartStore();

  const { data: symbols } = useQuery({
    queryKey: ['symbols'],
    queryFn: () => fetchSymbols(),
    staleTime: Infinity,
  });

  const symbolsList = Array.isArray(symbols) ? symbols : [];
  const filtered = symbolsList
    .filter(
      (s) =>
        s.symbol.toLowerCase().includes(search.toLowerCase()) ||
        s.name.toLowerCase().includes(search.toLowerCase())
    )
    .slice(0, 10);

  const handleSelect = useCallback(
    (symbol: string) => {
      setSymbol(symbol);
      setSearch('');
      setIsOpen(false);
    },
    [setSymbol]
  );

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filtered[selectedIndex]) {
          handleSelect(filtered[selectedIndex].symbol);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        break;
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <input
        ref={inputRef}
        type="text"
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setIsOpen(true);
          setSelectedIndex(0);
        }}
        onFocus={() => setIsOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={selectedSymbol || 'Search symbols...'}
        className="w-64 rounded border border-dark-400 bg-dark-600 px-3 py-1.5 text-sm text-dark-50 placeholder-dark-300 outline-none focus:border-accent"
      />

      {isOpen && search && filtered.length > 0 && (
        <div className="absolute left-0 top-full z-50 mt-1 w-64 rounded border border-dark-500 bg-dark-700 shadow-lg">
          {filtered.map((s, i) => (
            <button
              key={s.symbol}
              onClick={() => handleSelect(s.symbol)}
              className={cn(
                'flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors',
                i === selectedIndex
                  ? 'bg-dark-500 text-dark-50'
                  : 'text-dark-200 hover:bg-dark-600'
              )}
            >
              <span className="font-medium">{s.symbol}</span>
              <span className="text-xs text-dark-400">{s.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

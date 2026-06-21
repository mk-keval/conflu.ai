import { useState, useRef, useEffect, useMemo } from 'react';
import { useScreenStore } from '@/store/screen';
import type { ScreenSymbolResult } from '@/types/screener';

interface ColumnToggleProps {
  data: ScreenSymbolResult[];
}

export function ColumnToggle({ data }: ColumnToggleProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { columnVisibility, toggleColumn } = useScreenStore();

  const allColumns = useMemo(() => {
    if (data.length === 0) return [];
    const cols = ['symbol', 'score', 'matched_filters'];
    const indicatorKeys = Object.keys(data[0].indicator_values || {});
    return [...cols, ...indicatorKeys];
  }, [data]);

  const filteredColumns = allColumns.filter((col) =>
    col.toLowerCase().includes(search.toLowerCase())
  );

  const visibleCount = allColumns.filter((col) => columnVisibility[col] !== false).length;

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsOpen(false);
    }
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen]);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="rounded bg-dark-600 px-3 py-1.5 text-sm text-dark-200 hover:bg-dark-500"
      >
        Columns ({visibleCount})
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full z-50 mt-1 max-h-80 w-56 overflow-y-auto rounded border border-dark-500 bg-dark-700 p-2 shadow-lg">
          <input
            type="text"
            placeholder="Search columns..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="mb-2 w-full rounded border border-dark-400 bg-dark-600 px-2 py-1 text-xs text-dark-50 outline-none placeholder-dark-300"
            autoFocus
          />
          {filteredColumns.map((col) => (
            <label
              key={col}
              className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm text-dark-200 hover:bg-dark-600"
            >
              <input
                type="checkbox"
                checked={columnVisibility[col] !== false}
                onChange={() => toggleColumn(col)}
                className="rounded border-dark-400 bg-dark-600 text-accent focus:ring-accent"
              />
              <span>{col}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

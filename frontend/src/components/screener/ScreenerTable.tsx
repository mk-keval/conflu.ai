import { useRef, useState, useMemo, useCallback } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useScreenStore } from '@/store/screen';
import { ScreenerRow } from './ScreenerRow';
import { ColumnHeader } from './ColumnHeader';
import type { ScreenSymbolResult } from '@/types/screener';

interface ColumnDef {
  key: string;
  label: string;
}

interface ScreenerTableProps {
  data: ScreenSymbolResult[];
}

export function ScreenerTable({ data }: ScreenerTableProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const { columnVisibility } = useScreenStore();
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc' | null>(null);

  const columns = useMemo(() => {
    if (data.length === 0) return [];
    const baseCols: ColumnDef[] = [
      { key: 'symbol', label: 'Symbol' },
      { key: 'score', label: 'Score' },
      { key: 'matched_filters', label: 'Matched Filters' },
    ];
    const indicatorCols = Object.keys(data[0].indicator_values || {}).map((key) => ({
      key,
      label: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    }));
    return [...baseCols, ...indicatorCols];
  }, [data]);

  const visibleColumns = columns.filter(
    (col) => columnVisibility[col.key] !== false
  );

  const sortedData = useMemo(() => {
    if (!sortKey || !sortDir) return data;
    return [...data].sort((a, b) => {
      let aVal: number | string = 0;
      let bVal: number | string = 0;

      if (sortKey === 'symbol') {
        aVal = a.symbol;
        bVal = b.symbol;
      } else if (sortKey === 'score') {
        aVal = a.score;
        bVal = b.score;
      } else if (sortKey === 'matched_filters') {
        aVal = a.matched_filters?.length ?? 0;
        bVal = b.matched_filters?.length ?? 0;
      } else if (a.indicator_values) {
        aVal = a.indicator_values[sortKey] ?? 0;
        bVal = b.indicator_values[sortKey] ?? 0;
      }

      if (typeof aVal === 'string') {
        return sortDir === 'asc'
          ? aVal.localeCompare(bVal as string)
          : (bVal as string).localeCompare(aVal);
      }
      return sortDir === 'asc'
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
  }, [data, sortKey, sortDir]);

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        if (sortDir === null) setSortDir('asc');
        else if (sortDir === 'asc') setSortDir('desc');
        else {
          setSortKey(null);
          setSortDir(null);
        }
      } else {
        setSortKey(key);
        setSortDir('asc');
      }
    },
    [sortKey, sortDir]
  );

  const virtualizer = useVirtualizer({
    count: sortedData.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
    overscan: 5,
  });

  if (data.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-dark-300">
        No results. Try a different screen configuration.
      </div>
    );
  }

  return (
    <div ref={parentRef} className="flex-1 overflow-auto">
      <table className="w-full table-fixed">
        <thead className="sticky top-0 z-20 bg-dark-700">
          <tr>
            {visibleColumns.map((col) => (
              <ColumnHeader
                key={col.key}
                column={col}
                sortKey={sortKey}
                sortDir={sortDir}
                onSort={handleSort}
              />
            ))}
          </tr>
        </thead>
        <tbody
          style={{
            position: 'relative',
            height: `${virtualizer.getTotalSize()}px`,
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => (
            <ScreenerRow
              key={virtualRow.key}
              data={sortedData[virtualRow.index]}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualRow.start}px)`,
              }}
              columns={visibleColumns}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

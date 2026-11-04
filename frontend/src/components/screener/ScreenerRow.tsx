import React from 'react';
import type { ScreenSymbolResult } from '@/types/screener';
import { formatPrice, formatPct } from '@/lib/format';
import { cn } from '@/lib/cn';

interface ColumnDef {
  key: string;
  label: string;
}

interface ScreenerRowProps {
  data: ScreenSymbolResult;
  style: React.CSSProperties;
  columns: ColumnDef[];
}

export const ScreenerRow = React.memo(function ScreenerRow({
  data,
  style,
  columns,
}: ScreenerRowProps) {
  const renderCell = (col: ColumnDef) => {
    if (col.key === 'symbol') {
      return (
        <span className="font-medium text-accent-light">{data.symbol}</span>
      );
    }
    if (col.key === 'score') {
      const score = data.score;
      return (
        <span
          className={cn(
            'font-mono font-semibold',
            score >= 80
              ? 'text-gain'
              : score >= 50
                ? 'text-yellow-400'
                : 'text-text-secondary'
          )}
        >
          {score.toFixed(1)}
        </span>
      );
    }
    if (col.key === 'matched_filters') {
      return (
        <span className="text-text-secondary">
          {data.matched_filters?.join(', ') || '—'}
        </span>
      );
    }

    // Indicator values
    const value = data.indicator_values?.[col.key];
    if (typeof value === 'number') {
      if (col.key.startsWith('price') || col.key.startsWith('close')) {
        return <span className="font-mono">{formatPrice(value)}</span>;
      }
      if (
        col.key.startsWith('rsi') ||
        col.key.startsWith('pct') ||
        col.key.endsWith('_pct')
      ) {
        return <span className="font-mono">{formatPct(value)}</span>;
      }
      return <span className="font-mono">{value.toFixed(2)}</span>;
    }

    return <span className="text-text-muted">—</span>;
  };

  return (
    <tr
      style={style}
      className="border-b border-border transition-colors hover:bg-surface/50"
    >
      {columns.map((col) => (
        <td
          key={col.key}
          className={cn(
            'whitespace-nowrap px-3 py-2 text-sm',
            col.key === 'symbol' && 'sticky left-0 z-10 bg-surface'
          )}
          title={
            col.key === 'symbol' || col.key === 'score'
              ? undefined
              : `${col.label}: ${
                  data.indicator_values?.[col.key]?.toFixed(4) ?? 'N/A'
                }`
          }
        >
          {renderCell(col)}
        </td>
      ))}
    </tr>
  );
});

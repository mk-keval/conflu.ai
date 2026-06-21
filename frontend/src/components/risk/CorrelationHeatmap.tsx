import { useMemo } from 'react';
import type { CorrelationResult } from '@/types/risk';
import { formatNumber } from '@/lib/format';
import { cn } from '@/lib/cn';

interface CorrelationHeatmapProps {
  data: CorrelationResult | null;
  isLoading?: boolean;
  error?: string | null;
}

function corrColor(value: number): string {
  if (value > 0.8) return 'bg-gain/30 text-gain';
  if (value > 0.5) return 'bg-gain/15 text-gain-light';
  if (value > 0.3) return 'bg-green-500/10 text-dark-100';
  if (value > -0.3) return 'bg-dark-500 text-dark-200';
  if (value > -0.5) return 'bg-loss/10 text-loss-light';
  if (value > -0.8) return 'bg-loss/15 text-loss';
  return 'bg-loss/30 text-loss';
}

function CorrCell({ value }: { value: number }) {
  return (
    <div
      className={cn(
        'flex h-9 items-center justify-center rounded text-[10px] font-mono font-medium transition-opacity hover:opacity-80',
        corrColor(value)
      )}
      title={value.toFixed(3)}
    >
      {formatNumber(value, 2)}
    </div>
  );
}

export function CorrelationHeatmap({ data, isLoading, error }: CorrelationHeatmapProps) {
  const matrix = useMemo(() => {
    if (!data) return { symbols: [] as string[], rows: [] as number[][] };
    return { symbols: data.symbols, rows: data.correlation_matrix };
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex h-48 items-center justify-center rounded border border-dark-600 bg-dark-800 text-sm text-dark-400">
        Loading correlation data...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-48 items-center justify-center rounded border border-dark-600 bg-dark-800 text-sm text-loss">
        Error: {error}
      </div>
    );
  }

  if (!data || matrix.symbols.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded border border-dashed border-dark-600 text-sm text-dark-400">
        No correlation data
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Diversification score */}
      <div className="flex items-center gap-2 rounded border border-dark-600 bg-dark-800 px-3 py-2">
        <span className="text-xs text-dark-300">Diversification Score:</span>
        <span
          className={cn(
            'font-mono text-sm font-semibold',
            data.diversification_score >= 0.7 ? 'text-gain' : data.diversification_score >= 0.4 ? 'text-yellow-400' : 'text-loss'
          )}
        >
          {formatNumber(data.diversification_score, 2)}
        </span>
      </div>

      {/* Correlation matrix */}
      <div className="overflow-x-auto">
        <div className="inline-block">
          {/* Header row */}
          <div className="flex items-center gap-1 pb-1">
            <div className="w-16 shrink-0" />
            {matrix.symbols.map((sym) => (
              <div
                key={sym}
                className="w-16 shrink-0 text-center text-[10px] font-medium text-dark-300"
              >
                {sym}
              </div>
            ))}
          </div>

          {/* Matrix rows */}
          {matrix.rows.map((row, i) => (
            <div key={matrix.symbols[i]} className="flex items-center gap-1 py-0.5">
              <div className="w-16 shrink-0 text-[10px] font-medium text-dark-200">
                {matrix.symbols[i]}
              </div>
              {row.map((value, j) => (
                <div key={j} className="w-16 shrink-0">
                  <CorrCell value={value} />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* High correlation pairs */}
      {data.high_correlation_pairs.length > 0 && (
        <div className="rounded border border-dark-600 bg-dark-800 p-3">
          <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-dark-400">
            High Correlation Pairs
          </h4>
          <div className="space-y-1">
            {data.high_correlation_pairs.slice(0, 5).map((pair) => (
              <div
                key={`${pair.symbols[0]}-${pair.symbols[1]}`}
                className="flex items-center justify-between text-xs"
              >
                <span className="text-dark-200">
                  {pair.symbols[0]} / {pair.symbols[1]}
                </span>
                <span className="font-mono text-loss">{formatNumber(pair.correlation, 3)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

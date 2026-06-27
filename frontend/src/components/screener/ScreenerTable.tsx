import { useRef, useState, useMemo, useCallback } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Minus } from 'lucide-react';
import { cn } from '@/lib/cn';
import { formatPrice, formatLargeNumber } from '@/lib/format';
import type { TVScoredTicker } from '@/types/screener';

interface ColumnDef {
  key: string;
  label: string;
  width?: number;
  align?: 'left' | 'right' | 'center';
  render?: (ticker: TVScoredTicker) => React.ReactNode;
}

interface ScreenerTableProps {
  results: TVScoredTicker[];
  onRowClick: (ticker: TVScoredTicker) => void;
  sortState: { key: string | null; dir: 'asc' | 'desc' | null };
  onSort: (key: string) => void;
  currentPage: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

const PAGE_SIZES = [10, 25, 50, 100];

const COLUMNS: ColumnDef[] = [
  { key: 'symbol', label: 'Symbol', width: 100, align: 'left' },
  { key: 'price', label: 'Price', width: 100, align: 'right' },
  { key: 'score', label: 'Score', width: 80, align: 'center' },
  { key: 'change', label: 'Change', width: 110, align: 'right' },
  { key: 'volume', label: 'Volume', width: 120, align: 'right' },
  { key: 'rsi', label: 'RSI', width: 70, align: 'center' },
  { key: 'macd', label: 'MACD', width: 100, align: 'right' },
  { key: 'signal', label: 'Signal', width: 100, align: 'center' },
  { key: 'rating', label: 'Rating', width: 110, align: 'center' },
  { key: 'action', label: 'Action', width: 100, align: 'center' },
];

function SortIcon({ key, sortKey, sortDir }: { key: string; sortKey: string | null; sortDir: 'asc' | 'desc' | null }) {
  if (sortKey !== key) {
    return <Minus className="w-4 h-4 text-text-muted" />;
  }
  return sortDir === 'asc' ? (
    <ChevronUp className="w-4 h-4 text-accent" />
  ) : (
    <ChevronDown className="w-4 h-4 text-accent" />
  );
}

function ColumnHeader({ column, sortKey, sortDir, onSort }: { column: ColumnDef; sortKey: string | null; sortDir: 'asc' | 'desc' | null; onSort: (key: string) => void }) {
  return (
    <th
      className={cn(
        'whitespace-nowrap px-3 py-2.5 text-xs font-semibold text-text-secondary uppercase tracking-wider',
        'cursor-pointer select-none hover:text-text-primary transition-colors',
        column.align === 'right' && 'text-right',
        column.align === 'center' && 'text-center'
      )}
      style={{ width: column.width ? `${column.width}px` : undefined, minWidth: column.width ? `${column.width}px` : undefined }}
      onClick={() => onSort(column.key)}
    >
      <div className="flex items-center justify-center gap-1">
        <span>{column.label}</span>
        <SortIcon key={column.key} sortKey={sortKey} sortDir={sortDir} />
      </div>
    </th>
  );
}

function RatingBadge({ rating }: { rating: string }) {
  const config = {
    'Strong Buy': { className: 'badge-green' },
    'Buy': { className: 'badge-green' },
    'Hold': { className: 'badge-neutral' },
    'Sell': { className: 'badge-red' },
    'Strong Sell': { className: 'badge-red' },
  }[rating] || { className: 'badge-neutral' };

  return (
    <span className={cn('badge px-2 py-1 text-xs font-medium', config.className)}>
      {rating}
    </span>
  );
}

function SignalBadge({ signal }: { signal: string }) {
  const isBuy = signal.toLowerCase().includes('buy');
  const isSell = signal.toLowerCase().includes('sell');

  return (
    <span
      className={cn(
        'badge px-2 py-1 text-xs font-medium',
        isBuy ? 'badge-green' : isSell ? 'badge-red' : 'badge-neutral'
      )}
    >
      {signal}
    </span>
  );
}

function ChangeCell({ change, changePct }: { change: number; changePct: number }) {
  const isGain = change >= 0;
  return (
    <span className={cn('font-mono text-price', isGain ? 'text-gain' : 'text-loss')}>
      {isGain ? '+' : ''}{change.toFixed(2)} ({isGain ? '+' : ''}{changePct.toFixed(2)}%)
    </span>
  );
}

function VolumeCell({ volume }: { volume: number }) {
  return (
    <span className="font-mono text-price text-volume">
      {formatLargeNumber(volume)}
    </span>
  );
}

function PriceCell({ price }: { price: number }) {
  return (
    <span className="font-mono text-price tabular-nums text-text-primary">
      {formatPrice(price)}
    </span>
  );
}

function ScoreCell({ score }: { score: number }) {
  const color = score >= 80 ? 'text-gain' : score >= 60 ? 'text-warning' : score >= 40 ? 'text-info' : 'text-loss';
  return (
    <span className={cn('font-mono font-semibold text-price', color)}>
      {score.toFixed(1)}
    </span>
  );
}

function RSI_Cell({ rsi }: { rsi: number | undefined }) {
  if (rsi === undefined) return <span className="text-text-muted">—</span>;
  const color = rsi >= 70 ? 'text-loss' : rsi <= 30 ? 'text-gain' : 'text-text-primary';
  return (
    <span className={cn('font-mono text-price font-medium', color)}>
      {rsi.toFixed(1)}
    </span>
  );
}

function MACD_Cell({ macd, signal }: { macd: number | undefined; signal: number | undefined }) {
  if (macd === undefined || signal === undefined) return <span className="text-text-muted">—</span>;
  const isBullish = macd > signal;
  return (
    <span className={cn('font-mono text-price', isBullish ? 'text-gain' : 'text-loss')}>
      {macd.toFixed(3)}
    </span>
  );
}

function SymbolCell({ symbol }: { symbol: string }) {
  return (
    <span className="font-semibold text-text-primary cursor-pointer hover:text-accent transition-colors">
      {symbol}
    </span>
  );
}

function ActionButton({ onClick }: { onClick: (e: React.MouseEvent<HTMLButtonElement>) => void }) {
  return (
    <button
      onClick={onClick}
      className="btn-secondary px-3 py-1.5 text-xs gap-1"
      aria-label="View details"
    >
      <span>Details</span>
    </button>
  );
}

export function ScreenerTable({
  results,
  onRowClick,
  sortState,
  onSort,
  currentPage,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: ScreenerTableProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [sortKey, setSortKey] = useState<string | null>(sortState.key);
  const [sortDir, setSortDir] = useState<'asc' | 'desc' | null>(sortState.dir);

  // Sync with parent sort state
  if (sortState.key !== sortKey || sortState.dir !== sortDir) {
    setSortKey(sortState.key);
    setSortDir(sortState.dir);
  }

  const sortedData = useMemo(() => {
    if (!sortKey || !sortDir) return results;
    return [...results].sort((a, b) => {
      let aVal: number | string = 0;
      let bVal: number | string = 0;

      switch (sortKey) {
        case 'symbol':
          aVal = a.symbol;
          bVal = b.symbol;
          break;
        case 'price':
          aVal = a.tv_data?.close as number ?? 0;
          bVal = b.tv_data?.close as number ?? 0;
          break;
        case 'score':
          aVal = a.score;
          bVal = b.score;
          break;
        case 'change':
          aVal = a.tv_data?.change as number ?? 0;
          bVal = b.tv_data?.change as number ?? 0;
          break;
        case 'volume':
          aVal = a.tv_data?.volume as number ?? 0;
          bVal = b.tv_data?.volume as number ?? 0;
          break;
        case 'rsi':
          aVal = a.tv_data?.rsi as number ?? 0;
          bVal = b.tv_data?.rsi as number ?? 0;
          break;
        case 'macd':
          aVal = a.tv_data?.macd as number ?? 0;
          bVal = b.tv_data?.macd as number ?? 0;
          break;
        case 'rating':
          aVal = a.rating;
          bVal = b.rating;
          break;
        default:
          aVal = 0;
          bVal = 0;
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
  }, [results, sortKey, sortDir]);

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
      onSort(key);
    },
    [sortKey, sortDir, onSort]
  );

  // Pagination
  const totalPages = Math.ceil(sortedData.length / pageSize);
  const paginatedData = sortedData.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize
  );

  const virtualizer = useVirtualizer({
    count: paginatedData.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
    overscan: 5,
  });

  if (results.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center p-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-surface border border-border flex items-center justify-center">
            <svg className="w-8 h-8 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-text-primary mb-1">No Results</h3>
          <p className="text-text-muted">
            Configure your filters and run a screen to discover trading opportunities
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Table */}
      <div ref={parentRef} className="flex-1 overflow-auto">
        <div className="overflow-x-auto">
          <table className="w-full table-fixed min-w-[1060px]">
            <thead className="sticky top-0 z-20 bg-surface/80 backdrop-blur-sm border-b border-border">
              <tr>
                {COLUMNS.map((col) => (
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
              {virtualizer.getVirtualItems().map((virtualRow) => {
                const ticker = paginatedData[virtualRow.index];
                const price = ticker.tv_data?.close as number ?? ticker.entry;
                const change = ticker.tv_data?.change as number ?? 0;
                const changePct = ticker.tv_data?.change_percent as number ?? 0;
                const volume = ticker.tv_data?.volume as number ?? 0;
                const rsi = ticker.tv_data?.rsi as number | undefined;
                const macd = ticker.tv_data?.macd as number | undefined;
                const macdSignal = ticker.tv_data?.macd_signal as number | undefined;
                const signal = ticker.tv_data?.signal as string ?? 'Neutral';

                return (
                  <tr
                    key={ticker.symbol}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                    className="border-b border-border/50 transition-colors hover:bg-surface-hover/50 cursor-pointer"
                    onClick={() => onRowClick(ticker)}
                  >
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm sticky left-0 z-10 bg-surface/80 backdrop-blur-sm">
                      <SymbolCell symbol={ticker.symbol} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-right">
                      <PriceCell price={price} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-center">
                      <ScoreCell score={ticker.score} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-right">
                      <ChangeCell change={change} changePct={changePct} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-right">
                      <VolumeCell volume={volume} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-center">
                      <RSI_Cell rsi={rsi} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-right">
                      <MACD_Cell macd={macd} signal={macdSignal} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-center">
                      <SignalBadge signal={signal} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-center">
                      <RatingBadge rating={ticker.rating} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-center">
                      <ActionButton onClick={(e) => { e.stopPropagation(); onRowClick(ticker); }} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-border px-4 py-3 bg-surface/50">
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <span>Showing</span>
          <span className="font-mono text-text-primary">
            {sortedData.length > 0 ? currentPage * pageSize + 1 : 0}
          </span>
          <span>to</span>
          <span className="font-mono text-text-primary">
            {Math.min((currentPage + 1) * pageSize, sortedData.length)}
          </span>
          <span>of</span>
          <span className="font-mono text-text-primary">{sortedData.length}</span>
          <span>results</span>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="select w-auto px-2 py-1 text-xs"
            aria-label="Results per page"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size} per page
              </option>
            ))}
          </select>

          <div className="flex items-center gap-1 ml-4">
            <button
              onClick={() => onPageChange(0)}
              disabled={currentPage === 0}
              className="btn-ghost p-1.5 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="First page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 0}
              className="btn-ghost p-1.5 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-1 mx-2">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum: number;
                if (totalPages <= 5) {
                  pageNum = i;
                } else if (currentPage <= 1) {
                  pageNum = i;
                } else if (currentPage >= totalPages - 2) {
                  pageNum = totalPages - 5 + i;
                } else {
                  pageNum = currentPage - 2 + i;
                }
                return (
                  <button
                    key={pageNum}
                    onClick={() => onPageChange(pageNum)}
                    className={cn(
                      'w-8 h-8 rounded-lg text-sm font-medium transition-all',
                      pageNum === currentPage
                        ? 'bg-accent text-white'
                        : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                    )}
                    aria-label={`Page ${pageNum + 1}`}
                    aria-current={pageNum === currentPage ? 'page' : undefined}
                  >
                    {pageNum + 1}
                  </button>
                );
              })}
            </div>

            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages - 1}
              className="btn-ghost p-1.5 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Next page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => onPageChange(totalPages - 1)}
              disabled={currentPage >= totalPages - 1}
              className="btn-ghost p-1.5 disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Last page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
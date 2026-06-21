import { useState, useMemo } from 'react';
import type { Trade } from '@/types/backtest';
import { formatPrice, formatPnL, formatDateTime } from '@/lib/format';
import { cn } from '@/lib/cn';
import { TradeDetail } from './TradeDetail';

interface TradesTableProps {
  trades: Trade[];
}

type SortKey = 'entry_time' | 'exit_time' | 'symbol' | 'pnl' | 'direction' | 'hold_duration_bars';
type SortDir = 'asc' | 'desc';

export function TradesTable({ trades }: TradesTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('entry_time');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [selectedTrade, setSelectedTrade] = useState<Trade | null>(null);

  const sorted = useMemo(() => {
    const copy = [...trades];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'entry_time':
        case 'exit_time':
          cmp = a[sortKey].localeCompare(b[sortKey]);
          break;
        case 'symbol':
          cmp = a.symbol.localeCompare(b.symbol);
          break;
        case 'pnl':
          cmp = a.pnl - b.pnl;
          break;
        case 'direction':
          cmp = a.direction.localeCompare(b.direction);
          break;
        case 'hold_duration_bars':
          cmp = a.hold_duration_bars - b.hold_duration_bars;
          break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [trades, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  function SortHeader({ label, sort }: { label: string; sort: SortKey }) {
    const active = sortKey === sort;
    return (
      <th
        className={cn(
          'cursor-pointer px-2 py-2 text-left text-[10px] font-semibold uppercase tracking-wider transition-colors hover:text-dark-50',
          active ? 'text-accent-light' : 'text-dark-400'
        )}
        onClick={() => toggleSort(sort)}
      >
        {label}
        {active && <span className="ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>}
      </th>
    );
  }

  if (!trades.length) {
    return (
      <div className="flex h-24 items-center justify-center rounded border border-dark-600 bg-dark-800 text-sm text-dark-400">
        No trades recorded
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto rounded border border-dark-600">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-dark-600 bg-dark-800">
              <SortHeader label="Symbol" sort="symbol" />
              <SortHeader label="Direction" sort="direction" />
              <SortHeader label="Entry" sort="entry_time" />
              <SortHeader label="Exit" sort="exit_time" />
              <th className="px-2 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-dark-400">
                Entry $
              </th>
              <th className="px-2 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-dark-400">
                Exit $
              </th>
              <SortHeader label="Size" sort="hold_duration_bars" />
              <SortHeader label="PnL" sort="pnl" />
              <th className="px-2 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-dark-400">
                MAE
              </th>
              <th className="px-2 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-dark-400">
                MFE
              </th>
              <SortHeader label="Bars" sort="hold_duration_bars" />
              <th className="px-2 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-dark-400">
                Reason
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((trade) => (
              <tr
                key={`${trade.run_id}-${trade.trade_index}`}
                className={cn(
                  'cursor-pointer border-b border-dark-700 transition-colors hover:bg-dark-700',
                  selectedTrade?.trade_index === trade.trade_index && 'bg-dark-700'
                )}
                onClick={() => setSelectedTrade(trade)}
              >
                <td className="px-2 py-2 font-medium text-dark-50">{trade.symbol}</td>
                <td className="px-2 py-2">
                  <span
                    className={cn(
                      'rounded px-1.5 py-0.5 text-[10px] font-medium',
                      trade.direction === 'Long'
                        ? 'bg-gain/10 text-gain'
                        : 'bg-loss/10 text-loss'
                    )}
                  >
                    {trade.direction}
                  </span>
                </td>
                <td className="whitespace-nowrap px-2 py-2 text-dark-300">
                  {formatDateTime(trade.entry_time)}
                </td>
                <td className="whitespace-nowrap px-2 py-2 text-dark-300">
                  {formatDateTime(trade.exit_time)}
                </td>
                <td className="px-2 py-2 font-mono text-dark-200">{formatPrice(trade.entry_price)}</td>
                <td className="px-2 py-2 font-mono text-dark-200">{formatPrice(trade.exit_price)}</td>
                <td className="px-2 py-2 font-mono text-dark-200">{trade.size.toFixed(2)}</td>
                <td
                  className={cn(
                    'px-2 py-2 font-mono font-medium',
                    trade.pnl >= 0 ? 'text-gain' : 'text-loss'
                  )}
                >
                  {formatPnL(trade.pnl)}
                </td>
                <td className="px-2 py-2 font-mono text-dark-300">{formatPrice(trade.mae)}</td>
                <td className="px-2 py-2 font-mono text-dark-300">{formatPrice(trade.mfe)}</td>
                <td className="px-2 py-2 font-mono text-dark-300">{trade.hold_duration_bars}</td>
                <td className="px-2 py-2 text-dark-400">{trade.exit_reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedTrade && (
        <TradeDetail trade={selectedTrade} onClose={() => setSelectedTrade(null)} />
      )}
    </>
  );
}

import { useEffect, useRef } from 'react';
import type { Trade } from '@/types/backtest';
import { formatPrice, formatPnL, formatDateTime } from '@/lib/format';
import { cn } from '@/lib/cn';

interface TradeDetailProps {
  trade: Trade;
  onClose: () => void;
}

function DetailRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="border-dark-700 flex items-center justify-between border-b py-1.5">
      <span className="text-dark-400 text-[11px]">{label}</span>
      <span
        className={cn(
          'text-dark-50 font-mono text-xs font-medium',
          color && `text-${color}`
        )}
      >
        {value}
      </span>
    </div>
  );
}

export function TradeDetail({ trade, onClose }: TradeDetailProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onClose]);

  const pnlFormatted = formatPnL(trade.pnl);
  const isProfitable = trade.pnl >= 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div
        ref={ref}
        className="border-dark-500 bg-dark-800 w-full max-w-md rounded border p-4 shadow-xl"
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-dark-50 text-sm font-semibold">
            Trade #{trade.trade_index}
            <span className="text-dark-400 ml-2">{trade.symbol}</span>
          </h3>
          <button
            onClick={onClose}
            className="text-dark-400 hover:text-dark-50 transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="mb-3">
          <span
            className={cn(
              'rounded px-2 py-0.5 text-xs font-medium',
              trade.direction === 'Long'
                ? 'bg-gain/10 text-gain'
                : 'bg-loss/10 text-loss'
            )}
          >
            {trade.direction}
          </span>
          <span
            className={cn(
              'ml-2 rounded px-2 py-0.5 text-xs font-medium',
              isProfitable ? 'bg-gain/10 text-gain' : 'bg-loss/10 text-loss'
            )}
          >
            {isProfitable ? 'Profit' : 'Loss'}
          </span>
        </div>

        <div className="bg-dark-900 rounded px-3 py-2">
          <DetailRow
            label="Entry Time"
            value={formatDateTime(trade.entry_time)}
          />
          <DetailRow
            label="Exit Time"
            value={formatDateTime(trade.exit_time)}
          />
          <DetailRow
            label="Entry Price"
            value={formatPrice(trade.entry_price)}
          />
          <DetailRow label="Exit Price" value={formatPrice(trade.exit_price)} />
          <DetailRow label="Size" value={trade.size.toFixed(4)} />
          <DetailRow
            label="PnL"
            value={pnlFormatted}
            color={isProfitable ? 'text-gain' : 'text-loss'}
          />
          <DetailRow label="Fees" value={formatPrice(trade.fees)} />
          <DetailRow label="MAE" value={formatPrice(trade.mae)} />
          <DetailRow label="MFE" value={formatPrice(trade.mfe)} />
          <DetailRow
            label="Hold Duration"
            value={`${trade.hold_duration_bars} bars`}
          />
          <DetailRow label="Exit Reason" value={trade.exit_reason} />
        </div>
      </div>
    </div>
  );
}

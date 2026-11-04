/**
 * Open Positions Tracker (Slice 3 — Mission Surface)
 *
 * Shows today's open paper trades with current R (unrealized P&L in R units).
 * Uses the journal's read_open_positions and computes current R from
 * the latest close price vs entry/stop.
 */

import { useEffect, useMemo, useState } from 'react';
import { Clock } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useWorkflowStore } from '@/store/workflowStore';
import { fetchLatestPrice } from '@/api/market';
import type { PaperTrade } from '@/types/workflow';
import { TermLink } from '@/components/learn/TermLink';

interface OpenPositionWithR extends PaperTrade {
  currentPrice: number | null;
  currentR: number | null;
  unrealizedPct: number | null;
  daysHeld: number;
}

export function OpenPositionsTracker() {
  const paperTrades = useWorkflowStore((s) => s.paperTrades);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);

  const openTrades = useMemo(
    () => paperTrades.filter((t) => t.status === 'open'),
    [paperTrades]
  );

  // Fetch latest prices for open positions
  useEffect(() => {
    if (openTrades.length === 0) return;
    let cancelled = false;

    const fetchPrices = async () => {
      setLoading(true);
      const newPrices: Record<string, number> = {};
      for (const trade of openTrades) {
        try {
          const price = await fetchLatestPrice(trade.symbol);
          if (price != null && !cancelled) {
            newPrices[trade.symbol] = price;
          }
        } catch {
          // ignore individual failures
        }
      }
      if (!cancelled) {
        setPrices(newPrices);
        setLoading(false);
      }
    };

    fetchPrices();
    // Refresh every 30 seconds
    const interval = setInterval(fetchPrices, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [openTrades]);

  // Compute current R for each open position
  const positionsWithR = useMemo((): OpenPositionWithR[] => {
    return openTrades.map((trade) => {
      const currentPrice = prices[trade.symbol] ?? null;
      let currentR: number | null = null;
      let unrealizedPct: number | null = null;

      if (
        currentPrice != null &&
        trade.entryPrice != null &&
        trade.stopLoss != null
      ) {
        const risk = trade.entryPrice - trade.stopLoss;
        if (risk > 0) {
          currentR = (currentPrice - trade.entryPrice) / risk;
          unrealizedPct =
            ((currentPrice - trade.entryPrice) / trade.entryPrice) * 100;
        }
      }

      // Days held
      let daysHeld = 0;
      if (trade.openedAt) {
        const opened = new Date(trade.openedAt);
        const now = new Date();
        daysHeld = Math.floor(
          (now.getTime() - opened.getTime()) / (1000 * 60 * 60 * 24)
        );
      }

      return { ...trade, currentPrice, currentR, unrealizedPct, daysHeld };
    });
  }, [openTrades, prices]);

  if (positionsWithR.length === 0) {
    return (
      <div className="rounded-xl border border-border/50 bg-surface/20 p-6 text-center">
        <Clock className="mx-auto h-10 w-10 text-text-muted" />
        <h3 className="mt-3 text-sm font-semibold text-text-primary">
          Open Positions
        </h3>
        <p className="mx-auto mt-2 max-w-md text-xs text-text-muted">
          No open paper trades. Log a trade from the Execution Engine to track
          it here.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border/50 bg-surface/20 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Clock className="h-4 w-4 text-accent" />
          Open Positions ({positionsWithR.length})
          {loading && (
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          )}
        </h3>
        {loading && (
          <span className="text-[10px] text-text-muted">Updating…</span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/30 text-left text-text-muted">
              <th className="pb-2 pr-3 font-medium">Symbol</th>
              <th className="pb-2 pr-3 font-medium">Entry</th>
              <th className="pb-2 pr-3 font-medium">Stop</th>
              <th className="pb-2 pr-3 text-right font-medium">Current R</th>
              <th className="pb-2 pr-3 text-right font-medium">Unrealized %</th>
              <th className="pb-2 pr-3 text-right font-medium">Days</th>
              <th className="pb-2 text-right font-medium">Gate</th>
            </tr>
          </thead>
          <tbody>
            {positionsWithR.map((pos) => {
              const r = pos.currentR;
              const pct = pos.unrealizedPct;
              const rClass = cn(
                'font-mono font-semibold',
                r === null
                  ? 'text-text-muted'
                  : r > 0
                    ? 'text-green-500'
                    : r < 0
                      ? 'text-red-500'
                      : 'text-text-muted'
              );
              const pctClass = cn(
                'font-mono',
                pct === null
                  ? 'text-text-muted'
                  : pct > 0
                    ? 'text-green-500'
                    : pct < 0
                      ? 'text-red-500'
                      : 'text-text-muted'
              );
              const gateClass = cn(
                'inline-block rounded-full border px-2 py-0.5 text-[10px] font-medium',
                pos.gateVerdict === 'PASS'
                  ? 'text-green-500 bg-green-500/10 border-green-500/30'
                  : pos.gateVerdict === 'CONDITIONAL'
                    ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30'
                    : 'text-red-500 bg-red-500/10 border-red-500/30'
              );

              return (
                <tr key={pos.id} className="border-t border-border/20">
                  <td className="py-2 pr-3 font-mono font-semibold text-text-primary">
                    {pos.symbol}
                  </td>
                  <td className="py-2 pr-3 font-mono text-text-primary">
                    {pos.entryPrice?.toFixed(2) ?? '—'}
                  </td>
                  <td className="py-2 pr-3 font-mono text-text-secondary">
                    {pos.stopLoss?.toFixed(2) ?? '—'}
                  </td>
                  <td className={cn('py-2 pr-3 text-right', rClass)}>
                    {r !== null ? `${r >= 0 ? '+' : ''}${r.toFixed(2)}` : '—'}
                  </td>
                  <td className={cn('py-2 pr-3 text-right', pctClass)}>
                    {pct !== null
                      ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
                      : '—'}
                  </td>
                  <td className="py-2 pr-3 text-right text-text-muted">
                    {pos.daysHeld}
                  </td>
                  <td className="py-2 text-right">
                    <span className={gateClass}>{pos.gateVerdict ?? '—'}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[11px] text-text-muted">
        Current R = (current_price - entry) / (entry - stop).{' '}
        <TermLink text="R-multiple" /> measures unrealized P&L in risk units.
        Green = ahead of plan; Red = behind plan; updates every 30s.
      </p>
    </div>
  );
}

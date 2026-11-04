import { useState } from 'react';
import { cn } from '@/lib/cn';
import {
  ChevronDown,
  ChevronUp,
  Zap,
  TrendingUp,
  TrendingDown,
  Plus,
  AlertTriangle,
  CheckCircle,
  Download,
  RefreshCw,
} from 'lucide-react';
import type { SimpleBacktestResponse } from '@/api/backtest';

interface SimpleBacktestResultsProps {
  data: SimpleBacktestResponse | null;
  onRunNewBacktest: () => void;
}

const METRIC_CARDS = [
  { key: 'total_return', label: 'Total Return', format: (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`, positive: (v: number) => v >= 0, icon: TrendingUp },
  { key: 'annualized_return', label: 'Annualized Return', format: (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`, positive: (v: number) => v >= 0, icon: TrendingUp },
  { key: 'sharpe_ratio', label: 'Sharpe Ratio', format: (v: number) => v.toFixed(2), positive: (v: number) => v >= 1, icon: TrendingUp },
  { key: 'sortino_ratio', label: 'Sortino Ratio', format: (v: number) => v.toFixed(2), positive: (v: number) => v >= 1, icon: TrendingUp },
  { key: 'max_drawdown_pct', label: 'Max Drawdown', format: (v: number) => `${v.toFixed(2)}%`, positive: (v: number) => v <= 10, icon: TrendingDown },
  { key: 'win_rate', label: 'Win Rate', format: (v: number) => `${v.toFixed(2)}%`, positive: (v: number) => v >= 50, icon: CheckCircle },
  { key: 'profit_factor', label: 'Profit Factor', format: (v: number) => v.toFixed(2), positive: (v: number) => v >= 1.5, icon: TrendingUp },
  { key: 'expectancy', label: 'Expectancy', format: (v: number) => v.toFixed(2), positive: (v: number) => v >= 0, icon: TrendingUp },
  { key: 'total_trades', label: 'Total Trades', format: (v: number) => v.toString(), positive: (v: number) => v >= 10, icon: Plus },
  { key: 'avg_hold_days', label: 'Avg Hold (days)', format: (v: number) => v.toFixed(1), positive: (v: number) => v >= 1 && v <= 30, icon: AlertTriangle },
];

export function SimpleBacktestResults({ data, onRunNewBacktest }: SimpleBacktestResultsProps) {
  const [expandedTrades, setExpandedTrades] = useState(false);

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-text-muted">
        <Zap className="h-12 w-12 text-text-muted/30" />
        <p className="mt-4 text-lg">No backtest results yet</p>
        <p className="text-sm">Run a backtest to see results</p>
      </div>
    );
  }

  const metrics = data.metrics;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h3 className="font-display text-xl font-semibold tracking-tight text-text-primary">
            Backtest Results: {data.template}
          </h3>
          <p className="text-sm text-text-muted mt-1">
            {data.symbol} | {data.timeframe} | {data.metrics.total_trades} trades | {data.duration_ms}ms
          </p>
        </div>
        <button
          onClick={onRunNewBacktest}
          className="flex items-center gap-2 bg-surface-elevated hover:bg-surface-hover text-text-secondary px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Run New Backtest
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {METRIC_CARDS.map((metric) => {
          const value = metrics[metric.key as keyof typeof metrics];
          const isPositive = metric.positive(value);
          return (
            <div
              key={metric.key}
              className={cn(
                'rounded-lg border p-4 transition-colors',
                isPositive ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'
              )}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">{metric.label}</span>
                <metric.icon className={cn('h-3 w-3', isPositive ? 'text-green-500' : 'text-red-500')} />
              </div>
              <div className={cn('font-mono text-lg font-semibold', isPositive ? 'text-green-500' : 'text-red-500')}>
                {metric.format(value)}
              </div>
            </div>
          );
        })}
      </div>

      {/* Trades Table */}
      {data.trades.length > 0 && (
        <div className="border-t border-border/30 pt-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium text-text-primary">Trade Details ({data.trades.length})</h4>
            <button
              onClick={() => setExpandedTrades(!expandedTrades)}
              className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors"
            >
              {expandedTrades ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {expandedTrades ? `Show fewer (${Math.min(data.trades.length, 10)})` : `Show all (${data.trades.length})`}
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-text-muted border-b border-border/30">
                  <th className="pb-2 pr-4 font-medium">#</th>
                  <th className="pb-2 pr-4 font-medium">Entry</th>
                  <th className="pb-2 pr-4 font-medium">Exit</th>
                  <th className="pb-2 pr-4 font-medium">Entry $</th>
                  <th className="pb-2 pr-4 font-medium">Exit $</th>
                  <th className="pb-2 pr-4 font-medium">Units</th>
                  <th className="pb-2 pr-4 font-medium">P&L</th>
                  <th className="pb-2 pr-4 font-medium">Return</th>
                  <th className="pb-2 pr-4 font-medium">Hold</th>
                </tr>
              </thead>
              <tbody>
                {data.trades
                  .slice(0, expandedTrades ? data.trades.length : 10)
                  .map((trade) => (
                    <tr
                      key={trade.trade_id}
                      className="border-b border-border/20 hover:bg-surface-hover/50 transition-colors"
                    >
                      <td className="py-2 pr-4 font-mono">{trade.trade_id}</td>
                      <td className="py-2 pr-4">{trade.entry_date}</td>
                      <td className="py-2 pr-4">{trade.exit_date}</td>
                      <td className="py-2 pr-4 font-mono">${trade.entry_price.toFixed(2)}</td>
                      <td className="py-2 pr-4 font-mono">${trade.exit_price.toFixed(2)}</td>
                      <td className="py-2 pr-4 font-mono">{trade.units.toFixed(4)}</td>
                      <td className={cn('py-2 pr-4 font-mono font-medium', trade.pnl >= 0 ? 'text-green-500' : 'text-red-500')}>
                        {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                      </td>
                      <td className={cn('py-2 pr-4 font-mono font-medium', trade.return_pct >= 0 ? 'text-green-500' : 'text-red-500')}>
                        {trade.return_pct >= 0 ? '+' : ''}{trade.return_pct.toFixed(2)}%
                      </td>
                      <td className="py-2 pr-4 font-mono">{trade.hold_days}d</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Equity Curve Summary */}
      {data.equity_curve.length > 0 && (
        <div className="border-t border-border/30 pt-4">
          <h4 className="font-medium text-text-primary mb-3">Equity Curve</h4>
          <div className="h-48 rounded-lg bg-surface p-4 relative">
            <EquityCurveChart data={data.equity_curve} />
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3 pt-4 border-t border-border/30">
        <button
          onClick={onRunNewBacktest}
          className="flex items-center gap-2 bg-accent text-white hover:bg-accent-dark px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Run Another
        </button>
        <button
          className="flex items-center gap-2 bg-surface-elevated hover:bg-surface-hover text-text-secondary px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Download className="h-4 w-4" />
          Export CSV
        </button>
      </div>
    </div>
  );
}

// Simple equity curve chart component
function EquityCurveChart({ data }: { data: Array<{ date: string; equity: number }> }) {
  if (data.length === 0) return null;

  const minEquity = Math.min(...data.map(d => d.equity));
  const maxEquity = Math.max(...data.map(d => d.equity));
  const range = maxEquity - minEquity || 1;
  const initialEquity = data[0].equity;

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 100 - ((d.equity - minEquity) / range) * 90; // Leave 5% margin top/bottom
    return `${x}% ${y}%`;
  }).join(' ');

  const zeroLine = 100 - ((initialEquity - minEquity) / range) * 90;

  return (
    <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
      <defs>
        <linearGradient id="equityGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
        </linearGradient>
      </defs>
      
      {/* Zero line */}
      <line x1="0" y1={zeroLine} x2="100" y2={zeroLine} stroke="currentColor" strokeOpacity="0.2" strokeDasharray="4 4" />
      
      {/* Area */}
      <polygon
        points={`0,100 ${points} 100,100`}
        fill="url(#equityGradient)"
      />
      
      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke="#22c55e"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      
      {/* Current value */}
      <circle cx={100} cy={100 - ((data[data.length - 1].equity - minEquity) / range) * 90} r="3" fill="#22c55e" />
    </svg>
  );
}
import type { Metrics } from '@/types/backtest';
import { formatPct, formatNumber } from '@/lib/format';
import { cn } from '@/lib/cn';

interface MetricItem {
  label: string;
  value: string | number;
  color?: 'gain' | 'loss' | 'neutral';
  tooltip?: string;
}

function MetricCard({ label, value, color = 'neutral' }: MetricItem) {
  return (
    <div className="rounded border border-dark-600 bg-dark-800 px-3 py-2.5">
      <p className="mb-0.5 text-[10px] uppercase tracking-wider text-dark-400">{label}</p>
      <p
        className={cn(
          'font-mono text-sm font-semibold',
          color === 'gain' && 'text-gain',
          color === 'loss' && 'text-loss',
          color === 'neutral' && 'text-dark-50'
        )}
      >
        {value}
      </p>
    </div>
  );
}

function pctColor(v: number): 'gain' | 'loss' | 'neutral' {
  if (v > 0) return 'gain';
  if (v < 0) return 'loss';
  return 'neutral';
}

export function MetricsCards({ metrics }: { metrics: Metrics }) {
  const items: MetricItem[] = [
    {
      label: 'Total Return',
      value: formatPct(metrics.total_return_pct),
      color: pctColor(metrics.total_return_pct),
    },
    {
      label: 'Sharpe Ratio',
      value: formatNumber(metrics.sharpe_ratio, 2),
      color: metrics.sharpe_ratio >= 1 ? 'gain' : metrics.sharpe_ratio >= 0 ? 'neutral' : 'loss',
    },
    {
      label: 'Sortino Ratio',
      value: formatNumber(metrics.sortino_ratio, 2),
      color: metrics.sortino_ratio >= 1 ? 'gain' : 'neutral',
    },
    {
      label: 'Calmar Ratio',
      value: formatNumber(metrics.calmar_ratio, 2),
      color: metrics.calmar_ratio >= 1 ? 'gain' : 'neutral',
    },
    {
      label: 'Max Drawdown',
      value: formatPct(metrics.max_drawdown_pct),
      color: pctColor(-metrics.max_drawdown_pct),
    },
    {
      label: 'Win Rate',
      value: formatPct(metrics.win_rate),
      color: metrics.win_rate >= 50 ? 'gain' : 'loss',
    },
    {
      label: 'Profit Factor',
      value: formatNumber(metrics.profit_factor, 2),
      color: metrics.profit_factor >= 1.5 ? 'gain' : metrics.profit_factor >= 1 ? 'neutral' : 'loss',
    },
    {
      label: 'Expectancy',
      value: formatNumber(metrics.expectancy, 2),
      color: metrics.expectancy > 0 ? 'gain' : 'loss',
    },
    {
      label: 'SQN',
      value: formatNumber(metrics.sqn, 2),
      color: metrics.sqn >= 2 ? 'gain' : metrics.sqn >= 1 ? 'neutral' : 'loss',
    },
    {
      label: 'Ulcer Index',
      value: formatNumber(metrics.ulcer_index, 2),
      color: metrics.ulcer_index < 5 ? 'gain' : metrics.ulcer_index < 15 ? 'neutral' : 'loss',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
      {items.map((item) => (
        <MetricCard key={item.label} {...item} />
      ))}
    </div>
  );
}

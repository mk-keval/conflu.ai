import type { Metrics } from '@/types/backtest';
import { formatPct, formatNumber } from '@/lib/format';
import { cn } from '@/lib/cn';
import { HelpCircle } from 'lucide-react';
import { EducationTooltip } from '@/components/professional/EducationTooltip';

interface MetricItem {
  label: string;
  value: string | number;
  color?: 'gain' | 'loss' | 'neutral';
  metricKey: string;
}

function MetricCard({ label, value, color = 'neutral', metricKey }: MetricItem) {
  return (
    <div className="rounded border border-dark-600 bg-dark-800 px-3 py-2.5">
      <div className="mb-0.5 flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-wider text-dark-400">{label}</p>
        <EducationTooltip metricKey={metricKey} metricLabel={label} metricValue={String(value)} compact />
      </div>
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
      metricKey: 'total_return_pct',
    },
    {
      label: 'Sharpe Ratio',
      value: formatNumber(metrics.sharpe_ratio, 2),
      color: metrics.sharpe_ratio >= 1 ? 'gain' : metrics.sharpe_ratio >= 0 ? 'neutral' : 'loss',
      metricKey: 'sharpe_ratio',
    },
    {
      label: 'Sortino Ratio',
      value: formatNumber(metrics.sortino_ratio, 2),
      color: metrics.sortino_ratio >= 1 ? 'gain' : 'neutral',
      metricKey: 'sortino_ratio',
    },
    {
      label: 'Calmar Ratio',
      value: formatNumber(metrics.calmar_ratio, 2),
      color: metrics.calmar_ratio >= 1 ? 'gain' : 'neutral',
      metricKey: 'calmar_ratio',
    },
    {
      label: 'Max Drawdown',
      value: formatPct(metrics.max_drawdown_pct),
      color: pctColor(-metrics.max_drawdown_pct),
      metricKey: 'max_drawdown_pct',
    },
    {
      label: 'Win Rate',
      value: formatPct(metrics.win_rate),
      color: metrics.win_rate >= 50 ? 'gain' : 'loss',
      metricKey: 'win_rate',
    },
    {
      label: 'Profit Factor',
      value: formatNumber(metrics.profit_factor, 2),
      color: metrics.profit_factor >= 1.5 ? 'gain' : metrics.profit_factor >= 1 ? 'neutral' : 'loss',
      metricKey: 'profit_factor',
    },
    {
      label: 'Expectancy',
      value: formatNumber(metrics.expectancy, 2),
      color: metrics.expectancy > 0 ? 'gain' : 'loss',
      metricKey: 'expectancy',
    },
    {
      label: 'SQN',
      value: formatNumber(metrics.sqn, 2),
      color: metrics.sqn >= 2 ? 'gain' : metrics.sqn >= 1 ? 'neutral' : 'loss',
      metricKey: 'sqn',
    },
    {
      label: 'Ulcer Index',
      value: formatNumber(metrics.ulcer_index, 2),
      color: metrics.ulcer_index < 5 ? 'gain' : metrics.ulcer_index < 15 ? 'neutral' : 'loss',
      metricKey: 'ulcer_index',
    },
  ];

  return (
    <>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {items.map((item) => (
          <MetricCard key={item.label} {...item} />
        ))}
      </div>

      <details className="mt-4 rounded border border-dark-600 bg-dark-800 p-3">
        <summary className="cursor-pointer list-none">
          <div className="flex items-center gap-2 text-xs font-medium text-dark-200">
            <HelpCircle className="h-3.5 w-3.5 text-dark-400" />
            How to read these results
          </div>
        </summary>
        <ul className="mt-2 space-y-1 text-xs text-dark-300">
          <li>
            Win rate means nothing without average win/loss — a 70% win rate with small winners and
            large losers still loses money.
          </li>
          <li>
            Profit factor above 1.5 is acceptable; above 2.0 is strong but can signal overfitting on
            too few trades.
          </li>
          <li>
            Fewer than 100 trades makes any statistic noisy — use with caution.
          </li>
          <li>
            Max drawdown measures the worst decline from a peak so far, not the worst possible drop —
            it hides tail risk beyond the observed period.
          </li>
          <li>
            Positive expectancy (avg profit per trade) is the defining signal of an edge — if it is
            not positive, no other metric can save you.
          </li>
        </ul>
      </details>
    </>
  );
}

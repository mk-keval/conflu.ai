import { useState } from 'react';
import { cn } from '@/lib/cn';
import {
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Search,
  BarChart2,
  TrendingUp,
  TrendingDown,
  Eye,
  Copy,
  Plus,
  Download,
} from 'lucide-react';
import {
  type FilterSweepSummary,
  type FilterSweepResult,
} from '@/types/backtest';

interface FilterSweepResultsProps {
  summary: FilterSweepSummary | null;
  onRunNewSweep?: () => void;
}

const METRIC_LABELS: Record<string, { label: string; higherBetter: boolean }> = {
  expectancy: { label: 'Expectancy', higherBetter: true },
  sharpe: { label: 'Sharpe Ratio', higherBetter: true },
  sortino: { label: 'Sortino Ratio', higherBetter: true },
  calmar: { label: 'Calmar Ratio', higherBetter: true },
  win_rate: { label: 'Win Rate', higherBetter: true },
  profit_factor: { label: 'Profit Factor', higherBetter: true },
  total_return: { label: 'Total Return', higherBetter: true },
  annualized_return: { label: 'Annualized Return', higherBetter: true },
  max_drawdown: { label: 'Max Drawdown', higherBetter: false },
  total_trades: { label: 'Total Trades', higherBetter: true },
  avg_hold_days: { label: 'Avg Hold Days', higherBetter: false },
  max_drawdown_pct: { label: 'Max DD %', higherBetter: false },
};

function formatValue(value: number | null | undefined, metric: string): string {
  if (value === null || value === undefined) return '—';
  
  const isPercentage = ['win_rate', 'max_drawdown', 'total_return', 'annualized_return', 'max_drawdown_pct'].includes(metric);
  const isRatio = ['sharpe', 'sortino', 'calmar', 'profit_factor', 'recovery_factor', 'payoff_ratio'].includes(metric);
  const isCount = ['total_trades', 'winning_trades', 'losing_trades', 'max_consecutive_wins', 'max_consecutive_losses'].includes(metric);
  
  if (isPercentage) {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  }
  if (isRatio) {
    return value.toFixed(2);
  }
  if (isCount) {
    return value.toFixed(0);
  }
  if (['avg_win', 'avg_loss', 'best_trade', 'worst_trade', 'avg_hold_days', 'payoff_ratio', 'recovery_factor'].includes(metric)) {
    return value.toFixed(2);
  }
  return value.toFixed(2);
}

function MetricBadge({ value, metric, rank }: { value: number | null; metric: string; rank?: number }) {
  const metricInfo = METRIC_LABELS[metric];
  const label = metricInfo?.label || metric;
  
  return (
    <div className="flex items-center gap-1.5">
      {rank !== undefined && (
        <span className="flex items-center justify-center w-5 h-5 rounded bg-accent/20 text-accent text-[10px] font-bold">
          #{rank}
        </span>
      )}
      <span className="text-[10px] text-text-muted uppercase tracking-wider">{label}</span>
      <span className="font-mono text-xs font-semibold text-text-primary">
        {formatValue(value, metric)}
      </span>
    </div>
  );
}

function ResultCard({ result, index }: { result: FilterSweepResult; index: number }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className="border-dark-600 bg-dark-800 rounded border p-4 transition-colors hover:border-accent/30">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="flex items-center justify-center w-6 h-6 rounded bg-accent/20 text-accent text-xs font-bold">
            #{index + 1}
          </span>
          <div>
            <p className="text-xs text-text-muted">Parameters</p>
            <p className="font-mono text-xs text-text-primary truncate max-w-xs">
              {JSON.stringify(result.params).slice(0, 60)}{Object.keys(result.params).length > 3 ? '...' : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-dark-400 hover:text-text-primary transition-colors"
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
        <MetricBadge value={result.expectancy} metric="expectancy" rank={1} />
        <MetricBadge value={result.sharpe} metric="sharpe" rank={2} />
        <MetricBadge value={result.win_rate} metric="win_rate" rank={3} />
        <MetricBadge value={result.profit_factor} metric="profit_factor" rank={4} />
        <MetricBadge value={result.total_return} metric="total_return" rank={5} />
        <MetricBadge value={result.max_drawdown} metric="max_drawdown" rank={6} />
        <MetricBadge value={result.total_trades} metric="total_trades" rank={7} />
        <MetricBadge value={result.win_rate} metric="win_rate" rank={8} />
      </div>

      {expanded && (
        <div className="border-t border-border/30 pt-3 space-y-2">
          <details className="group">
            <summary className="group flex items-center gap-2 text-xs text-text-muted cursor-pointer">
              <ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" />
              All Parameters
            </summary>
            <div className="mt-2 grid grid-cols-2 gap-1 text-[10px] text-text-secondary">
              {Object.entries(result.params).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="font-mono text-text-muted">{k}</span>
                  <span className="font-mono text-text-primary">{JSON.stringify(v)}</span>
                </div>
              ))}
            </div>
          </details>

          <details className="group">
            <summary className="group flex items-center gap-2 text-xs text-text-muted cursor-pointer">
              <ChevronRight className="h-3 w-3 transition-transform group-open:rotate-90" />
              All Metrics
            </summary>
            <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-1 text-[10px] text-text-secondary">
              {Object.entries({
                'Total Return': result.total_return,
                'Annualized Return': result.annualized_return,
                'Sharpe': result.sharpe,
                'Sortino': result.sortino,
                'Calmar': result.calmar,
                'Max DD': result.max_drawdown,
                'Win Rate': result.win_rate,
                'Profit Factor': result.profit_factor,
                'Expectancy': result.expectancy,
                'Avg Win': result.avg_win,
                'Avg Loss': result.avg_loss,
                'Total Trades': result.total_trades,
                'Winning Trades': result.winning_trades,
                'Losing Trades': result.losing_trades,
                'Avg Hold Days': result.avg_hold_days,
                'Max Consec Wins': result.max_consecutive_wins,
                'Max Consec Losses': result.max_consecutive_losses,
                'Max DD %': result.max_drawdown_pct,
                'Recovery Factor': result.recovery_factor,
                'Payoff Ratio': result.payoff_ratio,
                'Best Trade': result.best_trade,
                'Worst Trade': result.worst_trade,
              }).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-text-muted">{k}</span>
                  <span className="font-mono text-text-primary">{v !== null && v !== undefined ? (typeof v === 'number' ? v.toFixed(2) : v) : '—'}</span>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/30">
        <button className="flex-1 flex items-center justify-center gap-1 text-xs text-accent hover:text-accent/80 transition-colors">
          <Eye className="h-3 w-3" />
          View Details
        </button>
        <button className="flex-1 flex items-center justify-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors">
          <Copy className="h-3 w-3" />
          Copy Params
        </button>
        <button className="flex-1 flex items-center justify-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors">
          <Download className="h-3 w-3" />
          Export
        </button>
      </div>
    </div>
  );
}

export function FilterSweepResults({ summary, onRunNewSweep }: FilterSweepResultsProps) {
  const [sortMetric, setSortMetric] = useState<'expectancy' | 'sharpe' | 'win_rate' | 'profit_factor' | 'calmar' | 'total_return'>('expectancy');
  const [sortAscending, setSortAscending] = useState(false);
  const [searchParams, setSearchParams] = useState('');

  if (!summary) {
    return (
      <div className="flex items-center justify-center h-64 text-text-muted">
        <div className="text-center">
          <BarChart2 className="mx-auto h-12 w-12 text-text-muted/50 mb-4" />
          <p className="text-text-muted">No sweep results to display</p>
          <p className="text-xs text-text-muted mt-1">Run a filter sweep to see results here</p>
        </div>
      </div>
    );
  }

  const { name, screen_name, total_combinations, valid_results, failed_results, best_by_sharpe, best_by_expectancy, best_by_win_rate, best_by_profit_factor, best_by_calmar, all_results, status } = summary;

  // Filter and sort results
  let filteredResults = all_results.filter(r => r.valid);
  
  if (searchParams) {
    const search = searchParams.toLowerCase();
    filteredResults = filteredResults.filter(r => 
      Object.values(r.params).some(v => String(v).toLowerCase().includes(search)) ||
      r.run_id.toLowerCase().includes(search)
    );
  }

  filteredResults.sort((a, b) => {
    const aVal = a[sortMetric] ?? -Infinity;
    const bVal = b[sortMetric] ?? -Infinity;
    return sortAscending ? aVal - bVal : bVal - aVal;
  });

  const metricOptions = [
    { value: 'expectancy', label: 'Expectancy' },
    { value: 'sharpe', label: 'Sharpe Ratio' },
    { value: 'win_rate', label: 'Win Rate' },
    { value: 'profit_factor', label: 'Profit Factor' },
    { value: 'calmar', label: 'Calmar Ratio' },
    { value: 'total_return', label: 'Total Return' },
  ] as const;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border/30 px-4 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-dark-100 font-semibold">{name}</h2>
          <p className="text-xs text-text-muted">{screen_name} · {total_combinations} combinations · {valid_results} valid · {failed_results} failed</p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1 rounded-lg border border-border/30 bg-surface/30 px-2 py-1">
            <Search className="h-3 w-3 text-text-muted mr-1" />
            <input
              type="text"
              placeholder="Search params..."
              value=""
              onChange={(e) => setSearchParams(e.target.value)}
              className="bg-transparent text-text-primary placeholder:text-text-muted text-xs w-40 focus:outline-none"
            />
          </div>
          
          <select
            value={sortMetric}
            onChange={(e) => setSortMetric(e.target.value as typeof sortMetric)}
            className="rounded border border-border/30 bg-surface px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
          >
            {metricOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          
          <button
            onClick={() => setSortAscending(!sortAscending)}
            className="rounded border border-border/30 bg-surface px-2 py-1 text-xs text-text-muted hover:bg-surface-hover transition-colors"
          >
            {sortAscending ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
          </button>
        </div>
      </div>

      {/* Status & Summary */}
      <div className="px-4 py-3 space-y-2">
        <div className="flex items-center gap-3 flex-wrap">
          <span className={cn(
            'rounded-full px-2 py-0.5 text-[10px] font-semibold',
            status === 'running' ? 'bg-yellow-500/20 text-yellow-400' :
            status === 'completed' ? 'bg-green-500/20 text-green-400' :
            'bg-red-500/20 text-red-400'
          )}>
            {status.toUpperCase()}
          </span>
          <span className="text-xs text-text-muted">{total_combinations} combinations</span>
          <span className="text-xs text-green-400">{valid_results} valid</span>
          {failed_results > 0 && <span className="text-xs text-red-400">{failed_results} failed</span>}
        </div>

        {/* Best by metric cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2 mt-2">
          {best_by_expectancy && (
            <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-2">
              <p className="text-[10px] text-text-muted">Best Expectancy</p>
              <p className="font-mono text-sm font-semibold text-green-400">{best_by_expectancy.expectancy?.toFixed(2)}</p>
              <p className="text-[10px] text-text-muted">{best_by_expectancy.total_trades} trades</p>
            </div>
          )}
          {best_by_sharpe && (
            <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-2">
              <p className="text-[10px] text-text-muted">Best Sharpe</p>
              <p className="font-mono text-sm font-semibold text-blue-400">{best_by_sharpe.sharpe?.toFixed(2)}</p>
              <p className="text-[10px] text-text-muted">{best_by_sharpe.total_trades} trades</p>
            </div>
          )}
          {best_by_win_rate && (
            <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-2">
              <p className="text-[10px] text-text-muted">Best Win Rate</p>
              <p className="font-mono text-sm font-semibold text-green-400">{((best_by_win_rate.win_rate || 0) * 100).toFixed(1)}%</p>
              <p className="text-[10px] text-text-muted">{best_by_win_rate.total_trades} trades</p>
            </div>
          )}
          {best_by_profit_factor && (
            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-2">
              <p className="text-[10px] text-text-muted">Best Profit Factor</p>
              <p className="font-mono text-sm font-semibold text-yellow-400">{best_by_profit_factor.profit_factor?.toFixed(2)}</p>
              <p className="text-[10px] text-text-muted">{best_by_profit_factor.total_trades} trades</p>
            </div>
          )}
          {best_by_calmar && (
            <div className="rounded-lg border border-purple-500/30 bg-purple-500/5 p-2">
              <p className="text-[10px] text-text-muted">Best Calmar</p>
              <p className="font-mono text-sm font-semibold text-purple-400">{best_by_calmar.calmar?.toFixed(2)}</p>
              <p className="text-[10px] text-text-muted">{best_by_calmar.total_trades} trades</p>
            </div>
          )}
        </div>
      </div>

      {/* Results Table */}
      <div className="flex-1 overflow-auto px-4 pb-4">
        <div className="space-y-2">
          {filteredResults.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-text-muted">
              <p className="text-text-muted">No results match your search</p>
            </div>
          ) : (
            filteredResults.map((result, index) => (
              <ResultCard key={result.run_id} result={result} index={index} />
            ))
          )}
        </div>
      </div>

      {/* Footer Actions */}
      <div className="border-t border-border/30 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span>Showing {filteredResults.length} of {all_results.filter(r => r.valid).length} valid results</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onRunNewSweep}
            className="bg-dark-600 text-dark-200 hover:bg-dark-500 rounded px-3 py-1.5 text-xs transition-colors"
          >
            <Plus className="h-3 w-3" />
            New Sweep
          </button>
        </div>
      </div>
    </div>
  );
}
import { useQuery, useMutation } from '@tanstack/react-query';
import { compareBacktests, fetchBacktest } from '@/api/backtest';
import { useBacktestStore } from '@/store/backtest';
import { cn } from '@/lib/cn';
import type { StrategyComparisonResult } from '@/types/backtest';

function AvailableRuns() {
  const { recentRunIds, comparisonRunIds, addComparisonRunId, removeComparisonRunId } = useBacktestStore();

  if (!recentRunIds.length) {
    return (
      <div className="flex h-16 items-center justify-center rounded border border-dashed border-dark-600 text-xs text-dark-400">
        No runs available — run a backtest first
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <h4 className="text-xs font-semibold text-dark-300 mb-1">Select Runs to Compare</h4>
      {recentRunIds.map((runId) => (
        <RunCheckbox
          key={runId}
          runId={runId}
          isSelected={comparisonRunIds.includes(runId)}
          onToggle={(selected) => selected ? addComparisonRunId(runId) : removeComparisonRunId(runId)}
        />
      ))}
    </div>
  );
}

function RunCheckbox({ runId, isSelected, onToggle }: { runId: string; isSelected: boolean; onToggle: (selected: boolean) => void }) {
  const { data } = useQuery({
    queryKey: ['backtest', runId],
    queryFn: () => fetchBacktest(runId),
    staleTime: Infinity,
    gcTime: Infinity,
  });

  return (
    <label className={cn(
      'flex items-center gap-2 rounded border px-3 py-2 text-xs cursor-pointer transition-colors',
      isSelected ? 'border-accent bg-accent/10' : 'border-dark-600 bg-dark-800 hover:border-dark-500'
    )}>
      <input
        type="checkbox"
        checked={isSelected}
        onChange={(e) => onToggle(e.target.checked)}
        className="rounded border-dark-500 bg-dark-700 text-accent focus:ring-accent"
      />
      <span className="text-dark-50">{data?.symbol ?? runId.slice(0, 8)}</span>
      {data?.timeframe && <span className="text-dark-400">@{data.timeframe}</span>}
      {data && <span className="text-dark-400 ml-auto">{data.trades_count} trades</span>}
    </label>
  );
}

function MetricsTable({ result }: { result: StrategyComparisonResult }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-dark-600">
            <th className="px-3 py-2 text-left text-dark-400 font-medium">Metric</th>
            {result.labels.map((label) => (
              <th key={label} className="px-3 py-2 text-right text-dark-400 font-medium">{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.metrics_table.map((row, i) => (
            <tr key={i} className="border-b border-dark-700 hover:bg-dark-800/50">
              <td className="px-3 py-2 text-dark-200 font-medium">{row.metric as string}</td>
              {result.labels.map((label) => {
                const val = row[label];
                return (
                  <td key={label} className={cn('px-3 py-2 text-right font-mono',
                    val === 'N/A' ? 'text-dark-500' :
                    typeof val === 'number' ? (val > 0 ? 'text-gain' : 'text-loss') : 'text-dark-50'
                  )}>
                    {val as string}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EquityOverlay({ result }: { result: StrategyComparisonResult }) {
  const colors = ['#00e676', '#40c4ff', '#ffd740', '#ff5252', '#e040fb', '#ff9100', '#69f0ae', '#18ffff'];
  const series = Object.entries(result.equity_curves).slice(0, 8);

  if (series.length === 0) {
    return <p className="text-xs text-dark-400 text-center py-8">No equity curve data available</p>;
  }

  return (
    <div className="space-y-0.5">
      {series.map(([runId, points], i) => (
        <div key={runId} className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: colors[i % colors.length] }} />
          <span className="text-xs text-dark-200">{result.labels[result.run_ids.indexOf(runId)] || runId.slice(0, 8)}</span>
          <span className="text-[10px] text-dark-400 ml-auto">
            Start: {(points[0]?.value ?? 1).toFixed(2)} &rarr; End: {(points[points.length - 1]?.value ?? 1).toFixed(2)}
          </span>
        </div>
      ))}
      <p className="text-[10px] text-dark-500 mt-2">Equity curves normalized to base=1.0</p>
    </div>
  );
}

function BestByMetricCards({ result }: { result: StrategyComparisonResult }) {
  const metricLabels: Record<string, string> = {
    sharpe: 'Sharpe', sortino: 'Sortino', calmar: 'Calmar',
    max_dd: 'Max DD', win_rate: 'Win Rate', profit_factor: 'Profit Factor',
    expectancy: 'Expectancy', sqn: 'SQN', ulcer: 'Ulcer', cagr: 'CAGR',
  };

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
      {Object.entries(result.best_by_metric).slice(0, 10).map(([metric, runId]) => (
        <div key={metric} className="rounded border border-dark-600 bg-dark-800 p-2">
          <p className="text-[10px] text-dark-400 uppercase">{metricLabels[metric] || metric}</p>
          <p className="text-xs font-semibold text-dark-50 mt-0.5 truncate">
            {result.labels[result.run_ids.indexOf(runId)] || runId.slice(0, 8)}
          </p>
        </div>
      ))}
    </div>
  );
}

export function ComparisonDashboard() {
  const { comparisonRunIds, clearComparisonRunIds } = useBacktestStore();

  const mutation = useMutation({
    mutationFn: () => compareBacktests({
      run_ids: comparisonRunIds,
      labels: null,
      include_significance: true,
      bootstrap_samples: 1000,
    }),
    onSuccess: () => {},
  });

  return (
    <div className="space-y-4 rounded border border-dark-600 bg-dark-800 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-dark-100">Strategy Comparison</h3>
        {comparisonRunIds.length > 0 && (
          <button onClick={clearComparisonRunIds}
            className="text-[10px] text-dark-400 hover:text-dark-200 transition-colors">
            Clear selection
          </button>
        )}
      </div>

      <AvailableRuns />

      <button
        onClick={() => mutation.mutate()}
        disabled={comparisonRunIds.length < 2 || mutation.isPending}
        className={cn('w-full rounded py-2 text-sm font-semibold transition-colors',
          comparisonRunIds.length < 2 || mutation.isPending
            ? 'cursor-not-allowed bg-dark-500 text-dark-300'
            : 'bg-accent text-white hover:bg-accent-dark'
        )}
      >
        {mutation.isPending
          ? 'Comparing...'
          : comparisonRunIds.length < 2
            ? `Select ${2 - comparisonRunIds.length} more run(s)`
            : `Compare ${comparisonRunIds.length} Runs`}
      </button>

      {mutation.isError && (
        <p className="text-xs text-loss">Error: {(mutation.error as Error)?.message}</p>
      )}

      {mutation.data && (
        <div className="space-y-4 pt-2 border-t border-dark-600">
          <h4 className="text-xs font-semibold text-dark-200">Best by Metric</h4>
          <BestByMetricCards result={mutation.data} />

          <h4 className="text-xs font-semibold text-dark-200">Metrics Comparison</h4>
          <MetricsTable result={mutation.data} />

          <h4 className="text-xs font-semibold text-dark-200">Equity Curves (Normalized)</h4>
          <EquityOverlay result={mutation.data} />
        </div>
      )}
    </div>
  );
}

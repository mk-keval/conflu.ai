import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchBacktest } from '@/api/backtest';
import { useBacktestStore } from '@/store/backtest';
import { BacktestForm } from './BacktestForm';
import { BacktestResult } from './BacktestResult';
import { ComparisonDashboard } from './ComparisonDashboard';
import { ErrorBoundary } from '@/components/layout/ErrorBoundary';
import { OptimizationForm } from './OptimizationForm';
import { cn } from '@/lib/cn';

function RecentRuns() {
  const { recentRunIds, selectedRunId, setSelectedRunId } = useBacktestStore();

  if (!recentRunIds.length) {
    return (
      <div className="flex h-24 items-center justify-center rounded border border-dashed border-dark-600 text-xs text-dark-400">
        No recent backtests
      </div>
    );
  }

  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold text-dark-300">Recent Runs</h3>
      <div className="space-y-1">
        {recentRunIds.map((runId) => (
          <RecentRunItem
            key={runId}
            runId={runId}
            isActive={runId === selectedRunId}
            onClick={() => setSelectedRunId(runId)}
          />
        ))}
      </div>
    </div>
  );
}

function RecentRunItem({
  runId,
  isActive,
  onClick,
}: {
  runId: string;
  isActive: boolean;
  onClick: () => void;
}) {
  const { data } = useQuery({
    queryKey: ['backtest', runId],
    queryFn: () => fetchBacktest(runId),
    staleTime: Infinity,
    gcTime: Infinity,
  });

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full rounded border px-3 py-2 text-left text-xs transition-colors',
        isActive
          ? 'border-accent bg-accent/10'
          : 'border-dark-600 bg-dark-800 hover:border-dark-500'
      )}
    >
      <p className="font-medium text-dark-50">
        {data?.symbol ?? runId.slice(0, 8)}
        {data?.timeframe && <span className="ml-1 text-dark-400">@{data.timeframe}</span>}
      </p>
      <p className="mt-0.5 text-[10px] text-dark-400">
        {data ? `${data.trades_count} trades` : 'Loading...'}
      </p>
    </button>
  );
}

const TABS = ['Run', 'Optimize', 'Compare'] as const;

function BacktestContent() {
  const { selectedRunId } = useBacktestStore();
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>('Run');

  if (selectedRunId) {
    return (
      <div className="flex h-full flex-col">
        <BacktestResult runId={selectedRunId} />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex border-b border-dark-600 px-4">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-px',
              activeTab === tab
                ? 'border-accent text-accent'
                : 'border-transparent text-dark-400 hover:text-dark-200'
            )}
          >
            {tab}
          </button>
        ))}
      </div>
      <div className="flex flex-1 gap-4 p-4">
        {activeTab === 'Run' && (
          <>
            <div className="w-80 shrink-0">
              <BacktestForm />
            </div>
            <div className="flex-1">
              <RecentRuns />
            </div>
          </>
        )}
        {activeTab === 'Optimize' && (
          <div className="w-full max-w-lg mx-auto">
            <OptimizationForm />
          </div>
        )}
        {activeTab === 'Compare' && (
          <div className="w-full max-w-2xl mx-auto">
            <ComparisonDashboard />
          </div>
        )}
      </div>
    </div>
  );
}

export function BacktestPage() {
  return (
    <ErrorBoundary>
      <BacktestContent />
    </ErrorBoundary>
  );
}

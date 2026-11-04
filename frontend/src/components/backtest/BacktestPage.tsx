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
      <div className="border-dark-600 bg-dark-800 text-dark-300 rounded border border-dashed p-4 text-center text-xs">
        <h3 className="text-dark-50 mb-1 text-sm font-semibold">
          What is a backtest?
        </h3>
        <p className="text-dark-400 mb-2 max-w-md text-xs">
          A backtest replays your rules against real historical data to see how
          they would have performed. It proves nothing about the future — it
          filters out ideas that never worked at all.
        </p>
        <p className="text-dark-400 text-[10px]">
          Run your first test using the form to the left: pick a symbol,
          timeframe, and strategy parameters, then click Run.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h3 className="text-dark-300 mb-2 text-xs font-semibold">Recent Runs</h3>
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
      <p className="text-dark-50 font-medium">
        {data?.symbol ?? runId.slice(0, 8)}
        {data?.timeframe && (
          <span className="text-dark-400 ml-1">@{data.timeframe}</span>
        )}
      </p>
      <p className="text-dark-400 mt-0.5 text-[10px]">
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
      <div className="border-dark-600 flex border-b px-4">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              '-mb-px border-b-2 px-4 py-2 text-xs font-medium transition-colors',
              activeTab === tab
                ? 'border-accent text-accent'
                : 'text-dark-400 hover:text-dark-200 border-transparent'
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
          <div className="mx-auto w-full max-w-lg">
            <OptimizationForm />
          </div>
        )}
        {activeTab === 'Compare' && (
          <div className="mx-auto w-full max-w-2xl">
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

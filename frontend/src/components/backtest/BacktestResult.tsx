import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { fetchBacktest, fetchTrades, fetchEquity } from '@/api/backtest';
import { useBacktestStore } from '@/store/backtest';
import { useWS } from '@/ws/WebSocketProvider';
import { backtestChannel } from '@/ws/channels';
import { SkeletonCard } from '@/components/layout/LoadingSkeleton';
import { MetricsCards } from './MetricsCards';
import { EquityCurveChart } from './EquityCurveChart';
import { DrawdownChart } from './DrawdownChart';
import { RegimeTimeline } from './RegimeTimeline';
import { ReportDownload } from './ReportDownload';
import { TradesTable } from './TradesTable';
import type { WSMessage, WSBacktestUpdate } from '@/types/ws';

interface BacktestResultProps {
  runId: string;
}

export function BacktestResult({ runId }: BacktestResultProps) {
  const navigate = useNavigate();
  const { setSelectedRunId } = useBacktestStore();
  const { subscribe, unsubscribe, onMessage } = useWS();

  const {
    data: result,
    isLoading: resultLoading,
    isError: resultError,
    error: resultErr,
  } = useQuery({
    queryKey: ['backtest', runId],
    queryFn: () => fetchBacktest(runId),
  });

  const { data: trades, isLoading: tradesLoading } = useQuery({
    queryKey: ['backtest', runId, 'trades'],
    queryFn: () => fetchTrades(runId),
    enabled: !!result,
  });

  const { data: equity, isLoading: equityLoading } = useQuery({
    queryKey: ['backtest', runId, 'equity'],
    queryFn: () => fetchEquity(runId),
    enabled: !!result,
  });

  // Subscribe to backtest WS updates
  useEffect(() => {
    const channel = backtestChannel(runId);
    subscribe(channel);
    return () => unsubscribe(channel);
  }, [runId, subscribe, unsubscribe]);

  // Listen for backtest status updates
  useEffect(() => {
    const unsub = onMessage((message: WSMessage) => {
      if (message.type === 'backtest_update') {
        const update = message as WSBacktestUpdate;
        if (update.data.run_id === runId && update.data.status === 'complete') {
          // Refetch data when backtest completes
          window.location.reload();
        }
      }
    });
    return unsub;
  }, [onMessage, runId]);

  useEffect(() => {
    setSelectedRunId(runId);
  }, [runId, setSelectedRunId]);

  if (resultLoading) {
    return (
      <div className="space-y-4 p-4">
        <div className="grid grid-cols-5 gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        <SkeletonCard className="h-64" />
      </div>
    );
  }

  if (resultError) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <p className="mb-2 text-loss">Error loading backtest</p>
          <p className="text-dark-400 text-xs">
            {(resultErr as Error)?.message}
          </p>
          <button
            onClick={() => navigate('/backtest')}
            className="mt-4 rounded bg-accent px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-accent-dark"
          >
            Back to Backtest
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/backtest')}
          className="text-dark-400 hover:text-dark-50 transition-colors"
        >
          ← Back
        </button>
        <div>
          <h2 className="text-dark-50 text-base font-semibold">
            Backtest Result
          </h2>
          <p className="text-dark-400 text-[11px]">
            Run ID: {runId}
            {result && (
              <>
                <span className="mx-2">·</span>
                {result.symbol} @ {result.timeframe}
                <span className="mx-2">·</span>
                {result.trades_count} trades
                <span className="mx-2">·</span>
                {(result.duration_ms / 1000).toFixed(1)}s
              </>
            )}
          </p>
        </div>
      </div>

      {/* Metrics */}
      {result?.metrics && <MetricsCards metrics={result.metrics} />}

      {/* Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {equity && !equityLoading && (
          <EquityCurveChart
            data={equity}
            initialCash={result?.metrics ? undefined : undefined}
          />
        )}
        {equity && !equityLoading && (
          <DrawdownChart data={equity} initialCash={0} />
        )}
      </div>

      {/* Trades */}
      {trades && !tradesLoading && <TradesTable trades={trades} />}

      {/* Regime Timeline */}
      {result && <RegimeTimeline runId={runId} symbol={result.symbol} />}

      {/* Report Download */}
      <ReportDownload runId={runId} />
    </div>
  );
}
